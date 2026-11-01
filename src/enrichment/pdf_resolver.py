"""
Résolveur récursif pour les documents PDF (arrêtés municipaux, délibérations, programmes).
"""

import io
import re
import logging
from typing import Optional, Dict, Any
from pypdf import PdfReader

from src.utils.http_client import fetch_bytes

logger = logging.getLogger(__name__)


class PdfResolver:
    """Télécharge et extrait le texte intégral de fichiers PDF distants."""

    def __init__(self, max_pages: int = 15, max_size_mb: int = 10):
        self.max_pages = max_pages
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def resolve(self, url: str) -> Optional[Dict[str, Any]]:
        logger.info(f"Résolution récursive PDF pour : {url}")
        pdf_data = fetch_bytes(url, max_size_bytes=self.max_size_bytes)
        if not pdf_data:
            logger.warning(f"Échec de récupération des données PDF depuis {url}")
            return None

        try:
            reader = PdfReader(io.BytesIO(pdf_data))
            total_pages = len(reader.pages)
            pages_to_read = min(total_pages, self.max_pages)

            extracted_chunks = []
            for page_idx in range(pages_to_read):
                page = reader.pages[page_idx]
                text = page.extract_text()
                if text:
                    # Nettoyer les espaces superflus
                    clean_text = re.sub(r"\s+", " ", text).strip()
                    if clean_text:
                        extracted_chunks.append(f"[Page {page_idx+1}] {clean_text}")

            if not extracted_chunks:
                logger.warning(f"PDF extrait vide (ou uniquement image scannée) pour {url}")
                return None

            full_text = "\n".join(extracted_chunks)
            logger.info(f"PDF extrait avec succès ({total_pages} pages, {len(full_text)} caractères)")

            # Recherche d'indices spécifiques aux arrêtés municipaux
            is_arrete = any(w in full_text.lower() for w in ["arrêté", "considérant", "article 1", "maire de dunières"])

            return {
                "type": "pdf",
                "pages_count": total_pages,
                "is_arrete": is_arrete,
                "extracted_text": full_text,
                "summary_snippet": full_text[:400] + "...",
                "original_url": url
            }
        except Exception as e:
            logger.error(f"Erreur lors du décodage du PDF {url}: {e}")
            return None
