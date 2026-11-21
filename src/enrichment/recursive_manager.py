"""
Gestionnaire d'enrichissement récursif (Étape 2) et déduplication multi-sources sensible aux dates.
"""

import re
import logging
import unicodedata
from datetime import date
from typing import List, Tuple, Dict, Any, Optional
from difflib import SequenceMatcher

from src.scrapers.base_scraper import RawPublication
from src.enrichment.link_detector import extract_urls_from_text, classify_url
from src.enrichment.calameo_resolver import CalameoResolver
from src.enrichment.pdf_resolver import PdfResolver
from src.utils.date_helpers import parse_dates_from_string, get_current_date
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
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pub_priority_score(pub: RawPublication) -> Tuple[int, int, int, int]:
    """Score de priorité pour retenir la version la plus fiable et complète d'un doublon."""
    is_official = 1 if ("illiwap" in pub.source_id or "manual" in pub.source_id) else 0
    is_dunieres = 1 if pub.source_id in ("illiwap_dunieres", "manual_mairie") else 0
    has_enrichment = 1 if pub.enrichment else 0
    return (is_official, has_enrichment, len(pub.content or ""), is_dunieres)


def _extract_pub_date(pub: RawPublication) -> Optional[date]:
    ref = get_current_date()
    d, _ = parse_dates_from_string(f"{pub.title}\n{pub.content[:600]}", default_year=ref.year, ref_date=ref)
    if d:
        return d
    if pub.published_at:
        d_pub, _ = parse_dates_from_string(pub.published_at, default_year=ref.year, ref_date=ref)
        return d_pub
    return None


class RecursiveEnrichmentManager:
    """Coordonne la résolution en 2 étapes (liens externes) et la fusion des données."""

    def __init__(self, max_pdf_size_mb: int = 10, timeout: int = 15):
        self.calameo_resolver = CalameoResolver(timeout=timeout)
        self.pdf_resolver = PdfResolver(max_size_mb=max_pdf_size_mb, timeout=max(timeout, 20))
        self._url_cache: Dict[str, Any] = {}

    def _resolve_calameo_cached(self, url: str) -> Optional[Dict[str, Any]]:
        if url not in self._url_cache:
            self._url_cache[url] = self.calameo_resolver.resolve(url)
        return self._url_cache[url]

    def _resolve_pdf_cached(self, url: str) -> Optional[Dict[str, Any]]:
        if url not in self._url_cache:
            self._url_cache[url] = self.pdf_resolver.resolve(url)
        return self._url_cache[url]

    def enrich_publications(self, publications: List[RawPublication]) -> List[RawPublication]:
        """
        Parcourt toutes les publications brutes, détecte les liens profonds
        (Calaméo, arrêtés PDF) et enrichit le texte pour l'étape IA suivante.
        """
        logger.info(f"Début de l'enrichissement récursif sur {len(publications)} publications...")
        enriched_count = 0

        for pub in publications:
            if not pub.raw_metadata.get("recursive_crawl", True):
                continue

            found_urls = list(pub.external_links)
            found_urls.extend(extract_urls_from_text(pub.content))
            all_urls = list(dict.fromkeys(found_urls))

            if not all_urls:
                continue

            for url in all_urls:
                link_type = classify_url(url)

                if link_type == "calameo" and "calameo" not in pub.enrichment:
                    res = self._resolve_calameo_cached(url)
                    if res:
                        pub.enrichment["calameo"] = res
                        enriched_count += 1
                        pub.content += f"\n\n[Détails extraits de la publication Calaméo]\n{res['enriched_text']}"
                        if not pub.image_url and res.get("cover_image_url"):
                            pub.image_url = res["cover_image_url"]

                elif link_type == "pdf" and "pdf" not in pub.enrichment:
                    res = self._resolve_pdf_cached(url)
                    if res:
                        pub.enrichment["pdf"] = res
                        enriched_count += 1
                        pub.content += f"\n\n[Contenu extrait du document PDF joint]\n{res['extracted_text']}"

        logger.info(f"Enrichissement terminé : {enriched_count} liens externes résolus.")
        return publications

    def deduplicate(self, publications: List[RawPublication], similarity_threshold: float = 0.85) -> List[RawPublication]:
        """
        Supprime les doublons entre sources ou entre onglets Illiwap (/actu/ vs /evenements/),
        tout en préservant les occurrences distinctes d'événements récurrents à des dates différentes.
        """
        unique_pubs: List[RawPublication] = []
        norm_titles: List[str] = []
        sorted_titles: List[str] = []
        pub_dates: List[Optional[date]] = []

        for candidate in publications:
            cand_norm = _normalize_title_for_dedup(candidate.title)
            cand_sorted = " ".join(sorted(cand_norm.split()))
            cand_date = _extract_pub_date(candidate)
            cand_content = normalize_text(candidate.content).lower()
            matched_idx = -1

            for idx, existing in enumerate(unique_pubs):
                # Même URL canonique explicite => doublon exact
                if candidate.url and existing.url and candidate.url == existing.url:
                    matched_idx = idx
                    break

                existing_norm = norm_titles[idx]
                if not cand_norm or not existing_norm:
                    continue

                ratio = SequenceMatcher(None, cand_norm, existing_norm).ratio()
                sorted_ratio = SequenceMatcher(None, cand_sorted, sorted_titles[idx]).ratio()
                shorter, longer = (
                    (cand_norm, existing_norm)
                    if len(cand_norm) <= len(existing_norm)
                    else (existing_norm, cand_norm)
                )
                is_contained = len(shorter) >= 15 and shorter in longer

                existing_date = pub_dates[idx]
                same_date_same_body = (
                    cand_date is not None
                    and existing_date is not None
                    and cand_date == existing_date
                    and len(cand_content) >= 50
                    and cand_content[:120] == normalize_text(existing.content).lower()[:120]
                )

                if not (ratio >= similarity_threshold or sorted_ratio >= 0.88 or is_contained or same_date_same_body):
                    continue

                # Préserver les événements récurrents espacés de plus d'un jour sur des URLs différentes
                if (
                    cand_date is not None
                    and existing_date is not None
                    and abs((cand_date - existing_date).days) > 1
                    and candidate.url != existing.url
                ):
                    continue

                matched_idx = idx
                break

            if matched_idx == -1:
                unique_pubs.append(candidate)
                norm_titles.append(cand_norm)
                sorted_titles.append(cand_sorted)
                pub_dates.append(cand_date)
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
            if loser.external_links:
                winner.external_links = list(dict.fromkeys([*winner.external_links, *loser.external_links]))
            if not winner.published_at and loser.published_at:
                winner.published_at = loser.published_at

            unique_pubs[matched_idx] = winner
            winner_norm = _normalize_title_for_dedup(winner.title)
            norm_titles[matched_idx] = winner_norm
            sorted_titles[matched_idx] = " ".join(sorted(winner_norm.split()))
            pub_dates[matched_idx] = _extract_pub_date(winner)

        logger.info(f"Déduplication : {len(publications)} publications initiales ➔ {len(unique_pubs)} publications uniques.")
        return unique_pubs
