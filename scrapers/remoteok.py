import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class RemoteOKScraper(BaseScraper):
    ENDPOINT = "https://remoteok.com/api"

    @property
    def source_name(self) -> str:
        return "RemoteOK"

    def __init__(self):
        super().__init__()
        self.request_delay = 2.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()

        try:
            response = self._get(self.ENDPOINT, headers=self.headers, timeout=12)
            if response.status_code != 200:
                logger.warning(f"RemoteOK returned status {response.status_code}")
                return []

            payload = response.json()
            if not isinstance(payload, list):
                return []

            items = [item for item in payload if isinstance(item, dict) and item.get("id") and item.get("position")]

            for job in items:
                raw_id = str(job.get("id") or "")
                if not raw_id or raw_id in seen_job_ids:
                    continue

                title = job.get("position") or "Untitled Position"
                company = job.get("company") or "Unknown Company"
                logo_url = job.get("company_logo")
                url = job.get("url") or f"https://remoteok.com/remote-jobs/{raw_id}"
                
                location = job.get("location") or "Remote, Worldwide"
                work_mode = "Remote"
                
                sal_min = job.get("salary_min")
                sal_max = job.get("salary_max")
                
                posted_at = None
                date_epoch = job.get("epoch")
                if date_epoch and isinstance(date_epoch, (int, float)):
                    try:
                        posted_at = datetime.fromtimestamp(date_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                if not posted_at:
                    date_raw = str(job.get("date") or "")
                    if len(date_raw) >= 10:
                        posted_at = date_raw[:10]

                item = new_job_dict(
                    raw_id=raw_id,
                    source=self.source_name,
                    title=sanitize_text(title),
                    company=sanitize_text(company),
                    logo_url=logo_url,
                    location=sanitize_text(location),
                    salary_min=sal_min,
                    salary_max=sal_max,
                    salary_currency="USD",
                    work_type="Full-time",
                    work_mode=work_mode,
                    posted_at=posted_at,
                    job_description=job.get("description"),
                    url=url,
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                )

                scraped_jobs.append(item)
                seen_job_ids.add(raw_id)

        except Exception as e:
            logger.error(f"Error scraping RemoteOK: {e}")

        return scraped_jobs
