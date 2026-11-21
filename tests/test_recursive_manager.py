import unittest

from src.enrichment.recursive_manager import RecursiveEnrichmentManager
from src.scrapers.base_scraper import RawPublication


class TestRecursiveManager(unittest.TestCase):
    def test_preserves_recurring_events_on_different_dates(self):
        manager = RecursiveEnrichmentManager()
        p1 = RawPublication(
            id="ev_1",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Permanence France Services",
            content="Accueil le mardi 17 novembre 2026 de 9h à 12h en mairie.",
            url="https://station.illiwap.com/fr/public/43087/actu/perm-17-nov",
        )
        p2 = RawPublication(
            id="ev_2",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Permanence France Services",
            content="Accueil le mardi 24 novembre 2026 de 9h à 12h en mairie.",
            url="https://station.illiwap.com/fr/public/43087/actu/perm-24-nov",
        )
        deduped = manager.deduplicate([p1, p2])
        self.assertEqual(len(deduped), 2)

    def test_merges_cross_source_duplicates_preferring_illiwap(self):
        manager = RecursiveEnrichmentManager()
        press = RawPublication(
            id="lacommere43_100",
            source_id="lacommere43",
            source_name="La Commère 43",
            title="Concours de coinche de l'association Ephata 43",
            content="Le concours aura lieu samedi 21 novembre 2026 à 14h à Dunières.",
            url="https://www.lacommere43.fr/item/100",
            image_url="https://www.lacommere43.fr/img.jpg",
            raw_metadata={"is_press": True},
        )
        illiwap = RawPublication(
            id="illiwap_dunieres_coinche",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Concours de coinche de l'association Ephata 43",
            content="Samedi 21 novembre 2026 à 14h à la Salle des Associations.",
            url="https://station.illiwap.com/fr/public/43087/actu/coinche",
            raw_metadata={"is_press": False},
        )
        deduped = manager.deduplicate([press, illiwap])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].source_id, "illiwap_dunieres")
        self.assertEqual(deduped[0].image_url, "https://www.lacommere43.fr/img.jpg")

    def test_merges_reordered_same_source_duplicate_announcements(self):
        manager = RecursiveEnrichmentManager()
        a = RawPublication(
            id="illiwap_1",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Tripes saucisses - Sapeurs Pompiers - 28/11/2026 - DUNIERES",
            content="L'Amicale des Sapeurs Pompiers organise Tripes Saucisses le samedi 28/11/2026 à la caserne de Dunières de 9h à 13h30.",
            url="https://station.illiwap.com/fr/public/43087/actu/1",
        )
        b = RawPublication(
            id="illiwap_2",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Tripes saucisses - Sapeurs Pompiers de Dunières - 28/11/2026",
            content="L'Amicale des Sapeurs Pompiers organise Tripes Saucisses le samedi 28/11/2026 à la caserne de Dunières de 9h à 13h30.",
            url="https://station.illiwap.com/fr/public/43087/actu/2",
        )
        deduped = manager.deduplicate([a, b])
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
