"""
Générateur du fichier structuré web/data.json pour le calendrier glissant en 3 volets.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.scrapers.base_scraper import RawPublication
from src.ai.classifier import GeminiClassifier
from src.ai.schemas import ClassifiedEvent
from src.utils.date_helpers import determine_bucket, get_current_date, PARIS_TZ

logger = logging.getLogger(__name__)


class DataGenerator:
    """Transforme les publications classifiées en structure de données pour le portail web."""

    def __init__(self, output_path: str = "web/data.json"):
        self.output_path = Path(output_path)
        self.classifier = GeminiClassifier()

    def process_and_export(self, publications: List[RawPublication], ref_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Traite la liste des publications, applique le tri déontologique,
        calcule les 3 volets temporels et écrit le fichier web/data.json.
        """
        if ref_date is None:
            ref_date = get_current_date()

        logger.info(f"Traitement IA et fenêtrage glissant (Date de référence : {ref_date})...")

        accepted_events = []
        rejected_count = 0

        buckets: Dict[str, List[Dict[str, Any]]] = {
            "retrospective": [],
            "today": [],
            "upcoming": [],
            "extended": []
        }

        for pub in publications:
            # Classification déontologique & extraction IA
            event: ClassifiedEvent = self.classifier.classify(pub)

            if not event.is_public_interest:
                logger.info(f"[REJET DÉONTOLOGIQUE] '{pub.title}' -> {event.rejection_reason}")
                rejected_count += 1
                continue

            # Détermination du volet temporel (bucket)
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

            is_period = bool(d_end and d_end != d_start)

            # Assemblage de l'objet final
            item = {
                "id": pub.id,
                "title": event.title,
                "summary": event.summary,
                "category": event.category,
                "badge": event.badge,
                "source_name": pub.source_name,
                "source_url": pub.url,
                "image_url": pub.image_url,
                "dates": {
                    "start": event.start_date or d_start.isoformat(),
                    "end": event.end_date,
                    "is_period": is_period,
                    "bucket": bucket
                },
                "location": event.location,
                "importance": event.importance,
                "has_attachment": bool(pub.enrichment),
                "attachment_type": list(pub.enrichment.keys())[0] if pub.enrichment else None,
                "attachment_data": pub.enrichment.get("calameo") or pub.enrichment.get("pdf")
            }

            accepted_events.append(item)
            if bucket in buckets:
                buckets[bucket].append(item)
            else:
                buckets["upcoming"].append(item)

        # Tri chronologique dans chaque volet
        for b_name in buckets:
            buckets[b_name].sort(key=lambda x: x["dates"]["start"])

        # Assemblage final
        final_payload = {
            "metadata": {
                "commune": "Dunières",
                "code_postal": "43220",
                "intercommunalite": "Haut Pays du Velay Communauté",
                "generated_at": datetime.now(PARIS_TZ).isoformat(),
                "reference_date": ref_date.isoformat(),
                "sliding_window": {
                    "retrospective_days": 15,
                    "upcoming_days": 15
                },
                "counts": {
                    "total_analyzed": len(publications),
                    "total_accepted": len(accepted_events),
                    "total_rejected": rejected_count,
                    "retrospective": len(buckets["retrospective"]),
                    "today": len(buckets["today"]),
                    "upcoming": len(buckets["upcoming"])
                }
            },
            "buckets": {
                "retrospective": buckets["retrospective"],
                "today": buckets["today"],
                "upcoming": buckets["upcoming"]
            },
            "all_events": accepted_events
        }

        # Écriture atomique dans web/data.json
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        logger.info(f"Fichier exporté avec succès : {self.output_path} ({len(accepted_events)} événements retenus)")
        return final_payload
