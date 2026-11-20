"""
Utilitaires de gestion des dates, horaires et de fenêtrage glissant (-7j, Aujourd'hui, +7j).
"""

import re
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

MOIS_FR = {
    "janvier": 1, "janv": 1,
    "fevrier": 2, "février": 2, "fevr": 2, "févr": 2, "fev": 2, "fév": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7, "juill": 7,
    "aout": 8, "août": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "décembre": 12, "dec": 12, "déc": 12,
}

WINDOW_DAYS = 7


def get_current_date() -> date:
    """Renvoie la date courante dans le fuseau horaire Europe/Paris."""
    return datetime.now(PARIS_TZ).date()


def determine_bucket(start: date, end: Optional[date] = None, ref_date: Optional[date] = None) -> str:
    """
    Détermine dans quel volet glissant classer un événement (fenêtre J-7 / J+7) :
    - 'today' : actif aujourd'hui (start <= ref_date <= end)
    - 'retrospective' : achevé dans les 7 derniers jours [J-7, J-1]
    - 'upcoming' : prévu dans les 7 prochains jours [J+1, J+7]
    - 'extended' : au-delà de 7 jours (futur lointain)
    - 'archive' : antérieur à plus de 7 jours
    """
    if ref_date is None:
        ref_date = get_current_date()

    end_d = end if end else start

    if start <= ref_date <= end_d:
        return "today"

    if end_d < ref_date:
        if ref_date - timedelta(days=WINDOW_DAYS) <= end_d:
            return "retrospective"
        return "archive"

    if start > ref_date:
        if start <= ref_date + timedelta(days=WINDOW_DAYS):
            return "upcoming"
        return "extended"

    return "upcoming"


