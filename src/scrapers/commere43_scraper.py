"""
Collecteur pour La Commère 43 (presse locale Haute-Loire / Dunières / Haut Pays du Velay).
"""

import re
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url

logger = logging.getLogger(__name__)

BASE_COMMERE_URL = "https://www.lacommere43.fr"


class Commere43Scraper(BaseScraper):
    """Scraper pour La Commère 43 via recherche ciblée et flux RSS."""

    def __init__(self, source_config: Dict[str, Any], territory_keywords: List[str]):
        super().__init__(source_config)
        self.keywords = [kw.lower() for kw in territory_keywords]
        self.search_url = source_config.get("search_url")
        self.feeds = source_config.get("feeds", [])

    def fetch(self) -> List[RawPublication]:
        publications: List[RawPublication] = []
        seen_urls = set()

        # 1. Collecte via la recherche ciblée Dunières
        if self.search_url:
            logger.info(f"Recherche La Commère 43 sur : {self.search_url}")
            search_pubs = self._fetch_from_search(self.search_url)
            for pub in search_pubs:
                if pub.url not in seen_urls:
                    seen_urls.add(pub.url)
                    publications.append(pub)

        # 2. Collecte via les flux RSS thématiques (filtrage par mots-clés)
        for feed_url in self.feeds:
            try:
                logger.info(f"Analyse du flux RSS La Commère 43 : {feed_url}")
                rss_pubs = self._fetch_from_rss(feed_url)
                for pub in rss_pubs:
                    if pub.url not in seen_urls:
                        seen_urls.add(pub.url)
                        publications.append(pub)
            except Exception as e:
                logger.warning(f"Erreur sur le flux RSS {feed_url}: {e}")

        logger.info(f"Total collecté pour La Commère 43 : {len(publications)} articles")
        return publications

    def _fetch_from_search(self, url: str) -> List[RawPublication]:
        results: List[RawPublication] = []
        html = fetch_url(url)
        if not html:
            return results

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-results dt, .result-title, .searchresults dt")

        for idx, item in enumerate(items[:10]):  # Limite aux 10 plus récents
            a_tag = item.find("a", href=True)
            if not a_tag:
                continue

            link = urljoin(BASE_COMMERE_URL, a_tag["href"])
            title = a_tag.get_text(strip=True)
            
            # Recherche du paragraphe de description associé
            dd_desc = item.find_next_sibling("dd", class_="result-text")
            desc_text = dd_desc.get_text(strip=True) if dd_desc else ""
            
            # Date éventuelle
            dd_created = item.find_next_sibling("dd", class_="result-created")
            pub_date = dd_created.get_text(strip=True) if dd_created else None

            # Vérification de pertinence territoriale
            full_text = f"{title} {desc_text}".lower()
            if not any(kw in full_text for kw in self.keywords):
                continue

            results.append(
                RawPublication(
                    id=f"{self.source_id}_search_{idx}",
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    content=desc_text if desc_text else title,
                    url=link,
                    published_at=pub_date,
                    external_links=[],
                    raw_metadata={"method": "search"}
                )
            )

        return results

    def _fetch_from_rss(self, feed_url: str) -> List[RawPublication]:
        results: List[RawPublication] = []
        content = fetch_url(feed_url)
        if not content:
            return results

        try:
            root = ET.fromstring(content)
        except Exception as e:
            logger.debug(f"Impossible de parser le XML RSS : {e}")
            return results

        items = root.findall("./channel/item")
        for idx, item in enumerate(items):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            date_elem = item.find("pubDate")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
            pub_date = date_elem.text.strip() if date_elem is not None and date_elem.text else None

            # Nettoyage HTML dans la description RSS
            if "<" in desc:
                desc = BeautifulSoup(desc, "html.parser").get_text(strip=True)

            full_text = f"{title} {desc}".lower()
            # On ne conserve que ce qui concerne Dunières ou le Haut Pays du Velay
            if any(kw in full_text for kw in self.keywords):
                results.append(
                    RawPublication(
                        id=f"{self.source_id}_rss_{idx}",
                        source_id=self.source_id,
                        source_name=self.source_name,
                        title=title,
                        content=desc if desc else title,
                        url=link,
                        published_at=pub_date,
                        external_links=[],
                        raw_metadata={"method": "rss"}
                    )
                )

        return results
