import logging
from typing import List, Dict, Any

from config import config
from .discord import DiscordNotifier
from .telegram import TelegramNotifier

logger = logging.getLogger(__name__)

def notify_new_jobs(jobs: List[Dict[str, Any]]) -> None:
    if not jobs:
        return

    if config.DISCORD_WEBHOOK_URL:
        try:
            discord = DiscordNotifier()
            discord.send_jobs(jobs)
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")


__all__ = ["DiscordNotifier", "TelegramNotifier", "notify_new_jobs"]
