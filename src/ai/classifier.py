"""
Module d'évaluation déontologique et de classification par IA (Google Gemini).
Garantit le tri strict de l'intérêt public local et le respect de la vie privée.
"""

import os
import re
import json
import logging
from typing import Optional
from dotenv import load_dotenv

from src.scrapers.base_scraper import RawPublication
from src.ai.schemas import ClassifiedEvent
from src.utils.date_helpers import parse_dates_from_string, extract_time_range, get_current_date
from src.utils.text_helpers import normalize_text, smart_truncate

load_dotenv()
logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    ref_date = get_current_date()
    return f"""Tu es l'assistant d'évaluation déontologique et éditoriale du portail citoyen officiel de la commune de Dunières (Haute-Loire, 43220) et de la communauté de communes 'Haut Pays du Velay Communauté'.

Ton rôle est d'analyser chaque publication pour déterminer si elle doit être diffusée aux administrés sur le calendrier municipal et de la structurer.

CRITÈRES DÉONTOLOGIQUES STRICTS :
1. INTÉRÊT PUBLIC LOCAL (is_public_interest = True) :
   - Vie municipale & intercommunale (séances de conseil, délibérations, vœux, arrêtés du maire).
   - Travaux, voirie, chantiers, coupures d'eau ou d'électricité, déchèteries, collectes.
   - Événements associatifs, culturels et sportifs ouverts au public (fêtes locales, lotos, concerts, médiathèque, randos, marchés).
   - Permanences des services publics (France Services, assistante sociale, mission locale, MDA).
   - Alertes météo, prévention sanitaire ou consignes de sécurité publique.

2. EXCLUSION FORMELLE (is_public_interest = False) :
   - FAITS DIVERS INDIVIDUELS : accidents de la route, cambriolages, violences, affaires judiciaires/tribunal (exclure systématiquement car anxiogènes et sans portée de service public).
   - VIE PRIVÉE : litiges de voisinage, informations nominatives personnelles, condoléances privées.
   - PUBLICITÉS COMMERCIALES & PUBLI-REPORTAGES : publi-reportages, annonces publicitaires ou promotions commerciales d'entreprises privées sans caractère d'intérêt général pour la commune.
   - DÉBATS PARTISANS : tracts électoraux polémiques ou attaques nominatives.

RÈGLES D'EXTRACTION :
- La date de référence aujourd'hui est {ref_date.isoformat()} (année {ref_date.year}).
- Si la publication contient des dates précises (ex: 'du 3 au 7 novembre', '22 nov. 2026', '15/11/{ref_date.year}'), extrais-les au format YYYY-MM-DD. Sinon utilise la date de publication source.
- Si des horaires sont mentionnés (ex: '18h30', 'de 14h à 19h', '16:00 - 17:00'), extrais start_time et end_time au format 24h HH:MM.
- Rédige un titre soigné (max 120 caractères, jamais coupé au milieu d'un mot) et un résumé clair et fluide en français sans mots collés ni coupés.
"""


class GeminiClassifier:
    """Classeur IA utilisant Google Gemini avec repli heuristique déterministe."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None

        if self.api_key and self.api_key != "AIzaSyYourGeminiApiKeyHere":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Client Google Gemini initialisé avec succès.")
            except Exception as e:
                logger.warning(f"Impossible d'initialiser le SDK google-genai : {e}. Utilisation du mode repli.")
        else:
            logger.info("Aucune clé GEMINI_API_KEY valide fournie. Fonctionnement en mode heuristique sécurisé.")

    def classify(self, pub: RawPublication) -> ClassifiedEvent:
        """Évalue une publication et renvoie un événement structuré."""
        if self.client:
            try:
                return self._classify_with_gemini(pub)
            except Exception as e:
                logger.warning(f"Erreur lors de l'appel Gemini pour '{pub.title}': {e}. Bascule sur le classificateur heuristique.")

        return self._classify_heuristically(pub)

    def _classify_with_gemini(self, pub: RawPublication) -> ClassifiedEvent:
        from google.genai import types

        clean_title = normalize_text(pub.title)
        clean_content = normalize_text(pub.content)

        prompt = f"""Analyse cette publication issue de la source '{pub.source_name}' :
TITRE : {clean_title}
DATE SOURCE : {pub.published_at or 'Inconnue'}
CONTENU COMPLET (incluant enrichissements récursifs Calaméo/PDF) :
{clean_content[:4000]}

