"""
Collecteur pour les stations citoyennes Illiwap (Dunières 43087 et Haut Pays du Velay).
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url
from src.utils.text_helpers import extract_clean_html_text, normalize_text

logger = logging.getLogger(__name__)

BASE_ILLIWAP_URL = "https://station.illiwap.com"

DATE_PREFIX_RE = re.compile(
    r"^\d{1,2}\s+[a-zA-Zéèêëàâäîïôöùûüç.]+\s+\d{4}(?:\s+\d{1,2}[:h]\d{2}(?:\s*-\s*\d{1,2}[:h]\d{2})?)?$",
    re.IGNORECASE,
)
NOISE_LINES = {
    "lire la suite",
    "voir plus",
    "votre mairie",
    "mentions légales",
    "partagez l'article",
    "nous contacter",
}
SHARE_URL_FRAGMENTS = (
    "facebook.com/sharer",
    "linkedin.com/share",
    "twitter.com/intent",
    "x.com/intent",
    "api.whatsapp.com",
    "wa.me/",
)


class IlliwapScraper(BaseScraper):
    """Scraper pour station.illiwap.com."""

    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        self.station_url = source_config.get("station_url")
        self.station_code = source_config.get("station_code")
        self.timeout = int(source_config.get("timeout", 15))
        self.recursive_crawl = bool(source_config.get("recursive_crawl", True))

    def fetch(self) -> List[RawPublication]:
        publications: List[RawPublication] = []
        if not self.station_url:
            logger.error(f"Aucune URL de station configurée pour {self.source_id}")
            return publications

        logger.info(f"Collecte Illiwap depuis {self.station_url}...")
        html = fetch_url(self.station_url, timeout=self.timeout)
        if not html:
            logger.warning(f"Impossible de récupérer la page de la station {self.station_url}")
            return publications

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".card")
        logger.info(f"Trouvé {len(cards)} annonces sur {self.source_name}")

        seen_detail_links: Set[str] = set()
        for idx, card in enumerate(cards):
            try:
                pub = self._parse_card(card, idx, seen_detail_links)
                if pub:
                    publications.append(pub)
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'une carte Illiwap: {e}")

        return publications

    def _extract_card_title(self, lines: List[str], index: int) -> str:
        """Extrait un titre propre depuis les lignes de la carte sans utiliser la date en titre."""
        candidates = [
            line for line in lines
            if line and line.lower() not in NOISE_LINES and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", line)
        ]
        if not candidates:
            return f"Publication Illiwap #{index + 1}"

        # Si la première ligne est une date/heure d'événement (ex: "22 nov. 2026 16:00 - 17:00"),
        # prendre la ligne suivante comme titre réel.
        if DATE_PREFIX_RE.match(candidates[0]) and len(candidates) > 1:
            return candidates[1]
        return candidates[0]

    def _parse_card(
        self,
        card: BeautifulSoup,
        index: int,
        seen_detail_links: Set[str],
    ) -> Optional[RawPublication]:
        # Recherche du lien vers le détail (/actu/, /message/, /evenements/)
        detail_link: Optional[str] = None
        for a in card.find_all("a", href=True):
            href = a["href"]
            if "/actu/" in href or "/message/" in href or "/evenements/" in href:
                detail_link = urljoin(BASE_ILLIWAP_URL, href)
                break

        if detail_link:
            if detail_link in seen_detail_links:
                logger.debug(f"Carte Illiwap déjà traitée : {detail_link}")
                return None
            seen_detail_links.add(detail_link)

        # Recherche de l'image de couverture
        image_url: Optional[str] = None
        img_tag = card.find("img", src=True)
        if img_tag:
            image_url = urljoin(BASE_ILLIWAP_URL, img_tag["src"])

        # Texte préliminaire nettoyé et titre de repli
        card_text = extract_clean_html_text(card)
        lines = [line.strip() for line in card_text.splitlines() if line.strip()]
        title = self._extract_card_title(lines, index)

        # Recherche de la date (format JJ/MM/AAAA) sur la carte
        date_str: Optional[str] = None
        for line in lines:
            match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
            if match:
                date_str = match.group(1)
                break

        content = card_text
        external_links: List[str] = []

        # Approfondissement sur la page de détail si disponible
        if detail_link:
            logger.debug(f"Approfondissement du message Illiwap: {detail_link}")
            detail_html = fetch_url(detail_link, timeout=self.timeout)
            if detail_html:
                detail_soup = BeautifulSoup(detail_html, "html.parser")

                # Titre principal de l'article/événement (éviter les h2 de la barre latérale)
                h_title = detail_soup.select_one("article header h1, article h1, main h1, h1")
                if h_title:
                    parsed_title = normalize_text(h_title.get_text(separator=" ", strip=True))
                    if parsed_title and not DATE_PREFIX_RE.match(parsed_title):
                        title = parsed_title

                # Date de publication si absente sur la carte
                if not date_str:
                    time_elem = detail_soup.select_one("article header time, article time")
                    if time_elem:
                        dt_attr = time_elem.get("datetime", "")
                        if dt_attr:
                            date_str = dt_attr.split("T")[0]
                        else:
                            date_str = normalize_text(time_elem.get_text(separator=" ", strip=True))

                # Corps réel de l'actualité ou de l'événement
                body_elem = detail_soup.select_one(
                    "#contenu-alerte, #contenu-evenement, article .content, article .actu-content, article .card-body, article"
                )
                if body_elem:
                    clean_body = extract_clean_html_text(body_elem)
                    filtered_lines = [
                        l for l in clean_body.splitlines()
                        if l.strip() and not any(stop in l.lower() for stop in NOISE_LINES)
                    ]
                    if filtered_lines:
                        content = normalize_text("\n".join(filtered_lines))

                # Image de repli si absente sur la carte
                if not image_url:
                    detail_img = detail_soup.select_one("article img[src], main img[src*='uploads']")
                    if detail_img and detail_img.get("src"):
                        image_url = urljoin(BASE_ILLIWAP_URL, detail_img["src"])

                # Extraction des liens externes dans le contenu (hors boutons de partage)
                link_scope = body_elem or detail_soup.select_one("article, main") or detail_soup
                for a in link_scope.find_all("a", href=True):
                    href = a["href"].strip()
                    if (
                        href.startswith("http")
                        and "illiwap.com" not in href
                        and not any(frag in href.lower() for frag in SHARE_URL_FRAGMENTS)
                    ):
                        external_links.append(href)

        # Détection d'éventuels liens collés en texte brut dans le contenu nettoyé
        text_urls = re.findall(r"https?://[^\s<>\"']+", content)
        for u in text_urls:
            clean_u = u.rstrip(".,;)\"']")
            if (
                clean_u not in external_links
                and "illiwap.com" not in clean_u
                and not any(frag in clean_u.lower() for frag in SHARE_URL_FRAGMENTS)
            ):
                external_links.append(clean_u)

        # Identifiant stable
        if detail_link:
            slug = detail_link.rstrip("/").split("/")[-1]
            pub_id = f"ev_{slug}" if "/evenements/" in detail_link else slug
        else:
            pub_id = f"{self.station_code}_{index}"

        canonical_url = detail_link if detail_link else self.station_url

        return RawPublication(
            id=f"{self.source_id}_{pub_id}",
            source_id=self.source_id,
            source_name=self.source_name,
            title=normalize_text(title),
            content=normalize_text(content),
            url=canonical_url,
            published_at=date_str,
            image_url=image_url,
            external_links=list(dict.fromkeys(external_links)),
            raw_metadata={
                "station_code": self.station_code,
                "is_press": False,
                "recursive_crawl": self.recursive_crawl,
            },
        )
