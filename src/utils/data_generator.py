"""
Générateur des fichiers structurés web/data.json (schéma v2) et web/calendar.ics (RFC 5545)
pour le calendrier glissant en 3 volets (J-7 / Aujourd'hui / J+7).
"""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.ai.classifier import GeminiClassifier
from src.ai.schemas import ClassifiedEvent
from src.enrichment.recursive_manager import _normalize_title_for_dedup
from src.scrapers.base_scraper import RawPublication
from src.utils.date_helpers import (
    PARIS_TZ,
    WINDOW_FUTURE_DAYS,
    WINDOW_PAST_DAYS,
    determine_bucket,
    extract_time_range,
    get_current_date,
    parse_dates_from_string,
)
from src.utils.text_helpers import clean_event_title, normalize_text, smart_truncate

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


def _parse_hhmm_minutes(hhmm: Optional[str]) -> Optional[int]:
    if not hhmm:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", hhmm.strip())
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mins <= 59:
        return h * 60 + mins
    return None


def _parse_slot_str(slot_str: str) -> Optional[Dict[str, Any]]:
    m = re.fullmatch(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", (slot_str or "").strip())
    if not m:
        return None
    s_m = _parse_hhmm_minutes(m.group(1))
    e_m = _parse_hhmm_minutes(m.group(2))
    if s_m is None or e_m is None or e_m <= s_m:
        return None
    return {
        "start_time": f"{s_m // 60:02d}:{s_m % 60:02d}",
        "end_time": f"{e_m // 60:02d}:{e_m % 60:02d}",
        "duration_minutes": e_m - s_m,
    }


def _build_timing(event: ClassifiedEvent, pub: RawPublication) -> Dict[str, Any]:
    """Assemble l'objet timing normalisé (incluant créneaux multiples si présents)."""
    fallback = extract_time_range(f"{normalize_text(pub.title)}\n{normalize_text(pub.content)}")

    start_min = _parse_hhmm_minutes(event.start_time)
    end_min = _parse_hhmm_minutes(event.end_time)

    # Ne pas réinjecter les horaires d'un encart secondaire d'article de presse si l'IA a déjà tranché
    is_press = bool(pub.raw_metadata.get("is_press"))
    start_time = (
        f"{start_min // 60:02d}:{start_min % 60:02d}"
        if start_min is not None
        else (None if is_press and event.start_time is None else fallback["start_time"])
    )
    end_time = (
        f"{end_min // 60:02d}:{end_min % 60:02d}"
        if end_min is not None
        else (None if is_press and event.end_time is None else fallback["end_time"])
    )

    s_m = _parse_hhmm_minutes(start_time)
    e_m = _parse_hhmm_minutes(end_time)
    duration_minutes: Optional[int] = None
    if s_m is not None and e_m is not None and e_m > s_m:
        duration_minutes = e_m - s_m
    elif not is_press and fallback.get("duration_minutes") and start_time == fallback.get("start_time"):
        duration_minutes = fallback["duration_minutes"]

    # Construction de la liste multi-créneaux uniquement si > 1 créneau
    slots: List[Dict[str, Any]] = []
    if start_time is not None:
        primary_slot = {
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
        }
        extra_slots: List[Dict[str, Any]] = []
        for raw_slot in event.additional_slots or []:
            parsed_slot = _parse_slot_str(raw_slot)
            if parsed_slot and parsed_slot["start_time"] != start_time:
                extra_slots.append(parsed_slot)

        if not extra_slots and not is_press and len(fallback.get("slots", [])) > 1:
            for fb_slot in fallback["slots"][1:]:
                if fb_slot.get("start_time") and fb_slot["start_time"] != start_time:
                    extra_slots.append({
                        "start_time": fb_slot["start_time"],
                        "end_time": fb_slot.get("end_time"),
                        "duration_minutes": fb_slot.get("duration_minutes"),
                    })

        if extra_slots:
            slots = [primary_slot, *extra_slots]

    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": duration_minutes,
        "all_day": start_time is None,
        "slots": slots,
    }


def _escape_ics_text(value: str) -> str:
    if not value:
        return ""
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )
    return escaped


