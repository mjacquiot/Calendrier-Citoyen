"""
Collecteur pour Le Progrès (Haute-Loire / Dunières et communes du Haut Pays du Velay).
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url

logger = logging.getLogger(__name__)


class LeProgresScraper(BaseScraper):
    """Scraper pour les flux RSS de Le Progrès (Haute-Loire)."""

    def __init__(self, source_config: Dict[str, Any], territory_keywords: List[str]):
        super().__init__(source_config)
        self.feed_url = source_config.get("feed_url")
        self.keywords = [kw.lower() for kw in territory_keywords]

    def fetch(self) -> List[RawPublication]:
        publications: List[RawPublication] = []
        if not self.feed_url:
            logger.warning("Aucun feed_url configuré pour Le Progrès")
            return publications

        logger.info(f"Collecte Le Progrès via flux RSS : {self.feed_url}")
        content = fetch_url(self.feed_url)
        if not content:
            return publications

        try:
            root = ET.fromstring(content)
        except Exception as e:
            logger.error(f"Erreur lors du parsing XML Le Progrès: {e}")
            return publications

        items = root.findall("./channel/item")
        logger.info(f"Le Progrès Haute-Loire : {len(items)} articles dans le flux")

        for idx, item in enumerate(items):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            date_elem = item.find("pubDate")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
            pub_date = date_elem.text.strip() if date_elem is not None and date_elem.text else None

            # Nettoyage HTML de la description
            if "<" in desc:
                desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)

            full_text = f"{title} {desc}".lower()

            # Filtrer pour ne retenir que ce qui concerne Dunières ou les communes membres
            if any(kw in full_text for kw in self.keywords):
                logger.info(f"Article Le Progrès retenu pour le territoire : {title}")
                publications.append(
                    RawPublication(
                        id=f"{self.source_id}_{idx}",
                        source_id=self.source_id,
                        source_name=self.source_name,
                        title=title,
                        content=desc if desc else title,
                        url=link,
                        published_at=pub_date,
                        external_links=[],
                        raw_metadata={"source": "leprogres_rss"}
                    )
                )

        return publications
