"""
Module de notification WhatsApp (CallMeBot) pour l'élu local.
Envoie un résumé quotidien d'exécution et distingue les alertes prioritaires du programme du jour.
"""

import logging
import os
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.utils.http_client import fetch_url_with_status

load_dotenv()
logger = logging.getLogger(__name__)


class WhatsAppNotifier:
    """Envoie des notifications WhatsApp à l'élu via l'API CallMeBot."""

    def __init__(self, phone: Optional[str] = None, api_key: Optional[str] = None):
        self.phone = phone or os.getenv("CALLMEBOT_PHONE")
        self.api_key = api_key or os.getenv("CALLMEBOT_API_KEY")
        self.site_url = os.getenv("SITE_URL", "https://mjacquiot.github.io/Calendrier-Citoyen/")
        self.enabled = bool(self.phone and self.api_key and self.phone != "+33600000000")

    @staticmethod
    def _format_sync_hour(generated_at: str) -> str:
        if not generated_at:
            return "--:--"
        try:
            dt = datetime.fromisoformat(generated_at)
            return dt.strftime("%Hh%M")
        except ValueError:
            return "--:--"

    def build_summary_message(
        self,
        metadata: Dict[str, Any],
        today_events: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Construit le texte complet de la synthèse quotidienne."""
        counts = metadata.get("counts", {})
        commune = metadata.get("commune", "Dunières")
        today_date = metadata.get("reference_date", "")
        sync_hour = self._format_sync_hour(metadata.get("generated_at", ""))

        sw = metadata.get("sliding_window", {})
        retro_days = sw.get("retrospective_days", 7)
        up_days = sw.get("upcoming_days", 7)

        cls_stats = metadata.get("classifier_stats", {})
        mode_raw = cls_stats.get("mode", "heuristic")
        mode_label = "Gemini IA" if mode_raw == "gemini" else "Heuristique"

        lines = [
            f"🏛️ *Portail Citoyen {commune} - Synthèse du {today_date}*",
            "",
            f"📊 *Bilan collecte ({sync_hour}, {mode_label}) :*",
            f"• Publications analysées : {counts.get('total_analyzed', 0)}",
            f"• Retenues (intérêt public) : {counts.get('total_accepted', 0)}",
            f"• Écartées (faits divers/privé) : {counts.get('total_rejected', 0)}",
            "",
            f"📅 *Calendrier glissant (-{retro_days}j / +{up_days}j) :*",
            f"• ⏪ Passés (-{retro_days}j) : {counts.get('retrospective', 0)}",
            f"• 📍 Aujourd'hui : {counts.get('today', 0)}",
            f"• ⏩ À venir (+{up_days}j) : {counts.get('upcoming', 0)}",
        ]

        # Alerte si des sources ont retourné une erreur ou 0 item
        sources_health = metadata.get("sources_health") or {}
        unhealthy = [
            f"{info.get('name', sid)} ({info.get('status')})"
            for sid, info in sources_health.items()
            if isinstance(info, dict) and info.get("status") in ("error", "empty")
        ]
        if unhealthy:
            lines.append("")
            lines.append("🔧 *État des sources à surveiller :*")
            for u in unhealthy:
                lines.append(f"• {u}")

        events = today_events or []
        priority_alerts = [
            ev for ev in events
            if ev.get("importance") == "high"
            or ev.get("category") in ("Alertes & Météo", "Travaux & Voirie")
        ]
        normal_today = [ev for ev in events if ev not in priority_alerts]

        if priority_alerts:
            lines.append("")
            lines.append("⚠️ *Alertes prioritaires du jour :*")
            for a in priority_alerts[:4]:
                lines.append(f"• {a.get('title')}")

        if normal_today:
            lines.append("")
            lines.append("📌 *Au programme aujourd'hui :*")
            for ev in normal_today[:4]:
                st = (ev.get("timing") or {}).get("start_time")
                prefix = f"[{st}] " if st else ""
                lines.append(f"• {prefix}{ev.get('title')}")

        lines.append("")
        lines.append(f"🌐 {self.site_url}")
        return "\n".join(lines)

    def send_daily_summary(
        self,
        metadata: Dict[str, Any],
        today_events: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Envoie le compte-rendu matinal de la collecte à l'élu."""
        if not self.enabled:
            logger.info("Notifications WhatsApp désactivées (CALLMEBOT_PHONE ou CALLMEBOT_API_KEY non configurés).")
            return False

        message = self.build_summary_message(metadata, today_events)
        return self._send_whatsapp(message)

    def _send_whatsapp(self, message: str) -> bool:
        encoded_msg = urllib.parse.quote(message)
        phone_clean = self.phone.replace("+", "").replace(" ", "").strip()
        url = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={phone_clean}&text={encoded_msg}&apikey={self.api_key}"
        )

        logger.info(f"Envoi du compte-rendu WhatsApp au numéro {self.phone[:6]}***...")
        status, res = fetch_url_with_status(url, timeout=10)
        if status == 200 and res is not None:
            low = res.lower()
            if "error" not in low and "invalid" not in low:
                logger.info("Notification WhatsApp délivrée avec succès.")
                return True

        logger.warning(f"Échec ou réponse inattendue CallMeBot (HTTP {status}): {res}")
        return False