Retourne l'objet JSON correspondant au schéma attendu.
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_build_system_prompt(),
                response_mime_type="application/json",
                response_schema=ClassifiedEvent,
                temperature=0.1,
            ),
        )

        data = json.loads(response.text)
        event = ClassifiedEvent(**data)
        event.title = smart_truncate(event.title, 120)
        event.summary = normalize_text(event.summary)
        event.location = normalize_text(event.location)
        return event

    def _extract_location(self, content: str) -> str:
        """Extrait un lieu précis lorsqu'il est indiqué avec 📍 dans le corps du texte."""
        for line in content.splitlines():
            if "📍" in line:
                loc = line.split("📍", 1)[1].strip(" :-–\t")
                loc = normalize_text(loc)
                if 2 < len(loc) <= 100:
                    return loc
        return "Dunières / Haut Pays du Velay"

    def _classify_heuristically(self, pub: RawPublication) -> ClassifiedEvent:
        """Classificateur de repli basé sur les règles déontologiques républicaines."""
        title_clean = normalize_text(pub.title)
        content_clean = normalize_text(pub.content)
        full_text = f"{title_clean}\n{content_clean}".lower()

        # 1. Filtre d'exclusion immédiate (faits divers, vie privée, publi-reportages)
        commercial_patterns = [
            r"\bpubli-?reportage\b",
            r"\bcontenu sponsoris[ée]\b",
        ]
        for pat in commercial_patterns:
            if re.search(pat, full_text, re.IGNORECASE):
                return ClassifiedEvent(
                    is_public_interest=False,
                    rejection_reason="Publi-reportage ou communication commerciale privée sans caractère de service public",
                    title=smart_truncate(title_clean, 120),
                    summary="Information exclue du portail public.",
                    category="Non retenu",
                    badge="Exclu",
                    location="Dunières",
                    importance="low",
                    start_date=None,
                    end_date=None,
                )

        rejection_words = [
            "accident", "blessé", "blessés", "refus de priorité", "cambriolage", "cambriolages",
            "vol", "vols", "voleur", "gendarmerie appelle à la vigilance", "prison", "tribunal",
            "délit", "incendie criminel", "décès tragique", "agression", "meurtre",
        ]
        for bad_word in rejection_words:
            pattern = rf"\b{re.escape(bad_word)}\b"
            if re.search(pattern, full_text, re.IGNORECASE):
                return ClassifiedEvent(
                    is_public_interest=False,
                    rejection_reason=f"Fait divers individuel ou sécuritaire ({bad_word}) sans lien avec le mandat public",
                    title=smart_truncate(title_clean, 120),
                    summary="Information exclue du portail public.",
                    category="Non retenu",
                    badge="Exclu",
                    location="Dunières",
                    importance="low",
                    start_date=None,
                    end_date=None,
                )

        # 2. Catégorisation thématique heuristique (ordre strict : Alertes et Services avant Culture/Assos)
        category = "Manifestations & Vie Associative"
        badge = "Animation"
        importance = "normal"

        if any(w in full_text for w in [
            "monoxyde de carbone", "intoxication", "alerte", "vigilance",
            "coupure d'eau", "coupure d'électricité", "enedis", "neige",
            "verglas", "inondation", "sécurité"
        ]):
            category = "Alertes & Météo"
            badge = "Alerte Publique"
            importance = "high"
        elif any(w in full_text for w in [
            "arrêté", "travaux", "circulation", "route barrée", "déviation", "enrobé", "chantier"
        ]):
            category = "Travaux & Voirie"
            badge = "Arrêté / Travaux"
            importance = "high"
        elif any(w in full_text for w in [
            "déchets", "déchèterie", "déchetterie", "poubelles", "france services",
            "permanence", "mda", "maison départementale de l'autonomie"
        ]):
            category = "Services & Déchets"
            badge = "Service Public"
        elif any(
            re.search(rf"\b{re.escape(w)}\b", full_text)
            for w in ["conseil municipal", "délibération", "conseil communautaire", "séance", "maire"]
        ) and "conseil municipal des jeunes" not in full_text:
            category = "Vie Municipale & Délibérations"
            badge = "Conseil Municipal"
            importance = "high"
        elif any(w in full_text for w in [
            "médiathèque", "bibliothèque", "exposition", "cinéma", "spectacle",
            "musique", "concert", "théâtre"
        ]):
            category = "Culture & Patrimoine"
            badge = "Culture"
        elif any(w in full_text for w in [
            "école", "cantine", "jeunesse", "ados", "centre de loisirs"
        ]) and not any(w in full_text for w in ["soirée", "karaoké", "loto", "concert"]):
            category = "Enfance & Jeunesse"
            badge = "Enfance"

        # 3. Extraction de dates (d'abord dans le contenu, sinon date de publication)
        ref_year = get_current_date().year
        d_start, d_end = parse_dates_from_string(f"{title_clean}\n{content_clean}", default_year=ref_year)

        if not d_start and pub.published_at:
            d_pub, _ = parse_dates_from_string(pub.published_at, default_year=ref_year)
            if d_pub:
                d_start = d_pub

        start_str = d_start.strftime("%Y-%m-%d") if d_start else None
        end_str = d_end.strftime("%Y-%m-%d") if d_end else None

        # 4. Extraction des horaires structurés
        timing = extract_time_range(f"{title_clean}\n{content_clean}")

        # 5. Résumé épuré sans couper au milieu d'un mot
        clean_lines = []
        for line in content_clean.splitlines():
            s = line.strip()
            if not s or s.startswith("http") or s == title_clean:
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
            location=self._extract_location(content_clean),
            importance=importance,
            start_date=start_str,
            end_date=end_str,
            start_time=timing.get("start_time"),
            end_time=timing.get("end_time"),
        )
