import os
import httpx
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        if not self.enabled:
            logger.warning("Telegram not configured, skipping notification")
            return False
        try:
            url = TELEGRAM_API.format(token=self.token)
            resp = httpx.post(url, json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram notification sent")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
