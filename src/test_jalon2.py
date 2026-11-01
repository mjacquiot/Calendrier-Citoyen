"""
Script de test et de validation pour le Jalon 2.
Exécute la collecte multi-sources et la résolution récursive en 2 étapes.
"""

import sys
import json
import logging
from pathlib import Path

# Assurer l'inclusion de la racine du projet dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scrapers.illiwap_scraper import IlliwapScraper
from src.scrapers.commere43_scraper import Commere43Scraper
from src.scrapers.leprogres_scraper import LeProgresScraper
from src.enrichment.recursive_manager import RecursiveEnrichmentManager
from src.enrichment.calameo_resolver import CalameoResolver
from src.enrichment.pdf_resolver import PdfResolver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestJalon2")


def main():
    logger.info("=== VALIDATION DU JALON 2 (COLLECTE & ENRICHISSEMENT RÉCURSIF) ===")

    # 1. Chargement de la configuration
    config_path = Path("config/sources.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    keywords = config.get("territoire_keywords", ["Dunières", "Haut Pays du Velay"])
    all_raw_pubs = []

    # 2. Test du collecteur Illiwap Dunières (43087)
    illiwap_conf_dunieres = next(s for s in config["sources"] if s["id"] == "illiwap_dunieres")
    scraper_illiwap_dunieres = IlliwapScraper(illiwap_conf_dunieres)
    pubs_dunieres = scraper_illiwap_dunieres.fetch()
    logger.info(f"-> Illiwap Dunières : {len(pubs_dunieres)} annonces récupérées")
    all_raw_pubs.extend(pubs_dunieres)

    # 3. Test du collecteur Illiwap Haut Pays du Velay
    illiwap_conf_comcom = next(s for s in config["sources"] if s["id"] == "illiwap_comcom")
    scraper_illiwap_comcom = IlliwapScraper(illiwap_conf_comcom)
    pubs_comcom = scraper_illiwap_comcom.fetch()
    logger.info(f"-> Illiwap Haut Pays du Velay : {len(pubs_comcom)} annonces récupérées")
    all_raw_pubs.extend(pubs_comcom)

    # 4. Test du collecteur La Commère 43
    commere_conf = next(s for s in config["sources"] if s["id"] == "lacommere43")
    scraper_commere = Commere43Scraper(commere_conf, keywords)
    pubs_commere = scraper_commere.fetch()
    logger.info(f"-> La Commère 43 : {len(pubs_commere)} articles retenus pour le secteur")
    all_raw_pubs.extend(pubs_commere)

    # 5. Test du collecteur Le Progrès
    progres_conf = next(s for s in config["sources"] if s["id"] == "leprogres_haute_loire")
    scraper_progres = LeProgresScraper(progres_conf, keywords)
    pubs_progres = scraper_progres.fetch()
    logger.info(f"-> Le Progrès : {len(pubs_progres)} articles retenus")
    all_raw_pubs.extend(pubs_progres)

    # 6. Test direct unitaire du résolveur Calaméo
    logger.info("\n--- TEST UNITAIRE : RÉSOLUTION CALAMÉO DIRECTE ---")
    calameo_resolver = CalameoResolver()
    sample_calameo_url = "https://www.calameo.com/read/001159770add8fb838647"
    calameo_res = calameo_resolver.resolve(sample_calameo_url)
    assert calameo_res is not None, "La résolution Calaméo a échoué"
    logger.info(f"Titre extrait : {calameo_res.get('title')}")
    logger.info(f"Auteur : {calameo_res.get('author')}")
    logger.info(f"Image couverture : {calameo_res.get('cover_image_url')}")
    logger.info(f"Description (extrait) : {calameo_res.get('description')[:150]}...")

    # 7. Exécution du gestionnaire d'enrichissement récursif et déduplication
    logger.info("\n--- EXÉCUTION DU GESTIONNAIRE D'ENRICHISSEMENT RÉCURSIF ---")
    enrichment_manager = RecursiveEnrichmentManager()
    enriched_pubs = enrichment_manager.enrich_publications(all_raw_pubs)
    final_pubs = enrichment_manager.deduplicate(enriched_pubs)

    logger.info("\n================ RÉSUMÉ DU JALON 2 ================")
    logger.info(f"Total publications brutes collectées : {len(all_raw_pubs)}")
    logger.info(f"Total publications après enrichissement et déduplication : {len(final_pubs)}")

    # Vérification qu'au moins une publication a bénéficié de la résolution Calaméo
    with_calameo = [p for p in final_pubs if "calameo" in p.enrichment]
    logger.info(f"Publications enrichies avec Calaméo : {len(with_calameo)}")
    for p in with_calameo:
        logger.info(f"  • {p.title} (Source: {p.source_name})")
        logger.info(f"    -> Calaméo lié : {p.enrichment['calameo']['title']}")

    logger.info("\nJALON 2 VALIDÉ AVEC SUCCÈS !")


if __name__ == "__main__":
    main()
