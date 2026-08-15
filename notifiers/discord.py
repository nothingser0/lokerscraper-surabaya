import logging
import time
from typing import List, Dict, Any
import requests

from config import config

logger = logging.getLogger(__name__)

COLOR_MAP = {
    "kalibrr": 0x00A8FF,
    "jobstreet": 0x6C5CE7,
    "glints": 0xFF7675,
    "linkedin": 0x0A66C2,
    "sejutacita": 0x00B894,
}

class DiscordNotifier:
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or config.DISCORD_WEBHOOK_URL

    def _job_to_embed(self, job: Dict[str, Any]) -> Dict[str, Any]:
        source = (job.get("source") or "unknown").lower()
        color = COLOR_MAP.get(source, 0x7289DA)
        
        title = job.get("title", "No Title")
        url = job.get("url", "")
        company = job.get("company", "Unknown")
        location = job.get("location", "N/A")
        salary = job.get("salary", "Not disclosed")
        work_mode = job.get("work_mode", "N/A")
        job_type = job.get("type", "N/A")
        posted_at = job.get("posted_at", "N/A")

        embed = {
            "title": title,
            "url": url if url else None,
            "color": color,
            "fields": [
                {"name": "Company", "value": company, "inline": True},
                {"name": "Location", "value": location, "inline": True},
                {"name": "Salary", "value": salary, "inline": True},
                {"name": "Work Mode", "value": work_mode, "inline": True},
                {"name": "Job Type", "value": job_type, "inline": True},
                {"name": "Posted Date", "value": posted_at, "inline": True},
                {"name": "Source", "value": job.get("source", "Unknown"), "inline": True},
            ],
            "footer": {
                "text": f"LokerScraper Surabaya • {job.get('source', 'JobScraper')}"
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
        if not self.webhook_url or not jobs:
            return False

        success = True
        batch_size = 10
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i:i + batch_size]
            embeds = [self._job_to_embed(j) for j in batch]
            payload = {"embeds": embeds}
            if not self._send_payload(payload):
                success = False
        return success
