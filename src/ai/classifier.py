"""
Module d'évaluation déontologique et de classification par IA (Google Gemini).
Inclut cache disque pour les réponses Gemini, backoff exponentiel, support multimodal
des affiches courtes, et repli heuristique déterministe de haute précision.
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.ai.schemas import ClassifiedEvent
from src.scrapers.base_scraper import RawPublication
from src.utils.date_helpers import extract_time_range, get_current_date, parse_dates_from_string
from src.utils.http_client import fetch_bytes
from src.utils.text_helpers import clean_event_title, normalize_text, smart_truncate

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "classifier_cache.json"
CACHE_SCHEMA_VERSION = "schema_v2"


def _build_system_prompt(ref_date: Optional[date] = None) -> str:
    ref = ref_date or get_current_date()
    return f"""Tu es l'assistant d'évaluation déontologique et éditoriale du portail citoyen officiel de la commune de Dunières (Haute-Loire, 43220) et de la communauté de communes 'Haut Pays du Velay Communauté'.

Ton rôle est d'analyser chaque publication pour déterminer si elle doit être diffusée aux administrés sur le calendrier municipal et de la structurer rigoureusement.

CRITÈRES DÉONTOLOGIQUES STRICTS :
1. INTÉRÊT PUBLIC LOCAL (is_public_interest = True) :
   - Vie municipale & intercommunale (séances de conseil, délibérations, vœux, arrêtés du maire, enquêtes publiques).
   - Travaux, voirie, chantiers, coupures d'eau ou d'électricité, déchèteries, collectes.
   - Événements associatifs, culturels et sportifs ouverts au public (fêtes locales, lotos, concours, concerts, médiathèque, randos, marchés, réunions publiques).
   - Permanences des services publics (France Services, assistante sociale, mission locale, MDA).
   - Alertes météo, prévention sanitaire ou consignes de sécurité publique.

