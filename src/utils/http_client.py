"""
Client HTTP robuste avec headers standards, timeouts et gestion d'erreurs.
"""

import logging
import urllib.request
import urllib.error
from typing import Optional, Dict

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_url(url: str, timeout: int = 15, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Effectue une requête GET HTTP(S) et renvoie le contenu texte décodé en UTF-8.
    """
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "").lower()
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            
            raw_data = response.read()
            try:
                return raw_data.decode(charset)
            except (UnicodeDecodeError, LookupError):
                return raw_data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        logger.warning(f"Erreur HTTP {e.code} lors de la requête sur {url}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Erreur réseau pour {url}: {e.reason}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la récupération de {url}: {e}")
        return None


def fetch_bytes(url: str, timeout: int = 20, max_size_bytes: int = 10 * 1024 * 1024) -> Optional[bytes]:
    """
    Télécharge des octets (ex: PDF ou image) avec contrôle de taille maximale en mémoire.
    """
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_size_bytes:
                logger.warning(f"Fichier trop lourd ({content_length} octets) sur {url}")
                return None
            
            data = response.read(max_size_bytes + 1)
            if len(data) > max_size_bytes:
                logger.warning(f"Dépassement du quota de taille ({max_size_bytes} octets) pour {url}")
                return None
            return data
    except Exception as e:
        logger.warning(f"Échec de téléchargement des octets depuis {url}: {e}")
        return None
