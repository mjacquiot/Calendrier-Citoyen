"""
Gestionnaire d'enrichissement récursif (Étape 2) et déduplication multi-sources.
"""

import re
import logging
import unicodedata
from typing import List, Tuple
from difflib import SequenceMatcher

from src.scrapers.base_scraper import RawPublication
from src.enrichment.link_detector import extract_urls_from_text, classify_url
from src.enrichment.calameo_resolver import CalameoResolver
from src.enrichment.pdf_resolver import PdfResolver
from src.utils.text_helpers import normalize_text

logger = logging.getLogger(__name__)


def _normalize_title_for_dedup(title: str) -> str:
    """Normalise un titre pour comparer efficacement les doublons inter-sources."""
    if not title:
        return ""
    text = normalize_text(title).lower()
    # Retirer un éventuel préfixe date/heure (ex: "22 nov. 2026 16:00 - 17:00 ...")
    text = re.sub(
        r"^\d{1,2}\s+[a-zà-ÿ.]+\s+\d{4}(?:\s+\d{1,2}[:h]\d{2}(?:\s*-\s*\d{1,2}[:h]\d{2})?)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Supprimer les accents
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    # Ne conserver que lettres, chiffres et espaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pub_priority_score(pub: RawPublication) -> Tuple[int, int, int, int]:
    """Score de priorité pour retenir la version la plus fiable et complète d'un doublon."""
    is_illiwap = 1 if "illiwap" in pub.source_id else 0
    is_dunieres = 1 if pub.source_id == "illiwap_dunieres" else 0
    has_enrichment = 1 if pub.enrichment else 0
    return (is_illiwap, has_enrichment, len(pub.content or ""), is_dunieres)


class RecursiveEnrichmentManager:
    """Coordonne la résolution en 2 étapes (liens externes) et la fusion des données."""

    def __init__(self, max_pdf_size_mb: int = 10):
        self.calameo_resolver = CalameoResolver()
        self.pdf_resolver = PdfResolver(max_size_mb=max_pdf_size_mb)

    def enrich_publications(self, publications: List[RawPublication]) -> List[RawPublication]:
        """
        Parcourt toutes les publications brutes, détecte les liens profonds
        (Calaméo, arrêtés PDF) et enrichit le texte pour l'étape IA suivante.
        """
        logger.info(f"Début de l'enrichissement récursif sur {len(publications)} publications...")
        enriched_count = 0

        for pub in publications:
            found_urls = list(pub.external_links)
            found_urls.extend(extract_urls_from_text(pub.content))
            all_urls = list(dict.fromkeys(found_urls))

            if not all_urls:
                continue

            for url in all_urls:
                link_type = classify_url(url)

                # Résolution Calaméo
                if link_type == "calameo" and "calameo" not in pub.enrichment:
                    res = self.calameo_resolver.resolve(url)
                    if res:
                        pub.enrichment["calameo"] = res
                        enriched_count += 1
                        pub.content += f"\n\n[Détails extraits de la publication Calaméo]\n{res['enriched_text']}"
                        if not pub.image_url and res.get("cover_image_url"):
                            pub.image_url = res["cover_image_url"]

                # Résolution PDF
                elif link_type == "pdf" and "pdf" not in pub.enrichment:
                    res = self.pdf_resolver.resolve(url)
                    if res:
                        pub.enrichment["pdf"] = res
                        enriched_count += 1
                        pub.content += f"\n\n[Contenu extrait du document PDF joint]\n{res['extracted_text']}"

        logger.info(f"Enrichissement terminé : {enriched_count} liens externes résolus.")
        return publications

    def deduplicate(self, publications: List[RawPublication], similarity_threshold: float = 0.85) -> List[RawPublication]:
        """
        Supprime les doublons entre sources ou entre onglets Illiwap (/actu/ vs /evenements/).
        Conserve en priorité la version officielle la plus riche et fusionne image/pièces jointes.
        """
        unique_pubs: List[RawPublication] = []
        norm_titles: List[str] = []

        for candidate in publications:
            cand_norm = _normalize_title_for_dedup(candidate.title)
            matched_idx = -1

            for idx, existing_norm in enumerate(norm_titles):
                if not cand_norm or not existing_norm:
                    continue
                ratio = SequenceMatcher(None, cand_norm, existing_norm).ratio()
                shorter, longer = (
                    (cand_norm, existing_norm)
                    if len(cand_norm) <= len(existing_norm)
                    else (existing_norm, cand_norm)
                )
                is_contained = len(shorter) >= 15 and shorter in longer
                if ratio >= similarity_threshold or is_contained:
                    matched_idx = idx
                    break

            if matched_idx == -1:
                unique_pubs.append(candidate)
                norm_titles.append(cand_norm)
                continue

            existing = unique_pubs[matched_idx]
            logger.info(f"Doublon détecté : '{candidate.title}' similaire à '{existing.title}'")

            if _pub_priority_score(candidate) > _pub_priority_score(existing):
                winner, loser = candidate, existing
            else:
                winner, loser = existing, candidate

            if not winner.image_url and loser.image_url:
                winner.image_url = loser.image_url
            if not winner.enrichment and loser.enrichment:
                winner.enrichment = loser.enrichment
            if not winner.published_at and loser.published_at:
                winner.published_at = loser.published_at

            unique_pubs[matched_idx] = winner
            norm_titles[matched_idx] = _normalize_title_for_dedup(winner.title)

        logger.info(f"Déduplication : {len(publications)} publications initiales ➔ {len(unique_pubs)} publications uniques.")
        return unique_pubs