def _fold_ics_line(line: str) -> str:
    """Plie une ligne ICS à 75 octets UTF-8 maximum selon la RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    chunks: List[str] = []
    current = ""
    current_bytes = 0
    limit = 75
    for ch in line:
        ch_bytes = len(ch.encode("utf-8"))
        if current_bytes + ch_bytes > limit:
            chunks.append(current)
            current = " " + ch
            current_bytes = 1 + ch_bytes
        else:
            current += ch
            current_bytes += ch_bytes
    if current:
        chunks.append(current)
    return "\r\n".join(chunks)


def build_ics_calendar(events: List[Dict[str, Any]], generated_at_iso: Optional[str] = None) -> str:
    """Génère un flux iCalendar (.ics) RFC 5545 complet pour tous les événements fournis."""
    try:
        dt_gen = datetime.fromisoformat(generated_at_iso) if generated_at_iso else datetime.now(PARIS_TZ)
    except ValueError:
        dt_gen = datetime.now(PARIS_TZ)
    dtstamp = (
        dt_gen.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if dt_gen.tzinfo
        else dt_gen.strftime("%Y%m%dT%H%M%SZ")
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Commune de Dunieres//Calendrier Citoyen//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Calendrier Citoyen de Dunières",
        "X-WR-TIMEZONE:Europe/Paris",
    ]

    for ev in events:
        dates_obj = ev.get("dates") or {}
        start_iso = dates_obj.get("start")
        if not start_iso:
            continue
        try:
            start_d = date.fromisoformat(start_iso)
        except ValueError:
            continue

        end_iso = dates_obj.get("end") or start_iso
        try:
            end_d = date.fromisoformat(end_iso)
            if end_d < start_d:
                end_d = start_d
        except ValueError:
            end_d = start_d

        timing = ev.get("timing") or {}
        slots = timing.get("slots") or []
        if not slots and timing.get("start_time"):
            slots = [{
                "start_time": timing.get("start_time"),
                "end_time": timing.get("end_time"),
                "duration_minutes": timing.get("duration_minutes"),
            }]

        summary = _escape_ics_text(ev.get("title") or "Événement Dunières")
        desc_parts = [ev.get("summary") or ""]
        if ev.get("price"):
            desc_parts.append(f"Tarif : {ev['price']}")
        if ev.get("source_url"):
            desc_parts.append(f"Source : {ev['source_url']}")
        description = _escape_ics_text("\n\n".join(p for p in desc_parts if p))
        location = _escape_ics_text(ev.get("location") or "Dunières")
        category = _escape_ics_text(ev.get("category") or "")
        source_url = ev.get("source_url") or ""

        if slots:
            for slot_idx, slot in enumerate(slots):
                s_min = _parse_hhmm_minutes(slot.get("start_time"))
                if s_min is None:
                    continue
                e_min = _parse_hhmm_minutes(slot.get("end_time"))
                if e_min is None or e_min <= s_min:
                    dur = slot.get("duration_minutes") or 90
                    e_min = s_min + int(dur)

                start_dt = datetime(start_d.year, start_d.month, start_d.day) + timedelta(minutes=s_min)
                end_dt = datetime(start_d.year, start_d.month, start_d.day) + timedelta(minutes=e_min)
                uid_suffix = f"-{slot_idx}" if len(slots) > 1 else ""
                uid = f"{ev.get('id', 'evt')}{uid_suffix}@calendrier-dunieres.local"

                lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{dtstamp}",
                    f"DTSTART;TZID=Europe/Paris:{start_dt.strftime('%Y%m%dT%H%M%S')}",
                    f"DTEND;TZID=Europe/Paris:{end_dt.strftime('%Y%m%dT%H%M%S')}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    f"LOCATION:{location}",
                ])
                if category:
                    lines.append(f"CATEGORIES:{category}")
                if source_url:
                    lines.append(f"URL:{source_url}")
                lines.append("END:VEVENT")
        else:
            dt_end_exclusive = end_d + timedelta(days=1)
            uid = f"{ev.get('id', 'evt')}@calendrier-dunieres.local"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;VALUE=DATE:{start_d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{dt_end_exclusive.strftime('%Y%m%d')}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{location}",
            ])
            if category:
                lines.append(f"CATEGORIES:{category}")
            if source_url:
                lines.append(f"URL:{source_url}")
            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    folded = [_fold_ics_line(ln) for ln in lines]
    return "\r\n".join(folded) + "\r\n"


class DataGenerator:
    """Transforme les publications classifiées en structure de données pour le portail web."""

    def __init__(
        self,
        output_path: str = "web/data.json",
        ics_output_path: Optional[str] = None,
        classifier: Optional[GeminiClassifier] = None,
        past_days: int = WINDOW_PAST_DAYS,
        future_days: int = WINDOW_FUTURE_DAYS,
    ):
        self.output_path = Path(output_path)
        self.ics_output_path = Path(ics_output_path) if ics_output_path else (self.output_path.parent / "calendar.ics")
        self.classifier = classifier or GeminiClassifier()
        self.past_days = past_days
        self.future_days = future_days

    def _load_previous_v2_events(self) -> List[Dict[str, Any]]:
        """Charge les événements d'un précédent data.json uniquement s'il est au schéma v2."""
        if not self.output_path.exists():
            return []
        try:
            with open(self.output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return []
            if data.get("metadata", {}).get("schema_version") != SCHEMA_VERSION:
                logger.info("Ancien data.json antérieur au schéma v2 ignoré lors de la migration.")
                return []
            events = data.get("all_events", [])
            return events if isinstance(events, list) else []
        except Exception as e:
            logger.warning(f"Impossible de relire l'ancien {self.output_path} : {e}")
            return []

    def process_and_export(
        self,
        publications: List[RawPublication],
        ref_date: Optional[date] = None,
        sources_health: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Traite la liste des publications, applique le tri déontologique,
        applique les garde-fous anti-écrasement & droit d'auteur presse,
        calcule les 3 volets temporels et génère web/data.json (v2) + web/calendar.ics.
        """
        if ref_date is None:
            ref_date = get_current_date()

        logger.info(
            f"Traitement IA et fenêtrage glissant J-{self.past_days}/J+{self.future_days} "
            f"(Date de référence : {ref_date})..."
        )

        previous_events = self._load_previous_v2_events()
        accepted_events: List[Dict[str, Any]] = []
        rejected_count = 0
        out_of_window_count = 0
        preserved_count = 0

        analyzed_ids: Set[str] = set()
        seen_ids: Set[str] = set()
        seen_title_dates: Set[Tuple[str, str]] = set()

        for pub in publications:
            analyzed_ids.add(pub.id)
            event: ClassifiedEvent = self.classifier.classify(pub, ref_date=ref_date)

            if not event.is_public_interest:
                logger.info(f"[REJET DÉONTOLOGIQUE] '{pub.title}' -> {event.rejection_reason}")
                rejected_count += 1
                continue

            d_start = None
            d_end = None
            if event.start_date:
                try:
                    d_start = date.fromisoformat(event.start_date)
                except ValueError:
                    pass
            if event.end_date:
                try:
                    d_end = date.fromisoformat(event.end_date)
                except ValueError:
                    pass

            if not d_start:
                d_start, d_end_fb = parse_dates_from_string(
                    f"{pub.title}\n{pub.published_at or ''}",
                    default_year=ref_date.year,
                    ref_date=ref_date,
                )
                if not d_end and d_end_fb:
                    d_end = d_end_fb

            if not d_start:
                logger.info(f"[SANS DATE - IGNORÉ] '{event.title}' (aucune date exploitable)")
                out_of_window_count += 1
                continue

            if d_end and d_end < d_start:
                d_end = None

            bucket = determine_bucket(
                d_start,
                d_end,
                ref_date=ref_date,
                past_days=self.past_days,
                future_days=self.future_days,
            )
            if bucket not in ("retrospective", "today", "upcoming"):
                logger.info(f"[HORS FENÊTRE {bucket}] '{event.title}' ({d_start})")
                out_of_window_count += 1
                continue

            is_period = bool(d_end and d_end != d_start)
            timing = _build_timing(event, pub)
            is_press = bool(pub.raw_metadata.get("is_press"))
            title_clean = clean_event_title(event.title) or normalize_text(event.title)
            summary_clean = smart_truncate(event.summary, 280) if is_press else normalize_text(event.summary)
            full_content = None if is_press else normalize_text(pub.content)

            attachment_type = list(pub.enrichment.keys())[0] if pub.enrichment else None
            attachment_data = pub.enrichment.get("calameo") or pub.enrichment.get("pdf")

            item = {
                "id": pub.id,
                "title": title_clean,
                "summary": summary_clean,
                "full_content": full_content,
                "is_press_excerpt": is_press,
                "content_type": event.content_type,
                "category": event.category,
                "badge": event.badge,
                "price": normalize_text(event.price) if event.price else None,
                "source_id": pub.source_id,
                "source_name": pub.source_name,
                "source_url": pub.url,
                "image_url": pub.image_url,
                "dates": {
                    "start": d_start.isoformat(),
                    "end": d_end.isoformat() if d_end else None,
                    "is_period": is_period,
                    "bucket": bucket,
                },
                "timing": timing,
                "location": normalize_text(event.location) or "Dunières / Haut Pays du Velay",
                "importance": event.importance,
                "has_attachment": bool(pub.enrichment),
                "attachment_type": attachment_type,
                "attachment_data": attachment_data,
            }

            accepted_events.append(item)
            seen_ids.add(pub.id)
            seen_title_dates.add((_normalize_title_for_dedup(title_clean), d_start.isoformat()))

        # Persistance incrémentale & garde-fou anti-écrasement
        degraded_mode = False
        if len(publications) == 0 and previous_events:
            degraded_mode = True
            logger.warning(
                "Aucune publication collectée lors de ce run : préservation de l'existant encore dans la fenêtre."
            )

        for prev in previous_events:
            prev_id = prev.get("id")
            if not prev_id or prev_id in seen_ids or prev_id in analyzed_ids:
                continue

            dates_obj = prev.get("dates") or {}
            start_s = dates_obj.get("start")
            if not start_s:
                continue
            try:
                p_start = date.fromisoformat(start_s)
                p_end = date.fromisoformat(dates_obj["end"]) if dates_obj.get("end") else None
            except ValueError:
                continue

            p_bucket = determine_bucket(
                p_start,
                p_end,
                ref_date=ref_date,
                past_days=self.past_days,
                future_days=self.future_days,
            )
            if p_bucket not in ("retrospective", "today", "upcoming"):
                continue

            title_key = (_normalize_title_for_dedup(prev.get("title", "")), start_s)
            if title_key in seen_title_dates:
                continue

            preserved = dict(prev)
            preserved["dates"] = {
                **dates_obj,
                "bucket": p_bucket,
            }
            accepted_events.append(preserved)
            seen_ids.add(prev_id)
            seen_title_dates.add(title_key)
            preserved_count += 1

        # Persister le cache Gemini
        if hasattr(self.classifier, "save_cache"):
            self.classifier.save_cache()

        def _sort_key(ev: Dict[str, Any]):
            return (ev["dates"]["start"], ev["timing"].get("start_time") or "99:99")

        accepted_events.sort(key=_sort_key)

        buckets: Dict[str, List[str]] = {
            "retrospective": [],
            "today": [],
            "upcoming": [],
        }
        high_importance_today = 0
        for ev in accepted_events:
            b_name = ev["dates"]["bucket"]
            if b_name in buckets:
                buckets[b_name].append(ev["id"])
            if b_name == "today" and (
                ev.get("importance") == "high"
                or ev.get("category") in ("Alertes & Météo", "Travaux & Voirie")
            ):
                high_importance_today += 1

        generated_at_iso = datetime.now(PARIS_TZ).isoformat()
        classifier_stats = dict(getattr(self.classifier, "stats", {}))

        final_payload = {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "commune": "Dunières",
                "code_postal": "43220",
                "intercommunalite": "Haut Pays du Velay Communauté",
                "generated_at": generated_at_iso,
                "reference_date": ref_date.isoformat(),
                "degraded_mode": degraded_mode,
                "sliding_window": {
                    "retrospective_days": self.past_days,
                    "upcoming_days": self.future_days,
                },
                "classifier_stats": classifier_stats,
                "sources_health": sources_health or {},
                "counts": {
                    "total_analyzed": len(publications),
                    "total_accepted": len(accepted_events),
                    "total_rejected": rejected_count,
                    "total_out_of_window": out_of_window_count,
                    "preserved_from_previous": preserved_count,
                    "retrospective": len(buckets["retrospective"]),
                    "today": len(buckets["today"]),
                    "upcoming": len(buckets["upcoming"]),
                    "high_importance_today": high_importance_today,
                },
            },
            "buckets": buckets,
            "all_events": accepted_events,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        # Génération du flux iCalendar (.ics)
        ics_content = build_ics_calendar(accepted_events, generated_at_iso=generated_at_iso)
        self.ics_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ics_output_path, "w", encoding="utf-8", newline="") as f:
            f.write(ics_content)

        logger.info(
            f"Fichiers exportés avec succès : {self.output_path} & {self.ics_output_path} "
            f"({len(accepted_events)} événements, dont {preserved_count} préservé(s))"
        )
        return final_payload
