"""
Utilitaires de gestion des dates, horaires multiples et fenêtrage glissant (-7j, Aujourd'hui, +7j).
"""

import os
import re
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple, Dict, Any, List
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


def _env_window_days(var_name: str, default: int = 7) -> int:
    raw = os.getenv(var_name)
    if not raw:
        return default
    try:
        val = int(raw.strip())
        return val if val >= 1 else default
    except ValueError:
        return default


WINDOW_DAYS = 7
WINDOW_PAST_DAYS = _env_window_days("SLIDING_WINDOW_PAST_DAYS", WINDOW_DAYS)
WINDOW_FUTURE_DAYS = _env_window_days("SLIDING_WINDOW_FUTURE_DAYS", WINDOW_DAYS)

_STREET_PREFIX_RE = re.compile(
    r"\b(?:rue|avenue|av\.?|place|pl\.?|boulevard|bd\.?|all[ée]es?|impasse|cours|square|chemin|lotissement)\s+"
    r"(?:du|de\s+la|de\s+l['’]|des|d['’])?\s*$",
    re.IGNORECASE,
)

_PUB_META_TIME_RE = re.compile(
    r"(?:publi[ée]|mis\s+à\s+jour|modifi[ée]|actualis[ée])"
    r"(?:\s+(?:le\s+)?[^\n,:]{1,40})?\s+(?:à|a)\s+\d{1,2}\s*[:h]\s*\d{0,2}\b",
    re.IGNORECASE,
)

_DURATION_PHRASE_RE = re.compile(
    r"(?:dur[ée]e\s*[:\-]?\s*)\d{1,3}\s*(?:h(?:eures?)?(?:\s*\d{1,2})?|min(?:utes?)?)\b",
    re.IGNORECASE,
)

_INSCRIPTION_END_TIME_RE = re.compile(
    r"(?:fin\s+des\s+inscriptions?|cl[ôo]ture\s+des\s+inscriptions?)\s+(?:à|a)\s+\d{1,2}\s*[:h]\s*\d{0,2}\b",
    re.IGNORECASE,
)


def get_current_date() -> date:
    """Renvoie la date courante dans le fuseau horaire Europe/Paris."""
    return datetime.now(PARIS_TZ).date()


def determine_bucket(
    start: date,
    end: Optional[date] = None,
    ref_date: Optional[date] = None,
    past_days: Optional[int] = None,
    future_days: Optional[int] = None,
) -> str:
    """
    Détermine dans quel volet glissant classer un événement (fenêtre J-7 / J+7 par défaut) :
    - 'today' : actif aujourd'hui (start <= ref_date <= end)
    - 'retrospective' : achevé dans les `past_days` derniers jours [J-past, J-1]
    - 'upcoming' : prévu dans les `future_days` prochains jours [J+1, J+future]
    - 'extended' : au-delà de `future_days` jours (futur lointain)
    - 'archive' : antérieur à plus de `past_days` jours
    """
    if ref_date is None:
        ref_date = get_current_date()

    p_days = WINDOW_PAST_DAYS if past_days is None else past_days
    f_days = WINDOW_FUTURE_DAYS if future_days is None else future_days

    end_d = end if (end is not None and end >= start) else start

    if start <= ref_date <= end_d:
        return "today"

    if end_d < ref_date:
        if ref_date - timedelta(days=p_days) <= end_d:
            return "retrospective"
        return "archive"

    if start > ref_date:
        if start <= ref_date + timedelta(days=f_days):
            return "upcoming"
        return "extended"

    return "upcoming"


def _is_street_context(text: str, match_start: int) -> bool:
    """Vérifie si la date capturée appartient à un odonyme (ex: 'Rue du 19-Mars-1962')."""
    prefix = text[max(0, match_start - 40):match_start]
    return bool(_STREET_PREFIX_RE.search(prefix))


def _resolve_year_for_month_day(
    day: int,
    month: int,
    annee_str: Optional[str],
    base_year: int,
    ref: date,
    allow_rollover: bool,
) -> Optional[date]:
    if annee_str:
        year = int(annee_str)
        if year < base_year - 1:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None

    try:
        cand = date(base_year, month, day)
    except ValueError:
        return None

    if allow_rollover:
        delta = (cand - ref).days
        if delta < -180:
            try:
                return date(base_year + 1, month, day)
            except ValueError:
                return cand
        if delta > 180:
            try:
                return date(base_year - 1, month, day)
            except ValueError:
                return cand

    return cand


