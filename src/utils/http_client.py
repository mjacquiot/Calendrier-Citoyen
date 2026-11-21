"""
Client HTTP robuste avec session Requests, retries automatiques, timeouts et masquage des secrets.
"""

import logging
from typing import Optional, Dict, Tuple
from urllib.parse import urlsplit, urlunsplit, unquote_plus

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

SENSITIVE_QUERY_PARAMS = {
    "apikey",
    "api_key",
    "key",
    "token",
    "phone",
    "password",
    "secret",
}

_SESSION: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Retourne une session HTTP partagée configurée avec backoff et retries."""
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(DEFAULT_HEADERS)
        _SESSION = session
    return _SESSION


def sanitize_url_for_log(url: str) -> str:
    """Masque les paramètres de requête sensibles dans une URL avant journalisation."""
    if not url:
        return ""
    try:
        parts = urlsplit(str(url))
        if not parts.query:
            return str(url)
        masked_params = []
        for param in parts.query.split("&"):
            if "=" in param:
                k, _ = param.split("=", 1)
                if unquote_plus(k).strip().lower() in SENSITIVE_QUERY_PARAMS:
                    masked_params.append(f"{k}=***")
                    continue
            masked_params.append(param)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(masked_params), parts.fragment))
    except Exception:
        return "[URL masquée]"


def _decode_response_text(response: requests.Response) -> str:
    """Décode proprement le corps texte d'une réponse HTTP en respectant l'encodage déclaré."""
    content_type = (response.headers.get("content-type") or "").lower()
    charset = None
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip().strip("\"'")

    if not charset:
        charset = response.encoding or response.apparent_encoding or "utf-8"

    raw_data = response.content
    try:
        return raw_data.decode(charset)
    except (UnicodeDecodeError, LookupError):
        return raw_data.decode("utf-8", errors="replace")


def fetch_url_with_status(
    url: str,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """Effectue une requête GET HTTP(S) et renvoie `(status_code, body_text)`."""
    safe_url = sanitize_url_for_log(url)
    session = _get_session()
    try:
        response = session.get(url, timeout=timeout, headers=headers)
        status = response.status_code
        if status >= 400:
            logger.warning(f"Erreur HTTP {status} lors de la requête sur {safe_url}")
            return status, _decode_response_text(response) if response.content else None
        return status, _decode_response_text(response)
    except requests.RequestException as e:
        logger.warning(f"Erreur réseau pour {safe_url}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la récupération de {safe_url}: {e}")
        return None, None


def fetch_url(url: str, timeout: int = 15, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Effectue une requête GET HTTP(S) et renvoie le contenu texte décodé (ou None en cas d'erreur)."""
    status, text = fetch_url_with_status(url, timeout=timeout, headers=headers)
    if status is None or status >= 400:
        return None
    return text


def fetch_bytes(url: str, timeout: int = 20, max_size_bytes: int = 10 * 1024 * 1024) -> Optional[bytes]:
    """Télécharge des octets (ex: PDF ou image) en streaming avec contrôle strict de taille maximale."""
    safe_url = sanitize_url_for_log(url)
    session = _get_session()
    try:
        with session.get(url, timeout=timeout, stream=True) as response:
            if response.status_code >= 400:
                logger.warning(f"Erreur HTTP {response.status_code} lors du téléchargement de {safe_url}")
                return None

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > max_size_bytes:
                        logger.warning(f"Fichier trop lourd ({content_length} octets) sur {safe_url}")
                        return None
                except ValueError:
                    pass

            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_size_bytes:
                    logger.warning(f"Dépassement du quota de taille ({max_size_bytes} octets) pour {safe_url}")
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except requests.RequestException as e:
        logger.warning(f"Échec de téléchargement des octets depuis {safe_url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Erreur inattendue lors du téléchargement depuis {safe_url}: {e}")
        return None
