"""
Module d'évaluation déontologique et de classification par IA (Google Gemini).
Garantit le tri strict de l'intérêt public local et le respect de la vie privée.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import date
from dotenv import load_dotenv

from src.scrapers.base_scraper import RawPublication
from src.ai.schemas import ClassifiedEvent
from src.utils.date_helpers import parse_dates_from_string, get_current_date

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es l'assistant d'évaluation déontologique et éditoriale du portail citoyen officiel de la commune de Dunières (Haute-Loire, 43220) et de la communauté de communes 'Haut Pays du Velay Communauté'.

Ton rôle est d'analyser chaque publication pour déterminer si elle doit être diffusée aux administrés sur le calendrier municipal et de la structurer.

CRITÈRES DÉONTOLOGIQUES STRICTS :
1. INTÉRÊT PUBLIC LOCAL (is_public_interest = True) :
   - Vie municipale & intercommunale (séances de conseil, délibérations, vœux, arrêtés du maire).
   - Travaux, voirie, chantiers, coupures d'eau ou d'électricité, déchèteries, collectes.
   - Événements associatifs, culturels et sportifs ouverts au public (fêtes locales, lotos, concerts, médiathèque, randos, marchés).
   - Permanences des services publics (France Services, assistante sociale, mission locale).
   - Alertes météo ou consignes de sécurité publique.

2. EXCLUSION FORMELLE (is_public_interest = False) :
   - FAITS DIVERS INDIVIDUELS : accidents de la route, cambriolages, violences, affaires judiciaires/tribunal (exclure systématiquement car anxiogènes et sans portée de service public).
   - VIE PRIVÉE : litiges de voisinage, informations nominatives personnelles, condoléances privées.
   - PUBLICITÉS COMMERCIALES STRICTES : promotions de commerces ou d'entreprises privées sans caractère d'intérêt général pour la commune.
   - DÉBATS PARTISANS : tracts électoraux polémiques ou attaques nominatives.

RÈGLES D'EXTRACTION :
- Si la publication contient des dates précises (ex: 'du 3 au 7 novembre', '15/11/2026'), extrais-les au format YYYY-MM-DD.
- La date de référence aujourd'hui est l'année courante 2026.
- Rédige un titre soigné et un résumé clair et bienveillant pour les citoyens.
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
        # 1. Tentative d'analyse via Gemini si le client est disponible
        if self.client:
            try:
                return self._classify_with_gemini(pub)
            except Exception as e:
                logger.warning(f"Erreur lors de l'appel Gemini pour '{pub.title}': {e}. Bascule sur le classificateur heuristique.")

        # 2. Repli heuristique (sans dépendance externe ni quota)
        return self._classify_heuristically(pub)

    def _classify_with_gemini(self, pub: RawPublication) -> ClassifiedEvent:
        from google.genai import types

        prompt = f"""Analyse cette publication issue de la source '{pub.source_name}' :
TITRE : {pub.title}
DATE SOURCE : {pub.published_at or 'Inconnue'}
CONTENU COMPLET (incluant enrichissements récursifs Calaméo/PDF) :
{pub.content[:4000]}

Retourne l'objet JSON correspondant au schéma attendu.
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ClassifiedEvent,
                temperature=0.1
            )
        )

        data = json.loads(response.text)
        return ClassifiedEvent(**data)

    def _classify_heuristically(self, pub: RawPublication) -> ClassifiedEvent:
        """Classificateur de repli basé sur les règles déontologiques républicaines."""
        full_text = f"{pub.title}\n{pub.content}".lower()

        # 1. Filtre d'exclusion immédiate des faits divers et de la vie privée
        rejection_words = [
            "accident", "blessé", "blessés", "refus de priorité", "cambriolage", "cambriolages",
            "vol", "vols", "voleur", "gendarmerie appelle à la vigilance", "prison", "tribunal",
            "délit", "incendie criminel", "décès tragique", "agression", "meurtre"
        ]
        for bad_word in rejection_words:
            # Utilisation de frontières de mots entiers (\b) pour éviter les faux positifs (ex: bénévole, survoler)
            pattern = rf"\b{re.escape(bad_word)}\b"
            if re.search(pattern, full_text, re.IGNORECASE):
                return ClassifiedEvent(
                    is_public_interest=False,
                    rejection_reason=f"Fait divers individuel ou sécuritaire ({bad_word}) sans lien avec le mandat public",
                    title=pub.title,
                    summary="Information exclue du portail public.",
                    category="Non retenu",
                    badge="Exclu",
                    location="Dunières",
                    importance="low",
                    start_date=None,
                    end_date=None
                )

        # 2. Catégorisation thématique heuristique
        category = "Manifestations & Vie Associative"
        badge = "Animation"
        importance = "normal"

        if any(w in full_text for w in ["arrêté", "travaux", "circulation", "voirie", "route barrée", "déviation", "enrobé"]):
            category = "Travaux & Voirie"
            badge = "Arrêté / Travaux"
            importance = "high"
        elif any(w in full_text for w in ["conseil municipal", "délibération", "conseil communautaire", "séance", "maire"]):
            category = "Vie Municipale & Délibérations"
            badge = "Conseil Municipal"
            importance = "high"
        elif any(w in full_text for w in ["alerte", "vigilance", "coupure d'eau", "enedis", "neige", "inondation"]):
            category = "Alertes & Météo"
            badge = "Alerte Publique"
            importance = "high"
        elif any(w in full_text for w in ["médiathèque", "exposition", "cinéma", "spectacle", "musique", "concert", "théâtre"]):
            category = "Culture & Patrimoine"
            badge = "Culture"
        elif any(w in full_text for w in ["école", "cantine", "jeunesse", "ados", "centre de loisirs"]):
            category = "Enfance & Jeunesse"
            badge = "Enfance"
        elif any(w in full_text for w in ["déchets", "poubelles", "déchèterie", "france services", "permanence"]):
            category = "Services & Déchets"
            badge = "Service Public"

        # 3. Extraction de dates dans le texte ou les métadonnées
        d_start, d_end = parse_dates_from_string(f"{pub.title} {pub.content}")
        
        start_str = d_start.strftime("%Y-%m-%d") if d_start else None
        end_str = d_end.strftime("%Y-%m-%d") if d_end else None

        # Si aucune date n'est mentionnée dans le texte, utiliser la date de publication
        if not start_str and pub.published_at:
            d_pub, _ = parse_dates_from_string(pub.published_at)
            if d_pub:
                start_str = d_pub.strftime("%Y-%m-%d")

        # Résumé épuré
        first_lines = [l.strip() for l in pub.content.splitlines() if l.strip() and not l.startswith("http")]
        summary = " ".join(first_lines[:2])
        if len(summary) > 250:
            summary = summary[:247] + "..."
        if not summary:
            summary = pub.title

        return ClassifiedEvent(
            is_public_interest=True,
            rejection_reason=None,
            title=pub.title[:80],
            summary=summary,
            category=category,
            badge=badge,
            location="Dunières / Haut Pays du Velay",
            importance=importance,
            start_date=start_str,
            end_date=end_str
        )