2. EXCLUSION FORMELLE (is_public_interest = False) :
   - FAITS DIVERS INDIVIDUELS : accidents de la route, cambriolages, violences, affaires judiciaires/tribunal (exclure sauf s'il s'agit d'une réunion publique de prévention/sensibilisation).
   - VIE PRIVÉE : litiges de voisinage, informations nominatives personnelles, condoléances privées.
   - ENTREPRISES PRIVÉES & PUBLI-REPORTAGES : portraits/ouvertures de commerces, garages, artisans ou micro-entreprises privées, publi-reportages ou promotions commerciales sans caractère d'intérêt général pour la commune.
   - COMPTES-RENDUS SPORTIFS OU SORTIES DE LIVRES SANS ÉVÉNEMENT : simples résultats/palmarès de matchs passés ou parutions de livres/BD sans annonce d'une rencontre, dédicace ou conférence publique datée.
   - DÉBATS PARTISANS : tracts électoraux polémiques ou attaques nominatives.

RÈGLES D'EXTRACTION STRICTES :
- La date de référence aujourd'hui est {ref.isoformat()} (année {ref.year}).
- Extrais UNIQUEMENT la date, les horaires, le lieu précis (salle + commune) et le tarif d'entrée de l'ÉVÉNEMENT PRINCIPAL. Ignore les encarts secondaires ou événements annexes parfois cités en bas d'un article de presse.
- Ne mets JAMAIS un montant de lot de concours, un bénéfice caritatif ou le prix d'un livre dans `price`. Laisse `price` à null s'il n'y a pas de tarif d'entrée/inscription explicite.
- Si plusieurs séances ont lieu le même jour (ex: '13h à 19h' et '20h30 à 22h'), renseigne `start_time`/`end_time` avec la première et ajoute les suivantes dans `additional_slots` au format 'HH:MM-HH:MM'.
- Rédige un titre sobre en français commençant par une majuscule, sans emoji décoratif au début (max 120 caractères) et un résumé factuel en 1 à 3 phrases complètes.
"""


def _detect_image_mime(data: bytes, url: str) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    low = (url or "").lower()
    if low.endswith(".png"):
        return "image/png"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if low.endswith(".webp"):
        return "image/webp"
    return None


class GeminiClassifier:
    """Classeur IA utilisant Google Gemini avec cache disque et repli heuristique déterministe."""

    def __init__(self, api_key: Optional[str] = None, cache_path: Optional[Path] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.cache_path = Path(cache_path) if cache_path is not None else DEFAULT_CACHE_PATH
        self.client = None
        self._cache: Dict[str, Dict[str, Any]] = {}

        if self.api_key and self.api_key != "AIzaSyYourGeminiApiKeyHere":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                self._load_cache()
                logger.info("Client Google Gemini initialisé avec succès.")
            except Exception as e:
                logger.warning(f"Impossible d'initialiser le SDK google-genai : {e}. Utilisation du mode repli.")
        else:
            logger.info("Aucune clé GEMINI_API_KEY valide fournie. Fonctionnement en mode heuristique sécurisé.")

        self.stats: Dict[str, Any] = {
            "mode": "gemini" if self.client else "heuristic",
            "gemini_ok": 0,
            "gemini_fallback": 0,
            "cache_hits": 0,
            "heuristic_only": 0,
        }

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._cache = data
        except Exception as e:
            logger.debug(f"Cache classificateur illisible ({e}), réinitialisation.")
            self._cache = {}

    def save_cache(self) -> None:
        """Persiste sur disque uniquement les résultats validés par Gemini."""
        if not self.client or not self._cache:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache IA : {e}")

    def _compute_cache_key(self, pub: RawPublication, ref_date: date) -> str:
        payload = "|".join([
            CACHE_SCHEMA_VERSION,
            str(ref_date.year),
            pub.id or "",
            normalize_text(pub.title),
            normalize_text(pub.content),
            str(pub.published_at or ""),
            ",".join(sorted(pub.enrichment.keys())),
            str(pub.image_url or ""),
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def classify(self, pub: RawPublication, ref_date: Optional[date] = None) -> ClassifiedEvent:
        """Évalue une publication et renvoie un événement structuré."""
        ref = ref_date or get_current_date()

        if self.client:
            cache_key = self._compute_cache_key(pub, ref)
            cached = self._cache.get(cache_key)
            if isinstance(cached, dict) and cached.get("engine") == "gemini" and isinstance(cached.get("event"), dict):
                try:
                    event = ClassifiedEvent(**cached["event"])
                    self.stats["cache_hits"] += 1
                    return event
                except Exception:
                    pass

            try:
                event = self._classify_with_gemini(pub, ref_date=ref)
                self._cache[cache_key] = {
                    "engine": "gemini",
                    "cached_at": ref.isoformat(),
                    "event": event.model_dump(),
                }
                self.stats["gemini_ok"] += 1
                return event
            except Exception as e:
                logger.warning(
                    f"Erreur lors de l'appel Gemini pour '{pub.title}': {e}. Bascule sur le classificateur heuristique."
                )
                self.stats["gemini_fallback"] += 1
                return self._classify_heuristically(pub, ref_date=ref)

        self.stats["heuristic_only"] += 1
        return self._classify_heuristically(pub, ref_date=ref)

    def _classify_with_gemini(self, pub: RawPublication, ref_date: Optional[date] = None) -> ClassifiedEvent:
        from google.genai import types

        ref = ref_date or get_current_date()
        clean_title = normalize_text(pub.title)
        clean_content = normalize_text(pub.content)

        prompt = f"""Analyse cette publication issue de la source '{pub.source_name}' (type={'presse' if pub.raw_metadata.get('is_press') else 'officiel'}) :
TITRE : {clean_title}
DATE SOURCE : {pub.published_at or 'Inconnue'}
CONTENU COMPLET (incluant enrichissements récursifs Calaméo/PDF) :
{clean_content[:4000]}

Retourne l'objet JSON correspondant au schéma attendu.
"""
        contents: Any = prompt

        # Lecture multimodale optionnelle d'affiche pour annonces officielles courtes
        if (
            not pub.raw_metadata.get("is_press")
            and pub.image_url
            and len(clean_content) < 280
        ):
            img_bytes = fetch_bytes(pub.image_url, timeout=10, max_size_bytes=3 * 1024 * 1024)
            if img_bytes:
                mime = _detect_image_mime(img_bytes, pub.image_url)
                if mime:
                    contents = [
                        prompt,
                        types.Part.from_bytes(data=img_bytes, mime_type=mime),
                    ]

        last_exc: Optional[Exception] = None
        delays = (2, 5)
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_build_system_prompt(ref),
                        response_mime_type="application/json",
                        response_schema=ClassifiedEvent,
                        temperature=0.1,
                    ),
                )
                data = json.loads(response.text)
                event = ClassifiedEvent(**data)
                event.title = clean_event_title(smart_truncate(event.title, 120))
                event.summary = normalize_text(event.summary)
                event.location = normalize_text(event.location) or "Dunières / Haut Pays du Velay"
                if event.price:
                    event.price = normalize_text(event.price)
                return event
            except Exception as e:
                last_exc = e
                if attempt < len(delays):
                    time.sleep(delays[attempt])

        raise last_exc if last_exc else RuntimeError("Échec Gemini inconnu")

    @staticmethod
    def _extract_primary_text(title_clean: str, content_clean: str, is_press: bool) -> str:
        """
        Isole le texte de l'événement principal pour les articles de presse afin d'éviter
        la contamination par des encarts annexes situés en fin d'article.
        """
        if not is_press:
            return f"{title_clean}\n{content_clean}"

        paragraphs = [p.strip() for p in content_clean.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1 and "\n" in content_clean:
            paragraphs = [p.strip() for p in content_clean.split("\n") if p.strip()]

        kept: List[str] = []
        for idx, p in enumerate(paragraphs[:3]):
            if idx >= 1 and len(p) <= 95 and not p.endswith((".", "!", "?", "»", '"')):
                if re.search(
                    r"\b(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre|no[ëe]l|sortie)\b",
                    p,
                    re.IGNORECASE,
                ):
                    break
            kept.append(p)

        body = "\n\n".join(kept) if kept else content_clean[:800]
        return f"{title_clean}\n{body}"

    def _extract_location(self, text: str) -> str:
        """Extrait un lieu précis (emoji 📍, salle nommée ou commune locale)."""
        for line in text.splitlines():
            if "📍" in line:
                loc = line.split("📍", 1)[1].strip(" :-–\t")
                loc = normalize_text(loc)
                if 2 < len(loc) <= 120:
                    return loc

        # Recherche d'une salle ou équipement avec éventuelle commune associée
        m_venue_commune = re.search(
            r"\b(?:à\s+la|a\s+la|à\s+l['’]|au)\s+"
            r"((?:Salle|Médiathèque|Bibliothèque|Gymnase|Mairie|Cinéma|Église|Caserne|Centre|Foyer|Espace|Maison|Stade|Complexe)"
            r"(?:\s+(?:de\s+la|de\s+l['’]|des|du|de|d['’]))?"
            r"(?:\s+[A-Za-zÀ-ÿ0-9'’-]+){1,6}?)"
            r"(?=\s+(?:a|est|sont|ont|aura|sera|propose|accueille|rencontre|pour|avec|qui|et)\b|\s+(?:de|du|le)\s+\d|[,.\n(:]|$)",
            text,
            re.IGNORECASE,
        )
        commune_match = re.search(
            r"\b(?:à|en)\s+(Dunières|Montfaucon-en-Velay|Raucoules|Riotord|Saint[- ]Romain[- ]Lachalm|Montregard|Saint[- ]Bonnet[- ]le[- ]Froid|Saint[- ]Julien[- ]Molhesabate|Tence)\b",
            text,
            re.IGNORECASE,
        )

        venue_str = ""
        if m_venue_commune:
            venue_str = normalize_text(m_venue_commune.group(1))
            if venue_str and venue_str[0].islower():
                venue_str = venue_str[0].upper() + venue_str[1:]
        else:
            m_simple_venue = re.search(
                r"\b((?:Salle|Médiathèque|Bibliothèque|Gymnase|Cinéma|Caserne|Foyer)\s+[A-ZÀ-Ÿ][^,.\n(:]{2,45})",
                text,
            )
            if m_simple_venue:
                venue_str = normalize_text(m_simple_venue.group(1))

        commune_str = ""
        if commune_match:
            raw_c = normalize_text(commune_match.group(1))
            # Normaliser la casse pour "TENCE" -> "Tence" tout en respectant les traits d'union
            commune_str = raw_c.title().replace("-En-", "-en-").replace("-Le-", "-le-") if raw_c.isupper() else raw_c

        if venue_str and commune_str:
            if commune_str.lower() in venue_str.lower():
                return venue_str
            return f"{venue_str}, {commune_str}"
        if venue_str:
            return venue_str
        if commune_str:
            return commune_str

        return "Dunières / Haut Pays du Velay"

    @staticmethod
    def _extract_price(text: str) -> Optional[str]:
        """Extrait un tarif d'entrée/inscription explicite sans confondre lots, livres ou bénéfices."""
        if not text:
            return None

        segments = re.split(r"[\n.!?;]+", text)
        excluded_context_re = re.compile(
            r"(?:lot\s*=|premier\s+lot|b[ée]n[ée]fices?|vendue?\s+au\s+prix|éditions?|budget|subvention)",
            re.IGNORECASE,
        )

        # 1. Tarifs explicites chiffrés (prioritaires avant "gratuit pour les moins de 12 ans")
        for seg in segments:
            if excluded_context_re.search(seg):
                continue
            m_explicit = re.search(
                r"(?:tarif|prix|adulte|formule|place|billet|entr[ée]e|inscription|menu|burger\s*\+\s*frites)"
                r"(?:\s*\([^)]+\))?\s*[:àa]?\s*(\d+(?:[.,]\d{1,2})?\s*€)",
                seg,
                re.IGNORECASE,
            )
            if m_explicit:
                return re.sub(r"\s+", " ", m_explicit.group(1)).strip()

        # 2. Mention d'entrée libre / gratuité générale
        for seg in segments:
            if excluded_context_re.search(seg):
                continue
            if re.search(r"\b(?:entr[ée]e\s+libre|acc[èe]s\s+libre)\b", seg, re.IGNORECASE):
                return "Gratuit"
            if re.search(r"\bgratuit(?:e|s)?\b", seg, re.IGNORECASE) and not re.search(
                r"accompagnement\s+gratuit|moins\s+de\s+\d+\s+ans", seg, re.IGNORECASE
            ):
                return "Gratuit"

        return None

    @staticmethod
    def _make_rejection(title_clean: str, reason: str) -> ClassifiedEvent:
        return ClassifiedEvent(
            is_public_interest=False,
            rejection_reason=reason,
            title=clean_event_title(smart_truncate(title_clean, 120)),
            summary="Information exclue du portail public.",
            category="Non retenu",
            badge="Exclu",
            location="Dunières",
            importance="low",
            content_type="news",
            price=None,
            start_date=None,
            end_date=None,
        )

    def _classify_heuristically(self, pub: RawPublication, ref_date: Optional[date] = None) -> ClassifiedEvent:
        """Classificateur de repli basé sur les règles déontologiques républicaines."""
        ref = ref_date or get_current_date()
        is_press = bool(pub.raw_metadata.get("is_press"))
        title_clean = clean_event_title(pub.title) or normalize_text(pub.title)
        content_clean = normalize_text(pub.content)
        full_text = f"{title_clean}\n{content_clean}".lower()
        primary_text = self._extract_primary_text(title_clean, content_clean, is_press=is_press)
        primary_lower = primary_text.lower()

        # 1. Filtre d'exclusion : publi-reportages & portraits d'entreprises privées
        commercial_patterns = [
            r"\bpubli-?reportage\b",
            r"\bcontenu sponsoris[ée]\b",
        ]
        for pat in commercial_patterns:
            if re.search(pat, full_text, re.IGNORECASE):
                return self._make_rejection(
                    title_clean,
                    "Publi-reportage ou communication commerciale privée sans caractère de service public",
                )

        has_public_event_marker = any(
            w in primary_lower
            for w in [
                "association", "conseil municipal", "mairie", "commune",
                "fête", "marché", "forum", "bourse aux", "karaoké",
                "spectacle", "concert", "loto", "concours", "réunion publique",
            ]
        )
        private_business_patterns = [
            r"\bmicro-?entreprise\b",
            r"\bouvre son garage\b",
            r"\bcr[ée]e des bijoux\b",
            r"\blance son activit[ée]\b",
            r"\bpropose diff[ée]rentes prestations\b",
        ]
        if not has_public_event_marker and any(re.search(p, full_text) for p in private_business_patterns):
            return self._make_rejection(
                title_clean,
                "Portrait ou ouverture d'entreprise commerciale privée sans portée de service public",
            )

        # Exclusion sorties de livres / BD sans rencontre ou dédicace publique
        book_patterns = [
            r"\bvient de publier un livre\b",
            r"\bdans son livre\b",
            r"\bautobiographie\b",
            r"\bcroqu[ée]e? en bd\b",
            r"\bbande dessin[ée]e intitul[ée]e\b",
        ]
        has_book_event = any(
            w in full_text
            for w in ["dédicace", "séance de dédicace", "rencontre littéraire", "conférence", "médiathèque"]
        )
        if not has_book_event and any(re.search(p, full_text) for p in book_patterns):
            return self._make_rejection(
                title_clean,
                "Parution d'ouvrage ou témoignage sans séance publique datée (dédicace/rencontre)",
            )

        # Exclusion comptes-rendus sportifs passés sans annonce d'événement local à venir
        sports_recap_patterns = [
            r"\bpoints pour\b",
            r"\bpalmar[èe]s\b",
            r"\bse sont illustr[ée]s\b",
            r"\bbrillent [àa]\b",
            r"\bnouvelle d[ée]faite\b",
        ]
        has_upcoming_local_match = any(
            w in full_text
            for w in ["prochain match à dunières", "match à domicile le", "inscriptions ouvertes", "tournoi ouvert à tous"]
        )
        if not has_upcoming_local_match and any(re.search(p, full_text) for p in sports_recap_patterns):
            return self._make_rejection(
                title_clean,
                "Compte-rendu sportif passé sans manifestation ouverte annoncée sur la commune",
            )

        # 2. Filtre faits divers sécuritaires (avec protection stricte des réunions de prévention / spectacles)
        strong_public_safe_markers = [
            "réunion publique", "sensibilisation", "premiers secours", "formation",
            "route barrée", "déviation", "cinéma", "spectacle", "théâtre",
            "ciné-débat", "atelier", "conférence",
        ]
        is_safe_public_context = any(w in full_text for w in strong_public_safe_markers) or (
            "prévention" in full_text
            and not any(w in full_text for w in ["plainte", "interpellé", "blessé", "victime"])
        )

        fait_divers_patterns = [
            r"\baccident de la route\b",
            r"\baccident corporel\b",
            r"\baccident mortel\b",
            r"\bbless[ée]s? graves?\b",
            r"\bbless[ée]s? l[ée]gers?\b",
            r"\brefus de priorit[ée]\b",
            r"\bcambriolages?\b",
            r"\bvol avec effraction\b",
            r"\bvol par effraction\b",
            r"\bvol de v[ée]hicule\b",
            r"\bvol de voiture\b",
            r"\bvictime d['’]un vol\b",
            r"\bgendarmerie appelle [àa] la vigilance\b",
            r"\bgarde [àa] vue\b",
            r"\btribunal correctionnel\b",
            r"\bincendie criminel\b",
            r"\bd[ée]c[èe]s tragique\b",
            r"\bagression\b",
            r"\bmeurtre\b",
        ]
        if not is_safe_public_context:
            for pat in fait_divers_patterns:
                if re.search(pat, full_text, re.IGNORECASE):
                    return self._make_rejection(
                        title_clean,
                        "Fait divers individuel ou sécuritaire sans portée de service public",
                    )

        # 3. Catégorisation thématique basée sur le texte principal
        category = "Manifestations & Vie Associative"
        badge = "Animation"
        importance = "normal"

        if any(w in primary_lower for w in [
            "monoxyde de carbone", "intoxication", "alerte", "vigilance météo",
            "coupure d'eau", "coupure d'électricité", "enedis", "neige",
            "verglas", "inondation", "consigne de sécurité"
        ]):
            category = "Alertes & Météo"
            badge = "Alerte Publique"
            importance = "high"
        elif any(w in primary_lower for w in [
            "arrêté", "travaux", "circulation", "route barrée", "déviation", "enrobé", "chantier"
        ]):
            category = "Travaux & Voirie"
            badge = "Arrêté / Travaux"
            importance = "high"
        elif any(w in primary_lower for w in [
            "déchets", "déchèterie", "déchetterie", "poubelles", "france services",
            "permanence", "mda", "maison départementale de l'autonomie"
        ]):
            category = "Services & Déchets"
            badge = "Service Public"
        elif any(
            re.search(rf"\b{re.escape(w)}\b", primary_lower)
            for w in [
                "conseil municipal", "délibération", "conseil communautaire",
                "arrêté municipal", "arrêté du maire", "vœux du maire",
                "séance du conseil", "ordre du jour", "enquête publique", "élections"
            ]
        ) and "conseil municipal des jeunes" not in primary_lower:
            category = "Vie Municipale & Délibérations"
            badge = "Conseil Municipal"
            importance = "high"
        elif any(w in primary_lower for w in [
            "médiathèque", "bibliothèque", "exposition", "cinéma", "spectacle",
            "musique", "concert", "théâtre"
        ]):
            category = "Culture & Patrimoine"
            badge = "Culture"
        elif any(w in primary_lower for w in [
            "école", "cantine", "jeunesse", "ados", "centre de loisirs"
        ]) and not any(w in primary_lower for w in ["soirée", "karaoké", "loto", "concert"]):
            category = "Enfance & Jeunesse"
            badge = "Enfance"

        # 4. Extraction de dates sur le texte principal, sinon date de publication source
        d_start, d_end = parse_dates_from_string(primary_text, default_year=ref.year, ref_date=ref)
        if not d_start and pub.published_at:
            d_pub, _ = parse_dates_from_string(pub.published_at, default_year=ref.year, ref_date=ref)
            if d_pub:
                d_start = d_pub

        start_str = d_start.strftime("%Y-%m-%d") if d_start else None
        end_str = d_end.strftime("%Y-%m-%d") if d_end else None

        # 5. Extraction des horaires multiples sur le texte principal
        timing = extract_time_range(primary_text)
        slots = timing.get("slots", [])
        additional_slots: List[str] = []
        for s in slots[1:]:
            if s.get("start_time") and s.get("end_time"):
                additional_slots.append(f"{s['start_time']}-{s['end_time']}")

        # 6. Nature éditoriale
        if category == "Alertes & Météo":
            content_type = "alert"
        elif category in ("Travaux & Voirie", "Vie Municipale & Délibérations", "Services & Déchets"):
            content_type = "info"
        elif is_press and not timing.get("start_time"):
            content_type = "news"
        else:
            content_type = "event"

        # 7. Résumé épuré basé sur les premiers paragraphes principaux
        clean_lines = []
        source_body_for_summary = primary_text.split("\n", 1)[1] if "\n" in primary_text else content_clean
        for line in source_body_for_summary.splitlines():
            s = line.strip()
            if not s or s.startswith("http") or s.lower() == title_clean.lower():
                continue
            clean_lines.append(s)

        summary_base = " ".join(clean_lines[:3]) if clean_lines else title_clean
        summary = smart_truncate(summary_base, 260)

        return ClassifiedEvent(
            is_public_interest=True,
            rejection_reason=None,
            title=smart_truncate(title_clean, 120),
            summary=summary,
            category=category,
            badge=badge,
            location=self._extract_location(primary_text),
            importance=importance,
            content_type=content_type,
            price=self._extract_price(primary_text),
            start_date=start_str,
            end_date=end_str,
            start_time=timing.get("start_time"),
            end_time=timing.get("end_time"),
            additional_slots=additional_slots,
        )
