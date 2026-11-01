"""
Utilitaires de gestion des dates et de fenêtrage glissant (-15j, Aujourd'hui, +15j).
"""

import re
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

MOIS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12
}


def get_current_date() -> date:
    """Renvoie la date courante dans le fuseau horaire Europe/Paris."""
    return datetime.now(PARIS_TZ).date()


def determine_bucket(start: date, end: Optional[date] = None, ref_date: Optional[date] = None) -> str:
    """
    Détermine dans quel volet glissant classer un événement :
    - 'today' : actif aujourd'hui
    - 'retrospective' : achevé dans les 15 derniers jours [J-15, J-1]
    - 'upcoming' : prévu dans les 15 prochains jours [J+1, J+15]
    - 'extended' : au-delà de 15 jours (futur lointain)
    - 'archive' : antérieur à plus de 15 jours
    """
    if ref_date is None:
        ref_date = get_current_date()

    end_d = end if end else start

    # 1. En cours aujourd'hui
    if start <= ref_date <= end_d:
        return "today"

    # 2. Événement passé
    if end_d < ref_date:
        if ref_date - timedelta(days=15) <= end_d:
            return "retrospective"
        return "archive"

    # 3. Événement futur
    if start > ref_date:
        if start <= ref_date + timedelta(days=15):
            return "upcoming"
        return "extended"

    return "upcoming"


def parse_dates_from_string(text: str, default_year: Optional[int] = None) -> Tuple[Optional[date], Optional[date]]:
    """
    Extrait les dates de début et fin d'une chaîne en français.
    Gère les formats:
    - JJ/MM/AAAA
    - 'du JJ au JJ mois AAAA'
    - 'JJ mois AAAA'
    """
    if not text:
        return None, None

    if default_year is None:
        default_year = get_current_date().year

    # 1. Période: 'du 03 au 07 novembre 2026' ou 'du 3 au 7 novembre'
    periode_match = re.search(
        r"du\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([a-zA-Zéèû]+)(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE
    )
    if periode_match:
        d1, d2, mois_str, annee_str = periode_match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        annee = int(annee_str) if annee_str else default_year
        if mois:
            try:
                date_start = date(annee, mois, int(d1))
                date_end = date(annee, mois, int(d2))
                return date_start, date_end
            except ValueError:
                pass

    # 2. Date unique littérale: '15 novembre 2026' ou '15 novembre'
    date_lit_match = re.search(
        r"(\d{1,2})\s+([a-zA-Zéèû]+)(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE
    )
    if date_lit_match:
        d1, mois_str, annee_str = date_lit_match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        annee = int(annee_str) if annee_str else default_year
        if mois:
            try:
                d = date(annee, mois, int(d1))
                return d, None
            except ValueError:
                pass

    # 3. Format numérique JJ/MM/AAAA
    num_matches = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if num_matches:
        try:
            d_list = [date(int(m[2]), int(m[1]), int(m[0])) for m in num_matches]
            if len(d_list) >= 2:
                return min(d_list), max(d_list)
            return d_list[0], None
        except ValueError:
            pass

    return None, None
