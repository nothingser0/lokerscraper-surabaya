import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from .discord import DiscordNotifier
from .telegram import TelegramNotifier

logger = logging.getLogger(__name__)

def _discord_webhook_urls() -> List[str]:
    """Return the full list of Discord webhook URLs to notify.

    Prefers the comma-separated DISCORD_WEBHOOK_URLS list; falls back to the
    single DISCORD_WEBHOOK_URL for backward compatibility. Duplicates removed.
    """
    urls: List[str] = []
    for u in getattr(config, "DISCORD_WEBHOOK_URLS", []) or []:
        if u:
            urls.append(u)
    if not urls and config.DISCORD_WEBHOOK_URL:
        urls.append(config.DISCORD_WEBHOOK_URL)
    # Preserve order while dropping duplicates.
    seen = set()
    unique: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def notify_new_jobs(jobs: List[Dict[str, Any]]) -> None:
    if not jobs:
        return

    # 1. Notify Discord webhooks
    for webhook_url in _discord_webhook_urls():
        try:
            discord = DiscordNotifier(webhook_url)
            discord.send_jobs(jobs)
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")

    # 2. Notify Telegram if token & chat_id are set and not placeholder
    bot_token = (getattr(config, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = (getattr(config, "TELEGRAM_CHAT_ID", "") or "").strip()
    placeholder_tokens = {"123456789:ABCdefGHIjklMNOpqrsTUVwxyz", "your_telegram_bot_token", "your_bot_token"}
    placeholder_chats = {"-100123456789", "your_telegram_chat_id", "your_chat_id"}
    if bot_token and chat_id and bot_token not in placeholder_tokens and chat_id not in placeholder_chats:
        try:
            telegram = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
            telegram.send_jobs(jobs)
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

def notify_scraper_error(errors: List[str]) -> None:
    """Send a system alert to the DEDICATED error channel(s).

    Kept separate from job notifications so operational alerts never mix with
    vacancy postings. Falls back to the job channels when no dedicated error
    webhook/chat is configured, so existing setups keep working.
    """
    if not errors:
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    description = "Platform scraper berikut gagal **>= 3 siklus berturut-turut**:\n\n" + "\n".join(f"• **{err}**" for err in errors)

    # 1. Discord system-alert webhook (fallback: job webhooks)
    error_webhook = (getattr(config, "DISCORD_ERROR_WEBHOOK_URL", "") or "").strip()
    webhook_urls = [error_webhook] if error_webhook else _discord_webhook_urls()
    payload = {
        "embeds": [
            {
                "title": "🚨 Scraper Consecutive Failure Alert",
                "description": description,
                "color": 0xE74C3C,  # Discord Red
                "footer": {
                    "text": f"LokerScraper Surabaya • System Alert • {now_str}"
                }
            }
        ]
    }
    for webhook_url in webhook_urls:
        try:
            import requests
            requests.post(webhook_url, json=payload, timeout=8)
        except Exception as e:
            logger.error(f"Error sending Discord error notification: {e}")

    # 2. Telegram system-alert chat (fallback: job chat)
    bot_token = (getattr(config, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    error_chat = (getattr(config, "TELEGRAM_ERROR_CHAT_ID", "") or "").strip()
    chat_id = error_chat or (getattr(config, "TELEGRAM_CHAT_ID", "") or "").strip()
    placeholder_tokens = {"123456789:ABCdefGHIjklMNOpqrsTUVwxyz", "your_telegram_bot_token", "your_bot_token"}
    placeholder_chats = {"-100123456789", "your_telegram_chat_id", "your_chat_id"}
    if bot_token and chat_id and bot_token not in placeholder_tokens and chat_id not in placeholder_chats:
        try:
            import requests
            text = f"🚨 <b>Scraper Failure Alert</b>\n\n{description}\n\n<i>{now_str}</i>"
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Error sending Telegram error notification: {e}")


__all__ = ["DiscordNotifier", "TelegramNotifier", "notify_new_jobs", "notify_scraper_error"]