def parse_dates_from_string(
    text: str,
    default_year: Optional[int] = None,
    ref_date: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date]]:
    """
    Extrait les dates de début et fin d'une chaîne en français ou standard (ISO, RFC 2822).
    Gère les ordinaux ('1er décembre'), les changements d'année, les plages explicites et
    ignore les odonymes ('Rue du 19 mars 1962') ou années historiques anciennes.
    """
    if not text:
        return None, None

    ref = ref_date if ref_date is not None else get_current_date()
    base_year = default_year if default_year is not None else ref.year
    allow_rollover = (ref_date is not None) or (default_year is None) or (default_year == ref.year)

    stripped = text.strip()

    # 0a. Format RFC 2822 (flux RSS) si la chaîne commence par un en-tête de date
    if re.match(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", stripped):
        try:
            dt = parsedate_to_datetime(stripped)
            return dt.date(), None
        except Exception:
            pass

    # 1a. Période inter-mois : 'du 28 novembre au 2 décembre 2026' ou 'du 28 déc au 1er janv'
    for inter_match in re.finditer(
        r"\bdu\s+(\d{1,2})(?:\s*(?:er|ᵉʳ))?\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?\s+"
        r"au\s+(\d{1,2})(?:\s*(?:er|ᵉʳ))?\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    ):
        if _is_street_context(text, inter_match.start()):
            continue
        d1, m1_str, d2, m2_str, annee_str = inter_match.groups()
        m1 = MOIS_FR.get(m1_str.lower())
        m2 = MOIS_FR.get(m2_str.lower())
        if not (m1 and m2):
            continue
        start_d = _resolve_year_for_month_day(int(d1), m1, annee_str, base_year, ref, allow_rollover)
        if not start_d:
            continue
        if annee_str:
            end_y = int(annee_str) + (1 if m2 < m1 else 0)
            try:
                end_d = date(end_y, m2, int(d2))
            except ValueError:
                end_d = None
        else:
            end_y = start_d.year + (1 if m2 < m1 else 0)
            try:
                end_d = date(end_y, m2, int(d2))
            except ValueError:
                end_d = None
        if end_d and end_d >= start_d:
            return start_d, end_d
        return start_d, None

    # 1b. Période même mois : 'du 1er au 7 décembre 2026' ou 'du 3 au 7 nov.'
    for periode_match in re.finditer(
        r"\bdu\s+(\d{1,2})(?:\s*(?:er|ᵉʳ))?\s+au\s+(\d{1,2})(?:\s*(?:er|ᵉʳ))?\s+"
        r"([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    ):
        if _is_street_context(text, periode_match.start()):
            continue
        d1, d2, mois_str, annee_str = periode_match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        if not mois:
            continue
        start_d = _resolve_year_for_month_day(int(d1), mois, annee_str, base_year, ref, allow_rollover)
        if not start_d:
            continue
        try:
            end_d = date(start_d.year, mois, int(d2))
            if end_d >= start_d:
                return start_d, end_d
        except ValueError:
            pass
        return start_d, None

    # 2. Date unique littérale : '1er décembre 2026', '22 nov. 2026', '15 janvier'
    for match in re.finditer(
        r"\b(\d{1,2})(?:\s*(?:er|ᵉʳ))?\s+([a-zA-Zéèêëàâäîïôöùûüç]+)\.?(?:\s+(\d{4}))?\b",
        text,
        re.IGNORECASE,
    ):
        if _is_street_context(text, match.start()):
            continue
        d1, mois_str, annee_str = match.groups()
        mois = MOIS_FR.get(mois_str.lower())
        if not mois:
            continue
        resolved = _resolve_year_for_month_day(int(d1), mois, annee_str, base_year, ref, allow_rollover)
        if resolved:
            return resolved, None

    # 3a. Période numérique explicite : 'du JJ/MM/AAAA au JJ/MM/AAAA' ou 'JJ/MM/AAAA - JJ/MM/AAAA'
    num_range = re.search(
        r"(?:\bdu\s+)?(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:au|[-–])\s*(\d{1,2})/(\d{1,2})/(\d{4})\b",
        text,
        re.IGNORECASE,
    )
    if num_range and not _is_street_context(text, num_range.start()):
        d1, m1, y1, d2, m2, y2 = [int(x) for x in num_range.groups()]
        if y1 >= base_year - 1 and y2 >= base_year - 1:
            try:
                sd, ed = date(y1, m1, d1), date(y2, m2, d2)
                if ed >= sd:
                    return sd, ed
            except ValueError:
                pass

    # 3b. Date numérique isolée JJ/MM/AAAA
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
        if _is_street_context(text, m.start()):
            continue
        d_s, m_s, y_s = m.groups()
        if int(y_s) < base_year - 1:
            continue
        try:
            return date(int(y_s), int(m_s), int(d_s)), None
        except ValueError:
            continue

    # 4a. Période ISO explicite : 'du YYYY-MM-DD au YYYY-MM-DD' ou 'YYYY-MM-DD - YYYY-MM-DD'
    iso_range = re.search(
        r"(?:\bdu\s+)?(\d{4})-(\d{2})-(\d{2})\s+(?:au|[-–])\s+(\d{4})-(\d{2})-(\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if iso_range:
        y1, m1, d1, y2, m2, d2 = [int(x) for x in iso_range.groups()]
        if y1 >= base_year - 1 and y2 >= base_year - 1:
            try:
                sd, ed = date(y1, m1, d1), date(y2, m2, d2)
                if ed >= sd:
                    return sd, ed
            except ValueError:
                pass

    # 4b. Date ISO isolée YYYY-MM-DD
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        y_s, m_s, d_s = m.groups()
        if int(y_s) < base_year - 1:
            continue
        try:
            return date(int(y_s), int(m_s), int(d_s)), None
        except ValueError:
            continue

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


def _overlaps(span: Tuple[int, int], occupied: List[Tuple[int, int]]) -> bool:
    s, e = span
    return any(not (e <= os_ or s >= oe_) for os_, oe_ in occupied)


def extract_all_time_ranges(text: str) -> List[Dict[str, Any]]:
    """
    Extrait tous les créneaux horaires distincts présents dans un texte, triés chronologiquement.
    Ignore les métadonnées de publication ('publié à 15:45') et les durées explicites ('Durée : 1h').
    """
    if not text:
        return []

    explicit_duration = _extract_explicit_duration_minutes(text)

    # Neutraliser métadonnées de publication, durées et fins d'inscription sans décaler les index utiles
    cleaned = _PUB_META_TIME_RE.sub(lambda m: " " * len(m.group(0)), text)
    cleaned = _DURATION_PHRASE_RE.sub(lambda m: " " * len(m.group(0)), cleaned)
    cleaned = _INSCRIPTION_END_TIME_RE.sub(lambda m: " " * len(m.group(0)), cleaned)

    found: List[Tuple[int, str, Optional[str], Optional[int]]] = []
    occupied: List[Tuple[int, int]] = []

    # 1. Plages explicites "18:30 - 19:30", "18h30 - 20h", "14 h - 18 h 30"
    for m in re.finditer(
        r"\b(\d{1,2})\s*(?::|h)\s*(\d{2})?\s*[-–]\s*(\d{1,2})\s*(?::|h)\s*(\d{2})?\b",
        cleaned,
        re.IGNORECASE,
    ):
        if _overlaps(m.span(), occupied):
            continue
        t1 = _valid_hhmm(m.group(1), m.group(2))
        t2 = _valid_hhmm(m.group(3), m.group(4))
        if t1 and t2:
            dur = (t2[0] * 60 + t2[1]) - (t1[0] * 60 + t1[1])
            found.append((
                t1[0] * 60 + t1[1],
                _fmt_hhmm(*t1),
                _fmt_hhmm(*t2),
                dur if dur > 0 else explicit_duration,
            ))
            occupied.append(m.span())

    # 2. Plages en toutes lettres "de 13h à 19h", "de 20h30 à 22h", "entre 18 h 30 et 20 h"
    for m in re.finditer(
        r"(?:de|d[eè]s|entre)\s+(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?\s*"
        r"(?:à|a|et|-|–)\s*(\d{1,2})\s*(?:heures?|h|:)\s*(\d{2})?(?=\s|$|[,.;:!?)\]])",
        cleaned,
        re.IGNORECASE,
    ):
        if _overlaps(m.span(), occupied):
            continue
        t1 = _valid_hhmm(m.group(1), m.group(2))
        t2 = _valid_hhmm(m.group(3), m.group(4))
        if t1 and t2:
            dur = (t2[0] * 60 + t2[1]) - (t1[0] * 60 + t1[1])
            found.append((
                t1[0] * 60 + t1[1],
                _fmt_hhmm(*t1),
                _fmt_hhmm(*t2),
                dur if dur > 0 else explicit_duration,
            ))
            occupied.append(m.span())

    # 3. Format HH:MM isolé
    for m in re.finditer(r"\b(\d{1,2}):(\d{2})\b", cleaned):
        if _overlaps(m.span(), occupied):
            continue
        t1 = _valid_hhmm(m.group(1), m.group(2))
        if t1:
            end_str = None
            if explicit_duration and not found:
                total_end = t1[0] * 60 + t1[1] + explicit_duration
                if total_end < 24 * 60:
                    end_str = _fmt_hhmm(total_end // 60, total_end % 60)
            found.append((t1[0] * 60 + t1[1], _fmt_hhmm(*t1), end_str, explicit_duration if not found else None))
            occupied.append(m.span())

    # 4. "à midi"
    for m in re.finditer(r"\b(?:à|a|vers)\s+midi\b", cleaned, re.IGNORECASE):
        if _overlaps(m.span(), occupied):
            continue
        found.append((12 * 60, "12:00", None, explicit_duration if not found else None))
        occupied.append(m.span())

    # 5. "à 18 h 30", "à partir de 18 h 30", "à 14h", "dès 20h"
    for m in re.finditer(
        r"(?:à\s+partir\s+de|partir\s+de|d[eè]s|vers|à|a)\s+(\d{1,2})\s*(?:heures?|h)\s*(\d{2})?\b",
        cleaned,
        re.IGNORECASE,
    ):
        if _overlaps(m.span(), occupied):
            continue
        t1 = _valid_hhmm(m.group(1), m.group(2))
        if t1:
            end_str = None
            if explicit_duration and not found:
                total_end = t1[0] * 60 + t1[1] + explicit_duration
                if total_end < 24 * 60:
                    end_str = _fmt_hhmm(total_end // 60, total_end % 60)
            found.append((t1[0] * 60 + t1[1], _fmt_hhmm(*t1), end_str, explicit_duration if not found else None))
            occupied.append(m.span())

    # 6. Direct "14h", "18h30", "18 h 30"
    for m in re.finditer(
        r"\b(\d{1,2})\s*h\s*(\d{2})?(?=\s|$|[,.;:!?)\]])",
        cleaned,
        re.IGNORECASE,
    ):
        if _overlaps(m.span(), occupied):
            continue
        t1 = _valid_hhmm(m.group(1), m.group(2))
        if t1:
            end_str = None
            if explicit_duration and not found:
                total_end = t1[0] * 60 + t1[1] + explicit_duration
                if total_end < 24 * 60:
                    end_str = _fmt_hhmm(total_end // 60, total_end % 60)
            found.append((t1[0] * 60 + t1[1], _fmt_hhmm(*t1), end_str, explicit_duration if not found else None))
            occupied.append(m.span())

    if not found:
        return []

    found.sort(key=lambda item: (item[0], item[2] or "99:99"))

    deduped: List[Dict[str, Any]] = []
    seen_keys = set()
    for _, st, et, dur in found:
        key = (st, et)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append({
            "start_time": st,
            "end_time": et,
            "duration_minutes": dur,
            "all_day": False,
        })

    # Si un unique créneau possède explicit_duration sans end_time, compléter end_time
    if len(deduped) == 1 and deduped[0]["end_time"] is None and explicit_duration:
        hh, mm = [int(x) for x in deduped[0]["start_time"].split(":")]
        total_end = hh * 60 + mm + explicit_duration
        if total_end < 24 * 60:
            deduped[0]["end_time"] = _fmt_hhmm(total_end // 60, total_end % 60)
        deduped[0]["duration_minutes"] = explicit_duration

    return deduped


def extract_time_range(text: str) -> Dict[str, Any]:
    """
    Extrait le créneau horaire principal (et la liste complète 'slots' le cas échéant) depuis un texte.
    Retourne :
    {
        "start_time": "HH:MM" | None,
        "end_time": "HH:MM" | None,
        "duration_minutes": int | None,
        "all_day": bool,
        "slots": List[Dict[str, Any]]
    }
    """
    slots = extract_all_time_ranges(text)
    if not slots:
        return {"start_time": None, "end_time": None, "duration_minutes": None, "all_day": True, "slots": []}

    primary = slots[0]
    return {
        "start_time": primary["start_time"],
        "end_time": primary["end_time"],
        "duration_minutes": primary["duration_minutes"],
        "all_day": False,
        "slots": slots,
    }
