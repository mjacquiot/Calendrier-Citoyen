"""
Détecteur et classificateur d'URLs pour la résolution récursive.
"""

import re
from typing import List, Dict
from urllib.parse import urlparse


def extract_urls_from_text(text: str) -> List[str]:
    """Extrait toutes les URLs valides présentes dans un texte."""
    if not text:
        return []
    raw_urls = re.findall(r"https?://[^\s<>\"']+", text)
    cleaned = []
    for u in raw_urls:
        clean_u = u.rstrip(".,;)\"']")
        if clean_u.startswith("http") and clean_u not in cleaned:
            cleaned.append(clean_u)
    return cleaned


def classify_url(url: str) -> str:
    """
    Détermine le type de lien pour aiguiller vers le bon résolveur :
    - 'calameo' : publication ou liseuse Calaméo
    - 'pdf' : arrêté ou document PDF
    - 'image' : affiche ou photo
    - 'generic' : lien web classique
    """
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    path = parsed.path

    if "calameo.com" in domain:
        return "calameo"
    if path.endswith(".pdf") or "download=pdf" in parsed.query:
        return "pdf"
    if any(path.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return "image"
    return "generic"


def categorize_links(urls: List[str]) -> Dict[str, List[str]]:
    """Groupe une liste d'URLs par catégorie."""
    categorized: Dict[str, List[str]] = {
        "calameo": [],
        "pdf": [],
        "image": [],
        "generic": []
    }
    for u in urls:
        cat = classify_url(u)
        categorized[cat].append(u)
    return categorized
