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

    for webhook_url in _discord_webhook_urls():
        try:
            discord = DiscordNotifier(webhook_url)
            discord.send_jobs(jobs)
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")


def notify_scraper_error(errors: List[str]) -> None:
    """Send a system alert embed to Discord webhook if scrapers encounter repeated failures."""
    if not errors:
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "embeds": [
            {
                "title": "🚨 Scraper Consecutive Failure Alert",
                "description": "Platform scraper berikut telah mengalami kegagalan **>= 3 siklus berturut-turut**:\n\n" + "\n".join(f"• **{err}**" for err in errors),
                "color": 0xE74C3C,  # Discord Red
                "footer": {
                    "text": f"LokerScraper Surabaya • System Alert • {now_str}"
                }
            }
        ]
    }
    for webhook_url in _discord_webhook_urls():
        try:
            import requests
            requests.post(webhook_url, json=payload, timeout=8)
        except Exception as e:
            logger.error(f"Error sending Discord error notification: {e}")


__all__ = ["DiscordNotifier", "TelegramNotifier", "notify_new_jobs", "notify_scraper_error"]
