"""
Résolveur récursif pour les publications Calaméo (agendas, plaquettes touristiques, affiches).
"""

import re
import logging
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

from src.utils.http_client import fetch_url

logger = logging.getLogger(__name__)


class CalameoResolver:
    """Extrait le contenu textuel et les métadonnées d'un livre/agenda Calaméo."""

    @staticmethod
    def extract_bkcode(url: str) -> Optional[str]:
        """Extrait l'identifiant Calaméo (bkcode) d'une URL."""
        match = re.search(r"/(?:read|books)/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        match_query = re.search(r"bkcode=([a-zA-Z0-9]+)", url)
        if match_query:
            return match_query.group(1)
        return None

    def resolve(self, url: str) -> Optional[Dict[str, Any]]:
        bkcode = self.extract_bkcode(url)
        if not bkcode:
            logger.warning(f"Impossible de trouver le code document Calaméo dans {url}")
            return None

        logger.info(f"Résolution récursive Calaméo pour le document : {bkcode}")
        
        # 1. Tentative principale via la page book publique
        book_url = f"https://www.calameo.com/books/{bkcode}"
        html = fetch_url(book_url)

        title = None
        author = None
        description = None
        cover_image = None

        if html:
            soup = BeautifulSoup(html, "html.parser")
            
            # Titre
            t_elem = soup.select_one("h1.title, .book-detail h1")
            if t_elem:
                title = t_elem.get_text(strip=True)

            # Auteur
            a_elem = soup.select_one(".name, .author")
            if a_elem:
                author = a_elem.get_text(strip=True)

            # Description complète (contient la liste des villages, dates et animations)
            d_elem = soup.select_one(".book-description .about.hidden, .book-description p")
            if d_elem:
                description = d_elem.get_text(separator="\n", strip=True)

            # Image de couverture
            img_elem = soup.select_one(".images img, .book-container img")
            if img_elem and img_elem.get("src"):
                cover_image = img_elem.get("src")
                if cover_image.startswith("//"):
                    cover_image = f"https:{cover_image}"

        # 2. Complément ou repli via la liseuse (ctx-content) si description vide
        if not description:
            viewer_url = f"https://v.calameo.com/?bkcode={bkcode}"
            v_html = fetch_url(viewer_url)
            if v_html:
                v_soup = BeautifulSoup(v_html, "html.parser")
                ctx = v_soup.select_one("#ctx-content")
                if ctx:
                    if not title:
                        h1 = ctx.find("h1")
                        title = h1.get_text(strip=True) if h1 else None
                    if not author:
                        h3 = ctx.find("h3")
                        author = h3.get_text(strip=True) if h3 else None
                    p = ctx.find("p")
                    if p:
                        description = p.get_text(separator="\n", strip=True)

        if not title and not description:
            logger.warning(f"Aucune métadonnée extraite pour Calaméo {bkcode}")
            return None

        summary_text = f"Document Calaméo '{title or 'Sans titre'}'"
        if author:
            summary_text += f" (par {author})"
        if description:
            summary_text += f" :\n{description}"

        return {
            "type": "calameo",
            "bkcode": bkcode,
            "title": title or "Agenda / Document Calaméo",
            "author": author or "Haut Pays du Velay",
            "description": description or "",
            "cover_image_url": cover_image,
            "enriched_text": summary_text,
            "original_url": url
        }