def parse_dates_from_string(text: str, default_year: Optional[int] = None) -> Tuple[Optional[date], Optional[date]]:
    """
    Extrait les dates de début et fin d'une chaîne en français ou standard (ISO, RFC 2822).
    Gère les formats :
    - RFC 2822 RSS ('Thu, 19 Nov 2026 21:12:00 +0100')
    - ISO ('2026-11-20' ou '2026-11-20T15:45:00+01:00')
    - 'du JJ mois au JJ mois AAAA' / 'du JJ au JJ mois AAAA'
    - 'JJ mois AAAA' / 'JJ nov. 2026' / 'JJ novembre'
    - JJ/MM/AAAA
    """
    if not text:
        return None, None

    if default_year is None:
        default_year = get_current_date().year

    stripped = text.strip()

    # 0a. Format RFC 2822 (flux RSS) si toute la chaîne est un en-tête de date
    if re.match(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", stripped):
        try:
            dt = parsedate_to_datetime(stripped)
            return dt.date(), None
        except Exception:
            pass

    # 1a. Période inter-mois : 'du 28 novembre au 2 décembre 2026'
    inter_match = re.search(
        r"\bdu\s+(\d{1,2})\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?\s+au\s+(\d{1,2})\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if inter_match:
        d1, m1_str, d2, m2_str, annee_str = inter_match.groups()
        m1 = MOIS_FR.get(m1_str.lower())
        m2 = MOIS_FR.get(m2_str.lower())
        annee = int(annee_str) if annee_str else default_year
        if m1 and m2:
            try:
                y2 = annee + 1 if m2 < m1 and not annee_str else annee
                return date(annee, m1, int(d1)), date(y2, m2, int(d2))
            except ValueError:
                pass

    # 1b. Période même mois : 'du 03 au 07 novembre 2026' ou 'du 3 au 7 nov.'
    periode_match = re.search(
        r"\bdu\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if periode_match:
        d1, d2, mois_str, annee_str = periode_match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        annee = int(annee_str) if annee_str else default_year
        if mois:
            try:
                return date(annee, mois, int(d1)), date(annee, mois, int(d2))
            except ValueError:
                pass

    # 2. Date unique littérale : '22 nov. 2026', '15 novembre 2026', '20 novembre'
    for match in re.finditer(
        r"\b(\d{1,2})\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?\b",
        text,
        re.IGNORECASE,
    ):
        d1, mois_str, annee_str = match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        if not mois:
            continue
        annee = int(annee_str) if annee_str else default_year
        try:
            return date(annee, mois, int(d1)), None
        except ValueError:
            continue

    # 3. Format numérique JJ/MM/AAAA
    num_matches = re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if num_matches:
        valid_dates = []
        for d_s, m_s, y_s in num_matches:
            try:
                valid_dates.append(date(int(y_s), int(m_s), int(d_s)))
            except ValueError:
                continue
        if len(valid_dates) >= 2:
            return min(valid_dates), max(valid_dates)
        if len(valid_dates) == 1:
            return valid_dates[0], None

    # 4. Format ISO YYYY-MM-DD
    iso_matches = re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_matches:
        valid_dates = []
        for y_s, m_s, d_s in iso_matches:
            try:
                valid_dates.append(date(int(y_s), int(m_s), int(d_s)))
            except ValueError:
                continue
        if len(valid_dates) >= 2:
            return min(valid_dates), max(valid_dates)
        if len(valid_dates) == 1:
            return valid_dates[0], None

    return None, None


def _valid_hhmm(h_str: str, m_str: Optional[str]) -> Optional[Tuple[int, int]]:
    try:
        h = int(h_str)
        m = int(m_str) if m_str else 0
    except (TypeError, ValueError):
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return h, m
    return None


def _fmt_hhmm(h: int, m: int) -> str:
    return f"{h:02d}:{m:02d}"


def _extract_explicit_duration_minutes(text: str) -> Optional[int]:
    m = re.search(
        r"(?:dur[ée]e\s*[:\-]?\s*)(\d{1,2})\s*(?:h|heures?)\s*(\d{1,2})?",
        text,
        re.IGNORECASE,
    )
    if m:
        h = int(m.group(1))
        mins = int(m.group(2)) if m.group(2) else 0
        total = h * 60 + mins
        if 0 < total <= 720:
            return total

    m_min = re.search(r"(?:dur[ée]e\s*[:\-]?\s*)(\d{1,3})\s*min", text, re.IGNORECASE)
    if m_min:
        total = int(m_min.group(1))
        if 0 < total <= 720:
            return total

    return None


def extract_time_range(text: str) -> Dict[str, Any]:
    """
    Extrait une heure de début, une heure de fin et une durée (en minutes) depuis un texte.
    Retourne :
    {
        "start_time": "HH:MM" | None,
        "end_time": "HH:MM" | None,
        "duration_minutes": int | None,
        "all_day": bool
    }
    """
    if not text:
        return {"start_time": None, "end_time": None, "duration_minutes": None, "all_day": True}

    explicit_duration = _extract_explicit_duration_minutes(text)

    # 1. Plage explicite "18:30 - 19:30", "18h30 - 20h", "14 h - 18 h 30"
    range_direct = re.search(
        r"\b(\d{1,2})\s*(?::|h)\s*(\d{2})?\s*[-–]\s*(\d{1,2})\s*(?::|h)\s*(\d{2})?\b",
        text,
        re.IGNORECASE,
    )
    if range_direct:
        t1 = _valid_hhmm(range_direct.group(1), range_direct.group(2))
        t2 = _valid_hhmm(range_direct.group(3), range_direct.group(4))
        if t1 and t2:
            dur = (t2[0] * 60 + t2[1]) - (t1[0] * 60 + t1[1])
            return {
                "start_time": _fmt_hhmm(*t1),
                "end_time": _fmt_hhmm(*t2),
                "duration_minutes": dur if dur > 0 else explicit_duration,
                "all_day": False,
            }

    # 2. Plage en toutes lettres "de 14 heures à 19 heures", "de 9h à 12h", "entre 18 h 30 et 20 h"
    range_words = re.search(
        r"(?:de|d[eè]s|entre)\s+(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?\s*(?:à|a|et|-|–)\s*(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?\b",
        text,
        re.IGNORECASE,
    )
    if range_words:
        t1 = _valid_hhmm(range_words.group(1), range_words.group(2))
        t2 = _valid_hhmm(range_words.group(3), range_words.group(4))
        if t1 and t2:
            dur = (t2[0] * 60 + t2[1]) - (t1[0] * 60 + t1[1])
            return {
                "start_time": _fmt_hhmm(*t1),
                "end_time": _fmt_hhmm(*t2),
                "duration_minutes": dur if dur > 0 else explicit_duration,
                "all_day": False,
            }

    start_tuple: Optional[Tuple[int, int]] = None

    # 3. Format HH:MM isolé (ex: "18:30")
    if not start_tuple:
        m_colon = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if m_colon:
            start_tuple = _valid_hhmm(m_colon.group(1), m_colon.group(2))

    # 4. "à midi"
    if not start_tuple and re.search(r"\b(?:à|a|vers)\s+midi\b", text, re.IGNORECASE):
        start_tuple = (12, 0)

    # 5. "à 18 h 30", "à partir de 18 h 30", "à 14h", "dès 20h"
    if not start_tuple:
        m_trig = re.search(
            r"(?:à\s+partir\s+de|partir\s+de|d[eè]s|vers|à|a)\s+(\d{1,2})\s*(?:heures?|h)\s*(\d{2})?\b",
            text,
            re.IGNORECASE,
        )
        if m_trig:
            start_tuple = _valid_hhmm(m_trig.group(1), m_trig.group(2))

    # 6. Direct "14h", "18h30", "18 h 30"
    if not start_tuple:
        m_direct = re.search(
            r"\b(\d{1,2})\s*h\s*(\d{2})?(?=\s|$|[,.;:!?)\]])",
            text,
            re.IGNORECASE,
        )
        if m_direct:
            start_tuple = _valid_hhmm(m_direct.group(1), m_direct.group(2))

    if start_tuple:
        end_time_str: Optional[str] = None
        if explicit_duration:
            total_end = start_tuple[0] * 60 + start_tuple[1] + explicit_duration
            if total_end < 24 * 60:
                end_time_str = _fmt_hhmm(total_end // 60, total_end % 60)
        return {
            "start_time": _fmt_hhmm(*start_tuple),
            "end_time": end_time_str,
            "duration_minutes": explicit_duration,
            "all_day": False,
        }

    return {"start_time": None, "end_time": None, "duration_minutes": None, "all_day": True}
