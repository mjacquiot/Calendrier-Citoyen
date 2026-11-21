import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.ai.classifier import GeminiClassifier
from src.scrapers.base_scraper import RawPublication
from src.utils.data_generator import DataGenerator, SCHEMA_VERSION


class TestDataGenerator(unittest.TestCase):
    def test_press_excerpt_no_duplication_ics_and_anti_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            json_path = tmp_path / "data.json"
            ics_path = tmp_path / "calendar.ics"
            ref = date(2026, 11, 21)

            classifier = GeminiClassifier(api_key="AIzaSyYourGeminiApiKeyHere")
            gen = DataGenerator(
                output_path=str(json_path),
                ics_output_path=str(ics_path),
                classifier=classifier,
            )

            official_pub = RawPublication(
                id="illiwap_serd",
                source_id="illiwap_dunieres",
                source_name="Illiwap Mairie de Dunières",
                title="Semaine Européenne de Réduction des Déchets",
                content=(
                    "Rendez-vous vendredi 27 novembre 2026 à TENCE :\n"
                    "Salle Maria Bonnet de 13h à 19h\n"
                    "Ciné-débat de 20h30 à 22h"
                ),
                url="https://station.illiwap.com/serd",
                raw_metadata={"is_press": False},
            )
            press_pub = RawPublication(
                id="lacommere43_karaoke",
                source_id="lacommere43",
                source_name="La Commère 43",
                title="Soirée burger karaoké du FJEP de Dunières",
                content=(
                    "L'association FJEP de Dunières organise une soirée burger karaoké le vendredi 20 novembre 2026 "
                    "à partir de 18h30 à la salle de la Mutualité de Dunières.\n\n"
                    "Menu burger + frites à 10 €."
                ),
                url="https://www.lacommere43.fr/item/86272",
                raw_metadata={"is_press": True},
            )

            payload = gen.process_and_export([official_pub, press_pub], ref_date=ref)

            self.assertEqual(payload["metadata"]["schema_version"], SCHEMA_VERSION)
            self.assertEqual(len(payload["all_events"]), 2)

            # Pas de duplication dans buckets : uniquement des IDs
            self.assertEqual(payload["buckets"]["retrospective"], ["lacommere43_karaoke"])
            self.assertEqual(payload["buckets"]["upcoming"], ["illiwap_serd"])

            # Politique presse : pas de full_content stocké
            events_by_id = {ev["id"]: ev for ev in payload["all_events"]}
            self.assertTrue(events_by_id["lacommere43_karaoke"]["is_press_excerpt"])
            self.assertIsNone(events_by_id["lacommere43_karaoke"]["full_content"])
            self.assertFalse(events_by_id["illiwap_serd"]["is_press_excerpt"])
            self.assertIsNotNone(events_by_id["illiwap_serd"]["full_content"])

            # Vérification du fichier ICS généré (2 VEVENTs pour SERD + 1 pour karaoké)
            ics_text = ics_path.read_text(encoding="utf-8")
            self.assertIn("BEGIN:VCALENDAR", ics_text)
            self.assertIn("END:VCALENDAR", ics_text)
            self.assertEqual(ics_text.count("BEGIN:VEVENT"), 3)

            # Garde-fou anti-écrasement si collecte vide le lendemain
            degraded_payload = gen.process_and_export([], ref_date=ref)
            self.assertTrue(degraded_payload["metadata"]["degraded_mode"])
            self.assertEqual(degraded_payload["metadata"]["counts"]["preserved_from_previous"], 2)
            self.assertEqual(len(degraded_payload["all_events"]), 2)

            # Vérifier la relecture du JSON sur disque
            disk_data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(disk_data["all_events"]), 2)


if __name__ == "__main__":
    unittest.main()
