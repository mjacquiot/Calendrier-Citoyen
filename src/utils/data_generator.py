"""
Générateur du fichier structuré web/data.json pour le calendrier glissant en 3 volets (J-7 / Aujourd'hui / J+7).
"""

import json
import re
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.scrapers.base_scraper import RawPublication
from src.ai.classifier import GeminiClassifier
from src.ai.schemas import ClassifiedEvent
from src.utils.date_helpers import (
    determine_bucket,
    extract_time_range,
    get_current_date,
    PARIS_TZ,
    WINDOW_DAYS,
)
from src.utils.text_helpers import normalize_text

logger = logging.getLogger(__name__)


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


def _build_timing(event: ClassifiedEvent, pub: RawPublication) -> Dict[str, Any]:
    """Assemble l'objet timing normalisé à partir de la sortie IA et de l'extraction déterministe."""
    fallback = extract_time_range(f"{normalize_text(pub.title)}\n{normalize_text(pub.content)}")

    start_min = _parse_hhmm_minutes(event.start_time)
    end_min = _parse_hhmm_minutes(event.end_time)

    start_time = f"{start_min // 60:02d}:{start_min % 60:02d}" if start_min is not None else fallback["start_time"]
    end_time = f"{end_min // 60:02d}:{end_min % 60:02d}" if end_min is not None else fallback["end_time"]

    s_m = _parse_hhmm_minutes(start_time)
    e_m = _parse_hhmm_minutes(end_time)
    duration_minutes: Optional[int] = None
    if s_m is not None and e_m is not None and e_m > s_m:
        duration_minutes = e_m - s_m
    elif fallback.get("duration_minutes"):
        duration_minutes = fallback["duration_minutes"]

    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": duration_minutes,
        "all_day": start_time is None,
    }


class DataGenerator:
    """Transforme les publications classifiées en structure de données pour le portail web."""

    def __init__(self, output_path: str = "web/data.json"):
        self.output_path = Path(output_path)
        self.classifier = GeminiClassifier()

    def process_and_export(self, publications: List[RawPublication], ref_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Traite la liste des publications, applique le tri déontologique,
        calcule les 3 volets temporels (J-7 / Aujourd'hui / J+7) et écrit web/data.json.
        """
        if ref_date is None:
            ref_date = get_current_date()

        logger.info(f"Traitement IA et fenêtrage glissant J-{WINDOW_DAYS}/J+{WINDOW_DAYS} (Date de référence : {ref_date})...")

        accepted_events: List[Dict[str, Any]] = []
        rejected_count = 0
        out_of_window_count = 0

        buckets: Dict[str, List[Dict[str, Any]]] = {
            "retrospective": [],
            "today": [],
            "upcoming": [],
        }

        for pub in publications:
            event: ClassifiedEvent = self.classifier.classify(pub)

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
                d_start = ref_date

            bucket = determine_bucket(d_start, d_end, ref_date)
            if bucket not in buckets:
                logger.info(f"[HORS FENÊTRE {bucket}] '{event.title}' ({d_start})")
                out_of_window_count += 1
                continue

            is_period = bool(d_end and d_end != d_start)
            timing = _build_timing(event, pub)
            full_content = normalize_text(pub.content)

            item = {
                "id": pub.id,
                "title": normalize_text(event.title),
                "summary": normalize_text(event.summary),
                "full_content": full_content,
                "category": event.category,
                "badge": event.badge,
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
                "location": normalize_text(event.location),
                "importance": event.importance,
                "has_attachment": bool(pub.enrichment),
                "attachment_type": list(pub.enrichment.keys())[0] if pub.enrichment else None,
                "attachment_data": pub.enrichment.get("calameo") or pub.enrichment.get("pdf"),
            }

            accepted_events.append(item)
            buckets[bucket].append(item)

        def _sort_key(ev: Dict[str, Any]):
            return (ev["dates"]["start"], ev["timing"]["start_time"] or "99:99")

        accepted_events.sort(key=_sort_key)
        for b_name in buckets:
            buckets[b_name].sort(key=_sort_key)

        final_payload = {
            "metadata": {
                "commune": "Dunières",
                "code_postal": "43220",
                "intercommunalite": "Haut Pays du Velay Communauté",
                "generated_at": datetime.now(PARIS_TZ).isoformat(),
                "reference_date": ref_date.isoformat(),
                "sliding_window": {
                    "retrospective_days": WINDOW_DAYS,
                    "upcoming_days": WINDOW_DAYS,
                },
                "counts": {
                    "total_analyzed": len(publications),
                    "total_accepted": len(accepted_events),
                    "total_rejected": rejected_count,
                    "total_out_of_window": out_of_window_count,
                    "retrospective": len(buckets["retrospective"]),
                    "today": len(buckets["today"]),
                    "upcoming": len(buckets["upcoming"]),
                },
            },
            "buckets": {
                "retrospective": buckets["retrospective"],
                "today": buckets["today"],
                "upcoming": buckets["upcoming"],
            },
            "all_events": accepted_events,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        logger.info(f"Fichier exporté avec succès : {self.output_path} ({len(accepted_events)} événements dans la fenêtre J-{WINDOW_DAYS}/J+{WINDOW_DAYS})")
        return final_payload
