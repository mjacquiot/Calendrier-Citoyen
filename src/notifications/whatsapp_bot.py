"""
Module de notification WhatsApp (CallMeBot) pour l'élu local.
Envoie un résumé quotidien d'exécution et les alertes majeures du jour.
"""

import os
import logging
import urllib.parse
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from src.utils.http_client import fetch_url

load_dotenv()
logger = logging.getLogger(__name__)


class WhatsAppNotifier:
    """Envoie des notifications WhatsApp à l'élu via l'API CallMeBot."""

    def __init__(self, phone: Optional[str] = None, api_key: Optional[str] = None):
        self.phone = phone or os.getenv("CALLMEBOT_PHONE")
        self.api_key = api_key or os.getenv("CALLMEBOT_API_KEY")
        self.enabled = bool(self.phone and self.api_key and self.phone != "+33600000000")

    def send_daily_summary(self, metadata: Dict[str, Any], alerts_today: list = None) -> bool:
        """Envoie le compte-rendu matinal de la collecte à l'élu."""
        if not self.enabled:
            logger.info("Notifications WhatsApp désactivées (CALLMEBOT_PHONE ou CALLMEBOT_API_KEY non configurés).")
            return False

        counts = metadata.get("counts", {})
        commune = metadata.get("commune", "Dunières")
        today_date = metadata.get("reference_date", "")

        lines = [
            f"🏛️ *Portail Citoyen {commune} - Synthèse du {today_date}*",
            "",
            f"📊 *Bilan de la collecte 6h00 :*",
            f"• Publications analysées : {counts.get('total_analyzed', 0)}",
            f"• Retenues (intérêt public) : {counts.get('total_accepted', 0)}",
            f"• Écartées (faits divers/privé) : {counts.get('total_rejected', 0)}",
            "",
            f"📅 *Calendrier glissant :*",
            f"• ⏪ Rétrospective (-15j) : {counts.get('retrospective', 0)}",
            f"• 📍 Aujourd'hui : {counts.get('today', 0)}",
            f"• ⏩ Agenda à venir (+15j) : {counts.get('upcoming', 0)}"
        ]

        if alerts_today:
            lines.append("")
            lines.append("⚠️ *Alertes & Urgences du jour :*")
            for a in alerts_today[:3]:
                lines.append(f"• {a.get('title')}")

        lines.append("")
        lines.append("🌐 Portail à jour sur GitHub Pages.")

        message = "\n".join(lines)
        return self._send_whatsapp(message)

    def _send_whatsapp(self, message: str) -> bool:
        encoded_msg = urllib.parse.quote(message)
        phone_clean = self.phone.replace("+", "").replace(" ", "").strip()
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone_clean}&text={encoded_msg}&apikey={self.api_key}"

        logger.info(f"Envoi du compte-rendu WhatsApp au numéro {self.phone[:6]}***...")
        res = fetch_url(url, timeout=10)
        if res and ("success" in res.lower() or "message sent" in res.lower() or "200" in res):
            logger.info("Notification WhatsApp délivrée avec succès.")
            return True
        else:
            logger.warning(f"Réponse CallMeBot : {res}")
            return False
