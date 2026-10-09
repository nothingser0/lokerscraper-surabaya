import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class KarirScraper(BaseScraper):
    ENDPOINT = "https://gateway2-beta.karir.com/v2/search/opportunities"

    @property
    def source_name(self) -> str:
        return "Karir"

    def __init__(self):
        super().__init__()
        self.request_delay = 1.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://karir.com",
            "Referer": "https://karir.com/",
        }

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()

        for kw in config.KEYWORDS:
            payload = {
                "keyword": kw,
                "locale": "id",
                "limit": 20,
                "offset": 0,
            }
            try:
                response = self.session.post(self.ENDPOINT, headers=self.headers, data=json.dumps(payload), timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Karir returned status {response.status_code} for keyword {kw}")
                    continue

                body = response.json()
                opportunities = body.get("data", {}).get("opportunities", []) if isinstance(body, dict) else []
                if not isinstance(opportunities, list):
                    continue

                for job in opportunities:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title = job.get("job_position") or "Untitled"
                    company = job.get("company_name") or "Unknown Company"
                    logo_url = job.get("company_logo_url")
                    location = job.get("description") or "Indonesia"

                    sal_min = job.get("salary_lower")
                    sal_max = job.get("salary_upper")

                    posted_at = None
                    posted_raw = str(job.get("posted_at") or "")
                    if len(posted_raw) >= 10:
                        posted_at = posted_raw[:10]

                    item = new_job_dict(
                        raw_id=raw_id,
                        source=self.source_name,
                        title=sanitize_text(title),
                        company=sanitize_text(company),
                        logo_url=logo_url,
                        location=sanitize_text(location),
                        salary_min=sal_min,
                        salary_max=sal_max,
                        salary_currency="IDR",
                        posted_at=posted_at,
                        url=f"https://karir.com/opportunities/{raw_id}",
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping Karir for keyword {kw}: {e}")

        return scraped_jobs
