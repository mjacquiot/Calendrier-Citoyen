"""
Script principal d'orchestration (exécuté quotidiennement par GitHub Actions ou en local).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Inclusion de la racine dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.enrichment.recursive_manager import RecursiveEnrichmentManager
from src.notifications.whatsapp_bot import WhatsAppNotifier
from src.scrapers.base_scraper import RawPublication
from src.scrapers.commere43_scraper import Commere43Scraper
from src.scrapers.illiwap_scraper import IlliwapScraper
from src.scrapers.leprogres_scraper import LeProgresScraper
from src.utils.data_generator import DataGenerator
from src.utils.date_helpers import WINDOW_FUTURE_DAYS, WINDOW_PAST_DAYS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MainPipeline")


def load_manual_events(manual_path: Path) -> List[RawPublication]:
    """Charge d'éventuels événements manuels déclarés dans config/manual_events.json."""
    if not manual_path.exists():
        return []
    try:
        with open(manual_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            return []
    except Exception as e:
        logger.warning(f"Impossible de lire {manual_path}: {e}")
        return []

    pubs: List[RawPublication] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("title"):
            continue
        title = str(entry["title"]).strip()
        date_str = str(entry.get("date") or entry.get("start_date") or "").strip()
        time_str = str(entry.get("time") or "").strip()
        location = str(entry.get("location") or "Dunières").strip()
        description = str(entry.get("description") or entry.get("content") or title).strip()
        url = str(entry.get("url") or "https://station.illiwap.com/fr/public/43087").strip()

        lines = [description]
        if location:
            lines.append(f"📍 {location}")
        if date_str:
            lines.append(f"🗓️ {date_str}")
        if time_str:
            lines.append(f"🕒 {time_str}")

        pubs.append(
            RawPublication(
                id=str(entry.get("id") or f"manual_mairie_{idx}"),
                source_id="manual_mairie",
                source_name="Mairie de Dunières (Ajout manuel)",
                title=title,
                content="\n".join(lines),
                url=url,
                published_at=date_str or None,
                image_url=entry.get("image_url"),
                external_links=list(entry.get("external_links") or []),
                raw_metadata={
                    "is_press": False,
                    "recursive_crawl": True,
                    "manual": True,
                },
            )
        )
    if pubs:
        logger.info(f"Chargé {len(pubs)} événement(s) manuel(s) depuis {manual_path}")
    return pubs


def run_pipeline() -> bool:
    logger.info("=================================================================")
    logger.info("DÉMARRAGE DU PIPELINE MUNICIPAL DUNIÈRES & HAUT PAYS DU VELAY")
    logger.info("=================================================================")

    # 1. Chargement de la configuration
    config_file = PROJECT_ROOT / "config" / "sources.json"
    if not config_file.exists():
        logger.error(f"Fichier de configuration introuvable : {config_file}")
        return False

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    keywords = config.get("territoire_keywords", ["Dunières", "Haut Pays du Velay"])
    enrichment_rules = config.get("enrichment_rules", {})
    default_timeout = int(enrichment_rules.get("request_timeout_seconds", 15))
    max_pdf_mb = int(enrichment_rules.get("max_pdf_size_mb", 10))

    sliding_cfg = config.get("sliding_window", {})
    past_days = int(sliding_cfg.get("retrospective_days", WINDOW_PAST_DAYS))
    future_days = int(sliding_cfg.get("upcoming_days", WINDOW_FUTURE_DAYS))

    all_raw_pubs: List[RawPublication] = []
    sources_health: Dict[str, Dict[str, Any]] = {}

    # 2. Collecte multi-sources
    for source in config.get("sources", []):
        if not source.get("enabled", True):
            continue

        source_cfg = dict(source)
        source_cfg.setdefault("timeout", default_timeout)

        s_id = source_cfg.get("id", "unknown")
        s_type = source_cfg.get("type")
        s_name = source_cfg.get("nom", s_id)
        logger.info(f"--- Lancement de la source : {s_name} ({s_type}) ---")

        try:
            pubs: List[RawPublication] = []
            if s_type == "illiwap":
                pubs = IlliwapScraper(source_cfg).fetch()
            elif s_type == "commere43":
                pubs = Commere43Scraper(source_cfg, keywords).fetch()
            elif s_type == "leprogres":
                pubs = LeProgresScraper(source_cfg, keywords).fetch()
            else:
                logger.warning(f"Type de scraper inconnu : {s_type}")
                sources_health[s_id] = {"name": s_name, "status": "error", "fetched": 0}
                continue

            all_raw_pubs.extend(pubs)
            sources_health[s_id] = {
                "name": s_name,
                "status": "ok" if pubs else "empty",
                "fetched": len(pubs),
            }
        except Exception as e:
            logger.error(f"Erreur lors de la collecte sur {s_name}: {e}")
            sources_health[s_id] = {"name": s_name, "status": "error", "fetched": 0}

    # Chargement des éventuels événements manuels
    manual_pubs = load_manual_events(PROJECT_ROOT / "config" / "manual_events.json")
    all_raw_pubs.extend(manual_pubs)

    logger.info(f"Total brut collecté avant déduplication : {len(all_raw_pubs)} publications")

    # 3. Déduplication d'abord, puis enrichissement récursif (Calaméo, PDF)
    enrichment_manager = RecursiveEnrichmentManager(
        max_pdf_size_mb=max_pdf_mb,
        timeout=default_timeout,
    )
    unique_pubs = enrichment_manager.deduplicate(all_raw_pubs)
    enriched_pubs = enrichment_manager.enrich_publications(unique_pubs)

    # 4. Traitement IA, Filtrage Déontologique & Génération de web/data.json + web/calendar.ics
    generator = DataGenerator(
        output_path=str(PROJECT_ROOT / "web" / "data.json"),
        ics_output_path=str(PROJECT_ROOT / "web" / "calendar.ics"),
        past_days=past_days,
        future_days=future_days,
    )
    payload = generator.process_and_export(enriched_pubs, sources_health=sources_health)

    # 5. Notification WhatsApp (optionnelle pour l'élu)
    try:
        notifier = WhatsAppNotifier()
        today_events = [
            ev for ev in payload.get("all_events", [])
            if (ev.get("dates") or {}).get("bucket") == "today"
        ]
        notifier.send_daily_summary(payload.get("metadata", {}), today_events)
    except Exception as e:
        logger.warning(f"Erreur lors de la notification WhatsApp : {e}")

    logger.info("=================================================================")
    logger.info("PIPELINE QUOTIDIEN TERMINÉ AVEC SUCCÈS")
    logger.info("=================================================================")
    return True


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
