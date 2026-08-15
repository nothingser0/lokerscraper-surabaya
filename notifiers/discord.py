import logging
import time
from typing import List, Dict, Any
import requests

from config import config
from utils.text import format_date_id, format_salary_id, format_job_type_id

logger = logging.getLogger(__name__)

COLOR_MAP = {
    "kalibrr": 0x00A8FF,
    "jobstreet": 0x6C5CE7,
    "glints": 0xFF7675,
    "linkedin": 0x0A66C2,
    "sejutacita": 0x00B894,
}

SOURCE_EMOJI = {
    "kalibrr": "🟦",
    "jobstreet": "🟪",
    "glints": "🟥",
    "linkedin": "🔷",
    "sejutacita": "🟩",
}

_FIELD_MAX_LEN = 28


def _clip(value: str, max_len: int = _FIELD_MAX_LEN) -> str:
    """Truncate long values so inline field boxes stay even."""
    value = (value or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


class DiscordNotifier:
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or config.DISCORD_WEBHOOK_URL

    def _job_to_embed(self, job: Dict[str, Any]) -> Dict[str, Any]:
        source = (job.get("source") or "unknown").lower()
        source_label = job.get("source", "Unknown").capitalize()
        color = COLOR_MAP.get(source, 0x7289DA)
        emoji = SOURCE_EMOJI.get(source, "🔹")

        title = job.get("title", "No Title")
        url = job.get("url", "")
        company = job.get("company", "Unknown")
        location = job.get("location", "N/A")
        salary = format_salary_id(job.get("salary", "Not disclosed"))
        work_mode = job.get("work_mode", "N/A")
        job_type = format_job_type_id(job.get("type", "N/A"))
        posted_at = format_date_id(job.get("posted_at", "N/A"))

        # 2 rows x 3 columns of inline fields, compact Indonesian labels.
        embed = {
            "title": title,
            "url": url if url else None,
            "color": color,
            "author": {
                "name": f"{emoji} {source_label}",
            },
            "fields": [
                {"name": "Perusahaan", "value": _clip(company), "inline": True},
                {"name": "Gaji", "value": _clip(salary), "inline": True},
                {"name": "Tgl", "value": _clip(posted_at), "inline": True},
                {"name": "Lokasi", "value": _clip(location), "inline": True},
                {"name": "Tipe", "value": _clip(job_type), "inline": True},
                {"name": "Mode", "value": _clip(work_mode), "inline": True},
            ],
            "footer": {
                "text": f"LokerScraper Surabaya"
            }
        }
        return {k: v for k, v in embed.items() if v is not None}


    def _send_payload(self, payload: Dict[str, Any]) -> bool:
        retries = 0
        backoff = 1.0
        while retries <= 3:
            try:
                resp = requests.post(self.webhook_url, json=payload, timeout=10)
                if resp.status_code in (200, 204):
                    return True
                elif resp.status_code == 429:
                    try:
                        retry_after = resp.json().get("retry_after", backoff)
                    except Exception:
                        retry_after = backoff
                    logger.warning(f"Discord rate limited (429). Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    retries += 1
                    backoff *= 2
                else:
                    logger.error(f"Discord webhook failed with status {resp.status_code}: {resp.text}")
                    return False
            except Exception as e:
                logger.error(f"Discord request exception: {e}")
                time.sleep(backoff)
                retries += 1
                backoff *= 2
        return False

    def send_jobs(self, jobs: List[Dict[str, Any]]) -> bool:
        if not self.webhook_url:
            logger.warning("Discord webhook URL is empty; skipping notification.")
            return False
        if not jobs:
            return False

        logger.info(f"Sending {len(jobs)} job(s) to Discord in batches of 10.")
        success = True
        batch_size = 10
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i:i + batch_size]
            embeds = [self._job_to_embed(j) for j in batch]
            payload = {"embeds": embeds}
            if not self._send_payload(payload):
                success = False
        if success:
            logger.info(f"Discord notification sent successfully for {len(jobs)} job(s).")
        return success
