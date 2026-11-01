"""
Collecteur pour les stations citoyennes Illiwap (Dunières 43087 et Haut Pays du Velay).
"""

import re
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper, RawPublication
from src.utils.http_client import fetch_url

logger = logging.getLogger(__name__)

BASE_ILLIWAP_URL = "https://station.illiwap.com"


class IlliwapScraper(BaseScraper):
    """Scraper pour station.illiwap.com."""

    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        self.station_url = source_config.get("station_url")
        self.station_code = source_config.get("station_code")

    def fetch(self) -> List[RawPublication]:
        publications: List[RawPublication] = []
        if not self.station_url:
            logger.error(f"Aucune URL de station configurée pour {self.source_id}")
            return publications

        logger.info(f"Collecte Illiwap depuis {self.station_url}...")
        html = fetch_url(self.station_url)
        if not html:
            logger.warning(f"Impossible de récupérer la page de la station {self.station_url}")
            return publications

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".card")
        logger.info(f"Trouvé {len(cards)} annonces sur {self.source_name}")

        for idx, card in enumerate(cards):
            try:
                pub = self._parse_card(card, idx)
                if pub:
                    publications.append(pub)
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'une carte Illiwap: {e}")

        return publications

    def _parse_card(self, card: BeautifulSoup, index: int) -> RawPublication:
        # Recherche du lien vers le détail
        detail_link = None
        for a in card.find_all("a", href=True):
            href = a["href"]
            if "/actu/" in href or "/message/" in href:
                detail_link = urljoin(BASE_ILLIWAP_URL, href)
                break

        # Recherche de l'image de couverture
        image_url = None
        img_tag = card.find("img", src=True)
        if img_tag:
            image_url = urljoin(BASE_ILLIWAP_URL, img_tag["src"])

        # Texte préliminaire et titre
        card_text = card.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in card_text.splitlines() if line.strip()]
        title = lines[0] if lines else f"Publication Illiwap #{index+1}"

        # Recherche de la date (format JJ/MM/AAAA)
        date_str = None
        for line in lines:
            match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
            if match:
                date_str = match.group(1)
                break

        content = card_text
        external_links = []

        # Si un lien de détail existe, on approfondit l'extraction
        if detail_link:
            logger.debug(f"Approfondissement du message Illiwap: {detail_link}")
            detail_html = fetch_url(detail_link)
            if detail_html:
                detail_soup = BeautifulSoup(detail_html, "html.parser")
                
                # Titre détaillé
                h_title = detail_soup.select_one("h1, h2, .title")
                if h_title and h_title.get_text(strip=True):
                    title = h_title.get_text(strip=True)

                # Corps de l'actualité
                body_elem = detail_soup.select_one(".content, .actu-content, .card-body, article")
                if not body_elem:
                    body_elem = detail_soup

                # Extraction du texte propre
                content_lines = []
                for p in body_elem.find_all(["p", "div", "li"]):
                    txt = p.get_text(strip=True)
                    if txt and txt not in content_lines and len(txt) > 3:
                        # Exclure les menus et le pied de page générique
                        if not any(stop in txt.lower() for stop in ["votre mairie", "mentions légales", "partagez l'article", "nous contacter"]):
                            content_lines.append(txt)
                
                if content_lines:
                    content = "\n".join(content_lines)

                # Extraction des liens externes
                for a in detail_soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith("http") and "illiwap.com" not in href:
                        external_links.append(href)

        # Détection d'éventuels liens dans le texte lui-même (ex: Calaméo collé en texte brut)
        text_urls = re.findall(r"https?://[^\s<>\"']+", content)
        for u in text_urls:
            clean_u = u.rstrip(".,;)")
            if clean_u not in external_links and "illiwap.com" not in clean_u:
                external_links.append(clean_u)

        # Identifiant stable
        pub_id = detail_link.split("/")[-1] if detail_link else f"{self.station_code}_{index}"
        canonical_url = detail_link if detail_link else self.station_url

        return RawPublication(
            id=f"{self.source_id}_{pub_id}",
            source_id=self.source_id,
            source_name=self.source_name,
            title=title,
            content=content,
            url=canonical_url,
            published_at=date_str,
            image_url=image_url,
            external_links=list(dict.fromkeys(external_links)),  # Déduplication
            raw_metadata={"station_code": self.station_code}
        )
