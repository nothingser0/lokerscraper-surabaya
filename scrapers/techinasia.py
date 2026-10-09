import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class TechInAsiaScraper(BaseScraper):
    ENDPOINT = "https://www.techinasia.com/api/2.0/job-postings"

    @property
    def source_name(self) -> str:
        return "TechInAsia"

    def __init__(self):
        super().__init__()
        self.request_delay = 1.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.techinasia.com/jobs",
        }

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()

        for kw in config.KEYWORDS:
            params = {
                "query": kw,
                "country_name": "Indonesia",
                "page": 1,
                "per_page": 20,
            }

            try:
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"TechInAsia returned {response.status_code} for keyword {kw}")
                    continue

                payload = response.json()
                job_list = payload.get("data", [])
                if not isinstance(job_list, list):
                    continue

                for job in job_list:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title = job.get("title") or "Untitled"
                    
                    company_data = job.get("company")
                    company_name = "Unknown Company"
                    logo_url = None
                    company_industry = None
                    if isinstance(company_data, dict):
                        company_name = company_data.get("name") or "Unknown Company"
                        logo_url = company_data.get("logo_url")
                        company_industry = company_data.get("industry")

                    locations = job.get("locations")
                    location_str = "Indonesia"
                    if isinstance(locations, list) and locations:
                        loc_names = [str(l["name"]) for l in locations if isinstance(l, dict) and l.get("name")]
                        if loc_names:
                            location_str = ", ".join(loc_names)

                    is_remote = bool(job.get("is_remote"))
                    work_arrangement = str(job.get("work_arrangement") or "").lower()
                    if is_remote or "remote" in work_arrangement:
                        work_mode = "Remote"
                    elif "hybrid" in work_arrangement:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    job_type_data = job.get("job_type")
                    work_type = None
                    if isinstance(job_type_data, dict):
                        work_type = job_type_data.get("name")

                    salary_min = job.get("salary_min")
                    salary_max = job.get("salary_max")
                    currency = "IDR"
                    curr_obj = job.get("currency")
                    if isinstance(curr_obj, dict):
                        currency = curr_obj.get("currency_code") or "IDR"

                    posted_at = job.get("created_at")
                    if posted_at and isinstance(posted_at, str):
                        posted_at = posted_at[:10]

                    job_url = f"https://www.techinasia.com/jobs/{raw_id}"

                    item = new_job_dict(
                        raw_id=raw_id,
                        source=self.source_name,
                        title=sanitize_text(title),
                        company=sanitize_text(company_name),
                        logo_url=logo_url,
                        company_industry=company_industry,
                        location=sanitize_text(location_str),
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_currency=currency,
                        work_type=work_type,
                        work_mode=work_mode,
                        posted_at=posted_at,
                        job_description=job.get("description"),
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping TechInAsia for keyword {kw}: {e}")

        return scraped_jobs
