import logging
import time
from typing import List, Dict, Any
import requests

from config import config
from utils.text import (
    format_date_id,
    format_salary_id,
    format_job_type_id,
    format_work_mode_id,
    format_experience_id,
    format_description_id,
)

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
_FIELD_MAX_LEN_LONG = 700
# Discord caps a single message's total embed size at 6000 characters. Keep
# batches small and descriptions modest so a batch never exceeds the cap.
_BATCH_SIZE = 3


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
        source_label = job.get("source") or "Unknown"
        source = source_label.lower()
        source_label = source_label.capitalize()
        color = COLOR_MAP.get(source, 0x7289DA)
        emoji = SOURCE_EMOJI.get(source, "🔹")

        title = job.get("title") or "No Title"
        url = job.get("url", "")
        company = job.get("company") or "Unknown"
        location = job.get("location") or "N/A"

        # Format salary from min/max
        sal_min = job.get("salary_min")
        sal_max = job.get("salary_max")
        if sal_min or sal_max:
            sal_str = f"{sal_min or ''} - {sal_max or ''}"
            salary = format_salary_id(sal_str)
        else:
            salary = "Not disclosed"

        work_mode = format_work_mode_id(job.get("work_mode") or "N/A")
        work_type = format_job_type_id(job.get("work_type") or "N/A")
        posted_at = format_date_id(job.get("posted_at") or "N/A")

        fields = [
            {"name": "Perusahaan", "value": _clip(company), "inline": True},
            {"name": "Gaji", "value": _clip(salary), "inline": True},
            {"name": "Tgl", "value": _clip(posted_at), "inline": True},
            {"name": "Lokasi", "value": _clip(location), "inline": True},
            {"name": "Tipe", "value": _clip(work_type), "inline": True},
            {"name": "Mode", "value": _clip(work_mode), "inline": True},
        ]

        # Extra optional fields
        if job.get("company_industry"):
            fields.append({"name": "Industri", "value": _clip(job["company_industry"], 200), "inline": True})
        if job.get("experience"):
            fields.append({"name": "Pengalaman", "value": _clip(format_experience_id(job["experience"])), "inline": True})
        if job.get("education"):
            fields.append({"name": "Pendidikan", "value": _clip(job["education"]), "inline": True})
        if job.get("application_deadline"):
            fields.append({"name": "Batas Lamaran", "value": _clip(format_date_id(job["application_deadline"])), "inline": True})
        if job.get("applicant_count") is not None:
            fields.append({"name": "Pelamar", "value": str(job["applicant_count"]), "inline": True})
        if job.get("number_of_openings") is not None:
            fields.append({"name": "Kuota", "value": str(job["number_of_openings"]), "inline": True})
        if job.get("skills"):
            skills_str = ", ".join(job["skills"]) if isinstance(job["skills"], list) else str(job["skills"])
            fields.append({"name": "Skills", "value": _clip(skills_str, 300), "inline": False})
        if job.get("benefits"):
            benefits_str = ", ".join(job["benefits"]) if isinstance(job["benefits"], list) else str(job["benefits"])
            fields.append({"name": "Fasilitas", "value": _clip(benefits_str, 300), "inline": False})
        if job.get("job_description"):
            fields.append({"name": "Deskripsi", "value": format_description_id(job["job_description"], _FIELD_MAX_LEN_LONG), "inline": False})

        embed = {
            "title": title,
            "url": url if url else None,
            "color": color,
            "author": {
                "name": f"{emoji} {source_label}",
            },
            "fields": fields,
            "footer": {
                "text": f"LokerScraper Surabaya"
            }
        }

        logo_url = job.get("logo_url")
        if logo_url and isinstance(logo_url, str) and logo_url.startswith("http"):
            embed["thumbnail"] = {"url": logo_url}

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

        logger.info(f"Sending {len(jobs)} job(s) to Discord in batches of {_BATCH_SIZE}.")
        success = True
        batch_size = _BATCH_SIZE
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i:i + batch_size]
            embeds = [self._job_to_embed(j) for j in batch]
            payload = {"embeds": embeds}
            if not self._send_payload(payload):
                success = False
        if success:
            logger.info(f"Discord notification sent successfully for {len(jobs)} job(s).")
        return success
