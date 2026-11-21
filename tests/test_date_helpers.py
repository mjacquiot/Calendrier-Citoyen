import unittest
from datetime import date

from src.utils.date_helpers import (
    determine_bucket,
    extract_all_time_ranges,
    extract_time_range,
    parse_dates_from_string,
)


class TestDateHelpers(unittest.TestCase):
    def test_ordinals_and_ranges(self):
        ref = date(2026, 11, 21)
        d1, d2 = parse_dates_from_string("Réunion le 1er décembre 2026", ref_date=ref)
        self.assertEqual(d1, date(2026, 12, 1))
        self.assertIsNone(d2)

        d1, d2 = parse_dates_from_string("Exposition du 1er au 7 décembre 2026", ref_date=ref)
        self.assertEqual((d1, d2), (date(2026, 12, 1), date(2026, 12, 7)))

        d1, d2 = parse_dates_from_string("Marché du 28 novembre au 2 décembre 2026", ref_date=ref)
        self.assertEqual((d1, d2), (date(2026, 11, 28), date(2026, 12, 2)))

    def test_year_rollover_dec_to_jan_and_jan_to_dec(self):
        d1, _ = parse_dates_from_string("Vœux le 15 janvier à la salle polyvalente", ref_date=date(2026, 12, 10))
        self.assertEqual(d1, date(2027, 1, 15))

        d1, _ = parse_dates_from_string("Rétrospective du 28 décembre", ref_date=date(2027, 1, 5))
        self.assertEqual(d1, date(2026, 12, 28))

    def test_ignores_street_names_and_historical_years(self):
        ref = date(2026, 11, 21)
        d1, d2 = parse_dates_from_string("Travaux Rue du 19 mars 1962 prévus le 25 novembre 2026", ref_date=ref)
        self.assertEqual(d1, date(2026, 11, 25))
        self.assertIsNone(d2)

        d1, d2 = parse_dates_from_string("Rendez-vous 12 rue du 19 mars 1962 à Dunières", ref_date=ref)
        self.assertIsNone(d1)
        self.assertIsNone(d2)

    def test_numeric_dates_only_range_when_explicit(self):
        ref = date(2026, 11, 21)
        d1, d2 = parse_dates_from_string(
            "Inscriptions avant le 10/11/2026 pour le spectacle du 22/11/2026",
            ref_date=ref,
        )
        self.assertEqual(d1, date(2026, 11, 10))
        self.assertIsNone(d2)

        d1, d2 = parse_dates_from_string("Travaux du 18/11/2026 au 25/11/2026", ref_date=ref)
        self.assertEqual((d1, d2), (date(2026, 11, 18), date(2026, 11, 25)))

    def test_multiple_time_slots_and_noise_filtering(self):
        serd_text = (
            "Publié le 19/11/2026 à 15:45\n"
            "Salle Maria Bonnet, l'après-midi, pour des animations et une friperie (de 13h à 19h)\n"
            "Au cinéma pour un ciné-débat (de 20h30 à 22h)"
        )
        slots = extract_all_time_ranges(serd_text)
        self.assertEqual(len(slots), 2)
        self.assertEqual((slots[0]["start_time"], slots[0]["end_time"]), ("13:00", "19:00"))
        self.assertEqual((slots[1]["start_time"], slots[1]["end_time"]), ("20:30", "22:00"))

        # Durée explicite et fin des inscriptions ne doivent pas créer de faux horaires de début
        coinche_text = "Début des inscriptions à 14h. Fin des inscriptions à 14h30. Durée : 3h"
        slots_coinche = extract_all_time_ranges(coinche_text)
        self.assertEqual(len(slots_coinche), 1)
        self.assertEqual(slots_coinche[0]["start_time"], "14:00")
        self.assertEqual(slots_coinche[0]["end_time"], "17:00")

        t_info = extract_time_range(serd_text)
        self.assertEqual(t_info["start_time"], "13:00")
        self.assertEqual(len(t_info["slots"]), 2)

    def test_determine_bucket_handles_inverted_end_date(self):
        ref = date(2026, 11, 21)
        self.assertEqual(determine_bucket(date(2026, 11, 21), date(2026, 11, 10), ref_date=ref), "today")
        self.assertEqual(determine_bucket(date(2026, 11, 14), None, ref_date=ref), "retrospective")
        self.assertEqual(determine_bucket(date(2026, 11, 13), None, ref_date=ref), "archive")
        self.assertEqual(determine_bucket(date(2026, 11, 28), None, ref_date=ref), "upcoming")
        self.assertEqual(determine_bucket(date(2026, 11, 29), None, ref_date=ref), "extended")


if __name__ == "__main__":
    unittest.main()
