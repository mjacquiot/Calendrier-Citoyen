import unittest

from src.notifications.whatsapp_bot import WhatsAppNotifier
from src.utils.http_client import sanitize_url_for_log


class TestWhatsappAndHttp(unittest.TestCase):
    def test_sanitize_url_for_log_masks_secrets(self):
        raw = "https://api.callmebot.com/whatsapp.php?phone=33612345678&text=Bonjour&apikey=987654&token=abc"
        safe = sanitize_url_for_log(raw)
        self.assertNotIn("33612345678", safe)
        self.assertNotIn("987654", safe)
        self.assertNotIn("abc", safe)
        self.assertIn("phone=***", safe)
        self.assertIn("apikey=***", safe)
        self.assertIn("text=Bonjour", safe)

    def test_whatsapp_message_distinguishes_alerts_and_uses_j7_window(self):
        notifier = WhatsAppNotifier(phone="+33600000000", api_key="dummy")
        metadata = {
            "commune": "Dunières",
            "reference_date": "2026-11-21",
            "generated_at": "2026-11-21T06:18:00+01:00",
            "sliding_window": {"retrospective_days": 7, "upcoming_days": 7},
            "classifier_stats": {"mode": "gemini"},
            "sources_health": {
                "illiwap_dunieres": {"name": "Illiwap Dunières", "status": "ok", "fetched": 3},
                "leprogres": {"name": "Le Progrès", "status": "empty", "fetched": 0},
            },
            "counts": {
                "total_analyzed": 10,
                "total_accepted": 6,
                "total_rejected": 4,
                "retrospective": 3,
                "today": 2,
                "upcoming": 1,
            },
        }
        today_events = [
            {
                "title": "Concours de coinche",
                "category": "Manifestations & Vie Associative",
                "importance": "normal",
                "timing": {"start_time": "14:00"},
            },
            {
                "title": "Route barrée RD500",
                "category": "Travaux & Voirie",
                "importance": "high",
                "timing": {"start_time": None},
            },
        ]
        msg = notifier.build_summary_message(metadata, today_events)
        self.assertIn("-7j / +7j", msg)
        self.assertIn("06h18, Gemini IA", msg)
        self.assertIn("⚠️ *Alertes prioritaires du jour :*\n• Route barrée RD500", msg)
        self.assertIn("📌 *Au programme aujourd'hui :*\n• [14:00] Concours de coinche", msg)
        self.assertIn("Le Progrès (empty)", msg)


if __name__ == "__main__":
    unittest.main()
