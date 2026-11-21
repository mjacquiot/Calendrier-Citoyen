import unittest

from src.utils.text_helpers import clean_event_title, normalize_text, smart_truncate


class TestTextHelpers(unittest.TestCase):
    def test_normalize_text_entities_elisions_and_cloudflare_email(self):
        raw = "L&#039; Ehpad &amp; l' accueil\nMail : [email protected]\nVoir:https://example.com"
        cleaned = normalize_text(raw)
        self.assertIn("L'Ehpad & l'accueil", cleaned)
        self.assertNotIn("[email protected]", cleaned)
        self.assertNotIn("Mail :", cleaned)
        self.assertIn("Voir: https://example.com", cleaned)

    def test_clean_event_title(self):
        self.assertEqual(
            clean_event_title("📅 Atelier bien-être : soutenir l’immunité"),
            "Atelier bien-être : soutenir l’immunité",
        )
        self.assertEqual(
            clean_event_title("concours coinche samedi 21 novembre"),
            "Concours coinche samedi 21 novembre",
        )

    def test_smart_truncate_preserves_words(self):
        text = "Première phrase complète. Deuxième phrase beaucoup plus longue qui dépasse largement la limite."
        res = smart_truncate(text, 45)
        self.assertLessEqual(len(res), 45)
        self.assertTrue(res.endswith(".") or res.endswith("…"))
        self.assertNotIn("beauc", res)


if __name__ == "__main__":
    unittest.main()
