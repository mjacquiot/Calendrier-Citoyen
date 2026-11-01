"""
Gestionnaire d'enrichissement récursif (Étape 2) et déduplication multi-sources.
"""

import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher

from src.scrapers.base_scraper import RawPublication
from src.enrichment.link_detector import extract_urls_from_text, classify_url
from src.enrichment.calameo_resolver import CalameoResolver
from src.enrichment.pdf_resolver import PdfResolver

logger = logging.getLogger(__name__)


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
            # 1. Rassembler toutes les URLs candidates (corps du texte + attributs)
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
                        # Compléter le texte principal avec les détails extraits du livret/agenda
                        pub.content += f"\n\n[Détails extraits de la publication Calaméo]\n{res['enriched_text']}"
                        # Compléter l'image si manquante
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
        Supprime les doublons entre sources (ex: même annonce postée sur Illiwap et la presse locale).
        Conserve en priorité la version municipale officielle (Illiwap).
        """
        unique_pubs: List[RawPublication] = []

        for candidate in publications:
            is_duplicate = False
            for existing in unique_pubs:
                # Calcul de similarité sur les titres
                ratio = SequenceMatcher(None, candidate.title.lower(), existing.title.lower()).ratio()
                if ratio >= similarity_threshold:
                    logger.info(f"Doublon détecté ({ratio:.2f}) : '{candidate.title}' similaire à '{existing.title}'")
                    is_duplicate = True
                    # Si le candidat vient d'Illiwap et l'existant d'un média tiers, on favorise la version officielle
                    if "illiwap" in candidate.source_id and "illiwap" not in existing.source_id:
                        unique_pubs.remove(existing)
                        unique_pubs.append(candidate)
                    break
            if not is_duplicate:
                unique_pubs.append(candidate)

        logger.info(f"Déduplication : {len(publications)} publications initiales ➔ {len(unique_pubs)} publications uniques.")
        return unique_pubs
