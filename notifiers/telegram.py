import html
import logging
import time
from typing import List, Dict, Any
import requests

from config import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID

    def _format_job(self, job: Dict[str, Any]) -> str:
        title = html.escape(job.get("title", "No Title"))
        company = html.escape(job.get("company", "Unknown"))
        location = html.escape(job.get("location", "N/A"))
        work_mode = html.escape(job.get("work_mode", "N/A"))
        source = html.escape(job.get("source", "Unknown"))
        url = job.get("url", "")

        msg = (
            f"<b>{title}</b>\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"📍 <b>Location:</b> {location}\n"
            f"💼 <b>Mode:</b> {work_mode}\n"
            f"🌐 <b>Source:</b> {source}\n"
        )
        if url:
            msg += f"🔗 <a href=\"{html.escape(url)}\">Apply Here</a>"
        return msg

    def _send_message(self, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        retries = 0
        backoff = 1.0
        while retries <= 3:
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                elif resp.status_code == 429:
                    try:
                        retry_after = resp.json().get("parameters", {}).get("retry_after", backoff)
                    except Exception:
                        retry_after = backoff
                    logger.warning(f"Telegram rate limited (429). Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    retries += 1
                    backoff *= 2
                else:
                    logger.error(f"Telegram send failed with status {resp.status_code}: {resp.text}")
                    return False
            except Exception as e:
                logger.error(f"Telegram request exception: {e}")
                time.sleep(backoff)
                retries += 1
                backoff *= 2
        return False

    def send_jobs(self, jobs: List[Dict[str, Any]]) -> bool:
        if not self.bot_token or not self.chat_id or not jobs:
            return False

        success = True
        for job in jobs:
            text = self._format_job(job)
            if not self._send_message(text):
                success = False
            time.sleep(0.05)
        return success
