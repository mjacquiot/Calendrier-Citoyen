"""
Collecteur pour La Commère 43 (presse locale Haute-Loire / Dunières / Haut Pays du Velay).
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url
from src.utils.text_helpers import extract_clean_html_text, normalize_text

logger = logging.getLogger(__name__)

BASE_COMMERE_URL = "https://www.lacommere43.fr"

SHARE_URL_FRAGMENTS = (
    "facebook.com/sharer",
    "linkedin.com/share",
    "twitter.com/intent",
    "x.com/intent",
    "api.whatsapp.com",
    "wa.me/",
    "mailto:",
)


def _stable_commere_id(url: str, fallback_key: str = "") -> str:
    """Construit un identifiant stable basé sur l'ID K2 de l'article ou un hash court de l'URL."""
    if url:
        m = re.search(r"/item/(\d+)(?:-|/|\.|$)", url)
        if m:
            return f"lacommere43_{m.group(1)}"
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        return f"lacommere43_{digest}"
    digest = hashlib.sha1((fallback_key or "unknown").encode("utf-8")).hexdigest()[:10]
    return f"lacommere43_{digest}"


class Commere43Scraper(BaseScraper):
    """Scraper pour La Commère 43 via recherche ciblée et flux RSS."""

    def __init__(self, source_config: Dict[str, Any], territory_keywords: List[str]):
        super().__init__(source_config)
        self.keywords = [kw.lower() for kw in territory_keywords]
        self.search_url = source_config.get("search_url")
        self.feeds = source_config.get("feeds", [])
        self.timeout = int(source_config.get("timeout", 15))
        self.recursive_crawl = bool(source_config.get("recursive_crawl", True))

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

    def _extract_body_links(self, container: Optional[BeautifulSoup]) -> List[str]:
        """Extrait les liens externes utiles (PDF, Calaméo, sites officiels) dans le corps de l'article."""
        if not self.recursive_crawl or container is None:
            return []
        links: List[str] = []
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith("http"):
                continue
            low = href.lower()
            if "lacommere43.fr" in low or any(frag in low for frag in SHARE_URL_FRAGMENTS):
                continue
            if href not in links:
                links.append(href)
        return links

    def _fetch_article_details(
        self,
        url: str,
        fallback_title: str,
        fallback_content: str,
        fallback_date: Optional[str],
    ) -> Tuple[str, str, Optional[str], Optional[str], List[str]]:
        """
        Récupère la page complète de l'article La Commère 43 (K2) pour obtenir
        le titre non tronqué, le texte complet, la date de publication, l'image et les liens externes.
        """
        title = normalize_text(fallback_title)
        content = normalize_text(fallback_content)
        pub_date = normalize_text(fallback_date) if fallback_date else None
        image_url: Optional[str] = None
        external_links: List[str] = []

        html = fetch_url(url, timeout=self.timeout)
        if not html:
            return title, content, pub_date, image_url, external_links

        soup = BeautifulSoup(html, "html.parser")

        # 1. Titre complet (K2 .itemTitle ou og:title)
        title_elem = soup.select_one(".itemTitle, h1.entry-title, h1, .page-header h2")
        if title_elem:
            cand_title = normalize_text(title_elem.get_text(separator=" ", strip=True))
            if cand_title:
                title = cand_title
        else:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                cand_title = normalize_text(og_title["content"])
                cand_title = cand_title.removesuffix(" - La Commère 43").strip()
                if cand_title:
                    title = cand_title

        # 2. Date de publication (.itemDateCreated, <time>, article:published_time)
        date_elem = soup.select_one(".itemDateCreated, time")
        if date_elem:
            dt_attr = date_elem.get("datetime")
            cand_date = normalize_text(dt_attr or date_elem.get_text(separator=" ", strip=True))
            if cand_date:
                pub_date = cand_date
        else:
            meta_pub = soup.find("meta", property="article:published_time")
            if meta_pub and meta_pub.get("content"):
                pub_date = normalize_text(meta_pub["content"])

        # 3. Corps complet (.itemIntroText + .itemFullText, sinon og:description)
        parts: List[str] = []
        intro_elem = soup.select_one(".itemIntroText")
        full_elem = soup.select_one(".itemFullText")
        if intro_elem:
            intro_txt = extract_clean_html_text(intro_elem)
            if intro_txt:
                parts.append(intro_txt)
            external_links.extend(self._extract_body_links(intro_elem))
        if full_elem:
            full_txt = extract_clean_html_text(full_elem)
            if full_txt and full_txt not in parts:
                parts.append(full_txt)
            for link in self._extract_body_links(full_elem):
                if link not in external_links:
                    external_links.append(link)

        if not parts:
            alt_body = soup.select_one("[itemprop='articleBody'], article")
            if alt_body:
                alt_txt = extract_clean_html_text(alt_body)
                if alt_txt:
                    parts.append(alt_txt)
                for link in self._extract_body_links(alt_body):
                    if link not in external_links:
                        external_links.append(link)

        if parts:
            content = normalize_text("\n\n".join(parts))
        else:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                cand_desc = normalize_text(og_desc["content"])
                if len(cand_desc) > len(content):
                    content = cand_desc

        # 4. Image de couverture
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = urljoin(BASE_COMMERE_URL, og_img["content"].strip())

        return title, content or title, pub_date, image_url, external_links

    def _fetch_from_search(self, url: str) -> List[RawPublication]:
        results: List[RawPublication] = []
        html = fetch_url(url, timeout=self.timeout)
        if not html:
            return results

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-results dt, .result-title, .searchresults dt")

        for item in items[:10]:  # Limite aux 10 plus récents
            a_tag = item.find("a", href=True)
            if not a_tag:
                continue

            link = urljoin(BASE_COMMERE_URL, a_tag["href"])
            snippet_title = normalize_text(a_tag.get_text(separator=" ", strip=True))

            dd_desc = item.find_next_sibling("dd", class_="result-text")
            snippet_desc = extract_clean_html_text(dd_desc) if dd_desc else ""

            dd_created = item.find_next_sibling("dd", class_="result-created")
            snippet_date = normalize_text(dd_created.get_text(separator=" ", strip=True)) if dd_created else None

            title, full_content, pub_date, image_url, ext_links = self._fetch_article_details(
                link,
                snippet_title,
                snippet_desc or snippet_title,
                snippet_date,
            )

            full_text = f"{title} {full_content}".lower()
            if not any(kw in full_text for kw in self.keywords):
                continue

            results.append(
                RawPublication(
                    id=_stable_commere_id(link, title),
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    content=full_content,
                    url=link,
                    published_at=pub_date,
                    image_url=image_url,
                    external_links=ext_links,
                    raw_metadata={
                        "method": "search",
                        "is_press": True,
                        "recursive_crawl": self.recursive_crawl,
                    },
                )
            )

        return results

    def _parse_rss_items(self, xml_content: str) -> List[Tuple[str, str, str, Optional[str]]]:
        """Parse un flux RSS en XML strict avec repli tolérant BeautifulSoup."""
        parsed: List[Tuple[str, str, str, Optional[str]]] = []
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
                parsed.append((raw_title, link, raw_desc, pub_date))
            return parsed
        except Exception as e:
            logger.debug(f"Parsing XML strict impossible ({e}), bascule BeautifulSoup.")

        soup = BeautifulSoup(xml_content, "html.parser")
        for item in soup.find_all("item"):
            t = item.find("title")
            l = item.find("link")
            d = item.find("description")
            p = item.find("pubdate")
            raw_title = t.get_text(strip=True) if t else ""
            link = l.get_text(strip=True) if l else ""
            raw_desc = d.get_text(strip=True) if d else ""
            pub_date = p.get_text(strip=True) if p else None
            parsed.append((raw_title, link, raw_desc, pub_date))
        return parsed

    def _fetch_from_rss(self, feed_url: str) -> List[RawPublication]:
        results: List[RawPublication] = []
        content = fetch_url(feed_url, timeout=self.timeout)
        if not content:
            return results

        items = self._parse_rss_items(content)
        for raw_title, link, raw_desc, pub_date in items:
            title = normalize_text(raw_title)
            if "<" in raw_desc:
                desc = extract_clean_html_text(BeautifulSoup(raw_desc, "html.parser"))
            else:
                desc = normalize_text(raw_desc)

            full_text = f"{title} {desc}".lower()
            if not any(kw in full_text for kw in self.keywords):
                continue

            image_url: Optional[str] = None
            ext_links: List[str] = []
            if link:
                title, desc, resolved_date, image_url, ext_links = self._fetch_article_details(
                    link, title, desc or title, pub_date
                )
                if resolved_date:
                    pub_date = resolved_date

            results.append(
                RawPublication(
                    id=_stable_commere_id(link, title),
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    content=desc if desc else title,
                    url=link,
                    published_at=pub_date,
                    image_url=image_url,
                    external_links=ext_links,
                    raw_metadata={
                        "method": "rss",
                        "is_press": True,
                        "recursive_crawl": self.recursive_crawl,
                    },
                )
            )

        return results
