"""
Utilitaires de normalisation et nettoyage des textes extraits depuis HTML / RSS.
"""

import html
import re
from bs4 import BeautifulSoup, Tag


_LEADING_DECORATIVE_EMOJI_RE = re.compile(
    r"^[\s\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f\u200d•\-–—|:]+"
)


def normalize_text(text: str) -> str:
    """
    Nettoie une chaîne de texte issue d'un scraping HTML ou RSS :
    - Décode les entités HTML (&amp;, &#039;, &nbsp;, etc.)
    - Remplace les espaces insécables et caractères invisibles
    - Supprime les artefacts Cloudflare de masquage d'email ([email protected])
    - Sépare proprement les URLs collées au texte adjacent
    - Corrige les espaces superflus avant virgule/point ou après élision française
    - Préserve les sauts de paragraphe propres
    """
    if not text:
        return ""

    cleaned = html.unescape(str(text))
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")
    cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")

    # Supprimer les libellés email orphelins + artefacts Cloudflare [email protected]
    cleaned = re.sub(
        r"(?:^|\n)[ \t]*(?:e?-?mail|courriel)\s*[:\-]?\s*\[email\s*protected\][ \t]*(?=\n|$)",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\[email\s*protected\]", "", cleaned, flags=re.IGNORECASE)

    # Séparer une URL collée immédiatement après un caractère (ex: ":https://...")
    cleaned = re.sub(r"([^\s(\[\"\'])(https?://)", r"\1 \2", cleaned)

    # Corriger les espaces parasites produits par get_text(separator=" ") devant . ou ,
    cleaned = re.sub(r"[ \t]+([.,])(?=\s|$)", r"\1", cleaned)

    # Corriger les espaces parasites après apostrophe d'élision française (l' Ehpad -> l'Ehpad)
    cleaned = re.sub(
        r"\b(c|d|j|l|m|n|s|t|qu|jusqu|lorsqu|puisqu|presqu|quelqu|aujourd)(['’])[ \t]+([A-Za-zÀ-ÿ0-9])",
        r"\1\2\3",
        cleaned,
        flags=re.IGNORECASE,
    )

    lines = []
    for raw_line in cleaned.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def clean_event_title(title: str) -> str:
    """
    Nettoie un titre d'événement pour l'affichage public :
    - Normalise le texte
    - Supprime les emojis décoratifs et ponctuations isolées en début de titre
    - Met une majuscule initiale si le titre commence par une minuscule brute
    """
    cleaned = normalize_text(title)
    if not cleaned:
        return ""

    stripped = _LEADING_DECORATIVE_EMOJI_RE.sub("", cleaned).strip()
    if stripped:
        cleaned = stripped

    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def extract_clean_html_text(soup_elem) -> str:
    """
    Extrait un texte lisible et structuré depuis un fragment HTML BeautifulSoup
    sans jamais coller deux mots autour de balises inline ou <br>.
    """
    if soup_elem is None:
        return ""

    # Travailler sur une copie isolée pour ne pas altérer l'arbre appelant
    fragment = BeautifulSoup(str(soup_elem), "html.parser")

    for unwanted in fragment.find_all(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        unwanted.decompose()

    for br in fragment.find_all("br"):
        br.replace_with("\n")

    block_tags = ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "section")
    for tag in fragment.find_all(block_tags):
        if isinstance(tag, Tag):
            tag.insert_before("\n")
            tag.insert_after("\n")

    raw_text = fragment.get_text(separator=" ")
    return normalize_text(raw_text)


def smart_truncate(text: str, max_len: int = 240) -> str:
    """
    Tronque un texte proprement sans jamais couper un mot en deux.
    Privilégie une fin de phrase si possible, sinon le dernier espace avant max_len.
    """
    cleaned = normalize_text(text)
    if not cleaned or len(cleaned) <= max_len:
        return cleaned

    if max_len <= 1:
        return "…"

    candidate = cleaned[: max_len - 1]

    # Chercher une fin de phrase convenable dans les derniers 40%
    min_sentence_idx = int((max_len - 1) * 0.6)
    best_sentence_end = -1
    for sep in (". ", "! ", "? "):
        idx = candidate.rfind(sep)
        if idx >= min_sentence_idx and idx > best_sentence_end:
            best_sentence_end = idx

    if best_sentence_end != -1:
        return candidate[: best_sentence_end + 1].strip()

    last_space = candidate.rfind(" ")
    if last_space > 0:
        return candidate[:last_space].rstrip(" ,;:-") + "…"

    return candidate.rstrip() + "…"
