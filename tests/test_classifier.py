import unittest
from datetime import date

from src.ai.classifier import GeminiClassifier
from src.scrapers.base_scraper import RawPublication


class TestClassifierHeuristic(unittest.TestCase):
    def setUp(self):
        self.classifier = GeminiClassifier(api_key="AIzaSyYourGeminiApiKeyHere")
        self.ref = date(2026, 11, 21)

    def test_rejects_andre_marcon_book_and_never_conseil_municipal(self):
        pub = RawPublication(
            id="lacommere43_86403",
            source_id="lacommere43",
            source_name="La Commère 43",
            title='André Marcon raconte l\'intimité familiale dans son livre "Les Marcon de Saint-Bonnet-le-Froid"',
            content=(
                "André Marcon vient de publier un livre où il raconte l'histoire familiale.\n\n"
                "Son frère Jean-Pierre a aussi été maire de Saint-Bonnet puis de Dunières.\n\n"
                "« Les Marcon de Saint-Bonnet-le-Froid », La Clé du Chemin 21 €"
            ),
            url="https://www.lacommere43.fr/item/86403",
            published_at="2026-11-18",
            raw_metadata={"is_press": True},
        )
        ev = self.classifier.classify(pub, ref_date=self.ref)
        self.assertFalse(ev.is_public_interest)
        self.assertNotEqual(ev.category, "Vie Municipale & Délibérations")

    def test_rejects_private_business_openings(self):
        garage = RawPublication(
            id="lacommere43_86433",
            source_id="lacommere43",
            source_name="La Commère 43",
            title="Il ouvre son garage automobile au milieu de la nature, entre Dunières et Saint-Julien-Molhesabate",
            content=(
                "Nicolas Truchet vient d'ouvrir un garage automobile au hameau de Coirolles.\n\n"
                "Le garage Truchet propose différentes prestations automobiles.\n\n"
                "Mail : [email protected]"
            ),
            url="https://www.lacommere43.fr/item/86433",
            published_at="2026-11-19",
            raw_metadata={"is_press": True},
        )
        bijoux = RawPublication(
            id="lacommere43_86404",
            source_id="lacommere43",
            source_name="La Commère 43",
            title="Dunières : Fanny Souchon crée des bijoux fantaisie à l'enseigne ALMA des Sucs",
            content="Fanny Souchon lance ALMA des Sucs à Dunières, une micro-entreprise artisanale.",
            url="https://www.lacommere43.fr/item/86404",
            published_at="2026-11-18",
            raw_metadata={"is_press": True},
        )
        self.assertFalse(self.classifier.classify(garage, ref_date=self.ref).is_public_interest)
        self.assertFalse(self.classifier.classify(bijoux, ref_date=self.ref).is_public_interest)

    def test_raucoules_bourse_aux_jouets_ignores_zenith_encart(self):
        pub = RawPublication(
            id="lacommere43_86350",
            source_id="lacommere43",
            source_name="La Commère 43",
            title="Raucoules : de bonnes affaires et une bonne action à la bourse aux jouets",
            content=(
                "La bourse aux jouets, vêtements et articles de puériculture organisée le dimanche 15 novembre "
                "à la salle polyvalente de Raucoules a rencontré un beau succès.\n\n"
                "Organisée conjointement par le Conseil Municipal des Jeunes et l'association Familles Rurales de Raucoules.\n\n"
                "L'intégralité des bénéfices, soit 600 €, a été remise à l'association « Victor, notre super héros ».\n\n"
                "Noël : un moment musical et gourmand le 19 décembre\n\n"
                "Une sortie en car au Zénith de Saint-Étienne le dimanche 31 janvier 2027 à 18 heures. Le tarif est de 50 € par place."
            ),
            url="https://www.lacommere43.fr/item/86350",
            published_at="2026-11-15",
            raw_metadata={"is_press": True},
        )
        ev = self.classifier.classify(pub, ref_date=self.ref)
        self.assertTrue(ev.is_public_interest)
        self.assertEqual(ev.category, "Manifestations & Vie Associative")
        self.assertEqual(ev.start_date, "2026-11-15")
        self.assertIsNone(ev.start_time)
        self.assertIsNone(ev.price)
        self.assertEqual(ev.location, "Salle polyvalente de Raucoules")

    def test_serd_tence_double_slot_and_location(self):
        pub = RawPublication(
            id="illiwap_serd",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="La Semaine Européenne de Réduction des Déchets",
            content=(
                "La Semaine Européenne de Réduction des Déchets met en lumière la fast-fashion.\n"
                "Rendez-vous vendredi 27 novembre 2026 à TENCE (6 rue de Saint-Agrève) :\n"
                "Salle Maria Bonnet, l'après-midi, pour des animations et une friperie (de 13h à 19h)\n"
                "Au cinéma pour un ciné-débat (de 20h30 à 22h)"
            ),
            url="https://station.illiwap.com/fr/public/43087/actu/serd",
            published_at="2026-11-20",
            raw_metadata={"is_press": False},
        )
        ev = self.classifier.classify(pub, ref_date=self.ref)
        self.assertTrue(ev.is_public_interest)
        self.assertEqual(ev.category, "Services & Déchets")
        self.assertEqual(ev.start_date, "2026-11-27")
        self.assertEqual(ev.start_time, "13:00")
        self.assertEqual(ev.end_time, "19:00")
        self.assertEqual(ev.additional_slots, ["20:30-22:00"])
        self.assertIn("Tence", ev.location)

    def test_prevention_meeting_and_vol_de_nuit_accepted_real_fait_divers_rejected(self):
        prevention = RawPublication(
            id="prev_1",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Réunion publique de prévention contre les cambriolages",
            content="Mardi 24 novembre 2026 à 18h30 à la Salle des Associations de Dunières.",
            url="https://station.illiwap.com/prev",
            raw_metadata={"is_press": False},
        )
        cinema = RawPublication(
            id="cine_1",
            source_id="illiwap_comcom",
            source_name="Illiwap Comcom",
            title="Projection cinéma : Vol de nuit",
            content="Vendredi 27 novembre 2026 à 20h30 au Cinéma de Dunières. Entrée : 6 €.",
            url="https://station.illiwap.com/cine",
            raw_metadata={"is_press": False},
        )
        accident = RawPublication(
            id="fd_1",
            source_id="leprogres",
            source_name="Le Progrès",
            title="Accident de la route : deux blessés légers après un refus de priorité",
            content="Une collision s'est produite hier soir sur la RD500.",
            url="https://www.leprogres.fr/fd",
            published_at="2026-11-20",
            raw_metadata={"is_press": True},
        )

        self.assertTrue(self.classifier.classify(prevention, ref_date=self.ref).is_public_interest)
        ev_cine = self.classifier.classify(cinema, ref_date=self.ref)
        self.assertTrue(ev_cine.is_public_interest)
        self.assertEqual(ev_cine.price, "6 €")
        self.assertFalse(self.classifier.classify(accident, ref_date=self.ref).is_public_interest)

    def test_coinche_theatre_and_conseil_municipal(self):
        coinche = RawPublication(
            id="illiwap_coinche",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="concours coinche samedi 21 novembre 14h EPHATA 43",
            content=(
                "L'association Ephata 43 renouvelle son concours de coinche, le samedi 21 novembre 2026, "
                "à la Salle des Associations de Dunières.\n"
                "Premier lot = 2 x 100€.\n"
                "Début des inscriptions à 14h. Fin des inscriptions à 14h30."
            ),
            url="https://station.illiwap.com/coinche",
            raw_metadata={"is_press": False},
        )
        ev_coinche = self.classifier.classify(coinche, ref_date=self.ref)
        self.assertEqual(ev_coinche.title, "Concours coinche samedi 21 novembre 14h EPHATA 43")
        self.assertEqual(ev_coinche.start_time, "14:00")
        self.assertIsNone(ev_coinche.price)
        self.assertEqual(ev_coinche.location, "Salle des Associations de Dunières")

        theatre = RawPublication(
            id="illiwap_theatre",
            source_id="illiwap_comcom",
            source_name="Illiwap Haut Pays du Velay",
            title="Théâtre d’objets « Le Mystère Léon Plouhinec »",
            content=(
                "📍 Salle Renaissance, Montfaucon-en-Velay\n"
                "🗓️ Dimanche 22 novembre à 16h\n"
                "⏱️ Durée : 1h\n"
                "🎟️ Adulte : 10 €, tarif réduit : 6 €, gratuit pour les moins de 12 ans"
            ),
            url="https://station.illiwap.com/theatre",
            raw_metadata={"is_press": False},
        )
        ev_theatre = self.classifier.classify(theatre, ref_date=self.ref)
        self.assertEqual(ev_theatre.category, "Culture & Patrimoine")
        self.assertEqual(ev_theatre.start_time, "16:00")
        self.assertEqual(ev_theatre.end_time, "17:00")
        self.assertEqual(ev_theatre.price, "10 €")
        self.assertEqual(ev_theatre.location, "Salle Renaissance, Montfaucon-en-Velay")

        conseil = RawPublication(
            id="illiwap_conseil",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Séance du conseil municipal",
            content="Le prochain conseil municipal se tiendra le mardi 24 novembre 2026 à 20h00 en mairie.",
            url="https://station.illiwap.com/conseil",
            raw_metadata={"is_press": False},
        )
        ev_conseil = self.classifier.classify(conseil, ref_date=self.ref)
        self.assertEqual(ev_conseil.category, "Vie Municipale & Délibérations")
        self.assertEqual(ev_conseil.importance, "high")
        self.assertEqual(ev_conseil.start_time, "20:00")

        tripes = RawPublication(
            id="illiwap_tripes",
            source_id="illiwap_dunieres",
            source_name="Illiwap Mairie de Dunières",
            title="Tripes saucisses - Sapeurs Pompiers - 28/11/2026",
            content="L'Amicale des Sapeurs Pompiers organise Tripes Saucisses le samedi 28/11/2026 à la caserne de Dunières de 9h à 13h30.",
            url="https://station.illiwap.com/tripes",
            raw_metadata={"is_press": False},
        )
        ev_tripes = self.classifier.classify(tripes, ref_date=self.ref)
        self.assertEqual(ev_tripes.location, "Caserne de Dunières")


if __name__ == "__main__":
    unittest.main()
