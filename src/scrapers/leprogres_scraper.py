"""
Collecteur pour Le Progrès (Haute-Loire / Dunières et communes du Haut Pays du Velay).
"""

import hashlib
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url
from src.utils.text_helpers import extract_clean_html_text, normalize_text

logger = logging.getLogger(__name__)


def _stable_progres_id(source_id: str, link: str, title: str) -> str:
    key = link.strip() or title.strip() or "unknown"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{source_id}_{digest}"


class LeProgresScraper(BaseScraper):
    """Scraper pour les flux RSS de Le Progrès (Haute-Loire)."""

    def __init__(self, source_config: Dict[str, Any], territory_keywords: List[str]):
        super().__init__(source_config)
        self.feed_url = source_config.get("feed_url")
        self.keywords = [kw.lower() for kw in territory_keywords]
        self.timeout = int(source_config.get("timeout", 15))
        self.recursive_crawl = bool(source_config.get("recursive_crawl", True))

    def _parse_rss_items(self, xml_content: str) -> List[Tuple[str, str, str, Optional[str], Optional[str]]]:
        """Parse le flux RSS XML avec repli BeautifulSoup et extraction d'image enclosure/media."""
        parsed: List[Tuple[str, str, str, Optional[str], Optional[str]]] = []
        try:
            root = ET.fromstring(xml_content)
            for item in root.findall("./channel/item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                date_elem = item.find("pubDate")

                raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                raw_desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                pub_date = date_elem.text.strip() if date_elem is not None and date_elem.text else None

                image_url: Optional[str] = None
                enc = item.find("enclosure")
                if enc is not None and enc.get("url"):
                    image_url = enc.get("url")
                if not image_url:
                    for child in item:
                        if child.tag.lower().endswith("content") and child.get("url"):
                            image_url = child.get("url")
                            break

                parsed.append((raw_title, link, raw_desc, pub_date, image_url))
            return parsed
        except Exception as e:
            logger.debug(f"Parsing XML Le Progrès échoué ({e}), repli BeautifulSoup.")

        soup = BeautifulSoup(xml_content, "html.parser")
        for item in soup.find_all("item"):
            t = item.find("title")
            l = item.find("link")
            d = item.find("description")
            p = item.find("pubdate")
            enc = item.find("enclosure")
            media = item.find("media:content")
            image_url = None
            if enc and enc.get("url"):
                image_url = enc["url"]
            elif media and media.get("url"):
                image_url = media["url"]
            parsed.append((
                t.get_text(strip=True) if t else "",
                l.get_text(strip=True) if l else "",
                d.get_text(strip=True) if d else "",
                p.get_text(strip=True) if p else None,
                image_url,
            ))
        return parsed

    def fetch(self) -> List[RawPublication]:
        publications: List[RawPublication] = []
        if not self.feed_url:
            logger.warning("Aucun feed_url configuré pour Le Progrès")
            return publications

        logger.info(f"Collecte Le Progrès via flux RSS : {self.feed_url}")
        content = fetch_url(self.feed_url, timeout=self.timeout)
        if not content:
            return publications

        items = self._parse_rss_items(content)
        logger.info(f"Le Progrès Haute-Loire : {len(items)} articles dans le flux")

        for raw_title, link, raw_desc, pub_date, image_url in items:
            title = normalize_text(raw_title)

            # Nettoyage HTML de la description
            if "<" in raw_desc:
                desc = extract_clean_html_text(BeautifulSoup(raw_desc, "html.parser"))
            else:
                desc = normalize_text(raw_desc)

            full_text = f"{title} {desc}".lower()

            # Filtrer pour ne retenir que ce qui concerne Dunières ou les communes membres
            if any(kw in full_text for kw in self.keywords):
                logger.info(f"Article Le Progrès retenu pour le territoire : {title}")
                publications.append(
                    RawPublication(
                        id=_stable_progres_id(self.source_id, link, title),
                        source_id=self.source_id,
                        source_name=self.source_name,
                        title=title,
                        content=desc if desc else title,
                        url=link,
                        published_at=pub_date,
                        image_url=image_url,
                        external_links=[],
                        raw_metadata={
                            "source": "leprogres_rss",
                            "is_press": True,
                            "recursive_crawl": self.recursive_crawl,
                        },
                    )
                )

        return publications
