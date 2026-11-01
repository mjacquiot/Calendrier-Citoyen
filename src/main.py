"""
Script principal d'orchestration (exécuté quotidiennement par GitHub Actions ou en local).
"""

import sys
import json
import logging
from pathlib import Path

# Inclusion de la racine dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scrapers.illiwap_scraper import IlliwapScraper
from src.scrapers.commere43_scraper import Commere43Scraper
from src.scrapers.leprogres_scraper import LeProgresScraper
from src.enrichment.recursive_manager import RecursiveEnrichmentManager
from src.utils.data_generator import DataGenerator
from src.notifications.whatsapp_bot import WhatsAppNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MainPipeline")


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
    all_raw_pubs = []

    # 2. Collecte multi-sources
    for source in config.get("sources", []):
        if not source.get("enabled", True):
            continue

        s_type = source.get("type")
        s_name = source.get("nom", source.get("id"))
        logger.info(f"--- Lancement de la source : {s_name} ({s_type}) ---")

        try:
            if s_type == "illiwap":
                scraper = IlliwapScraper(source)
                pubs = scraper.fetch()
                all_raw_pubs.extend(pubs)
            elif s_type == "commere43":
                scraper = Commere43Scraper(source, keywords)
                pubs = scraper.fetch()
                all_raw_pubs.extend(pubs)
            elif s_type == "leprogres":
                scraper = LeProgresScraper(source, keywords)
                pubs = scraper.fetch()
                all_raw_pubs.extend(pubs)
            else:
                logger.warning(f"Type de scraper inconnu : {s_type}")
        except Exception as e:
            logger.error(f"Erreur lors de la collecte sur {s_name}: {e}")

    logger.info(f"Total brut collecté avant enrichissement : {len(all_raw_pubs)} publications")

    # 3. Enrichissement récursif (Calaméo, PDF) & Déduplication
    enrichment_manager = RecursiveEnrichmentManager(
        max_pdf_size_mb=config.get("enrichment_rules", {}).get("max_pdf_size_mb", 10)
    )
    enriched_pubs = enrichment_manager.enrich_publications(all_raw_pubs)
    unique_pubs = enrichment_manager.deduplicate(enriched_pubs)

    # 4. Traitement IA, Filtrage Déontologique & Génération de web/data.json
    generator = DataGenerator(output_path=str(PROJECT_ROOT / "web" / "data.json"))
    payload = generator.process_and_export(unique_pubs)

    # 5. Notification WhatsApp (optionnelle pour l'élu)
    try:
        notifier = WhatsAppNotifier()
        alerts_today = payload.get("buckets", {}).get("today", [])
        notifier.send_daily_summary(payload.get("metadata", {}), alerts_today)
    except Exception as e:
        logger.warning(f"Erreur lors de la notification WhatsApp : {e}")

    logger.info("=================================================================")
    logger.info("PIPELINE QUOTIDIEN TERMINÉ AVEC SUCCÈS")
    logger.info("=================================================================")
    return True


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
