import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class SejutaCitaScraper(BaseScraper):
    ENDPOINT = "https://api.sejutacita.id/v1/explore-job/job"

    @property
    def source_name(self) -> str:
        return "SejutaCita"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"

        for kw in config.IT_KEYWORDS:
            params = {
                "cityIds[0]": "265",
                "published": "true",
                "limit": 20,
                "q": kw,
            }
            try:
                response = self.session.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"SejutaCita returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                data_obj = data.get("data") if isinstance(data, dict) else {}
                jobs_data = []
                if isinstance(data_obj, dict):
                    docs = data_obj.get("docs")
                    if isinstance(docs, list):
                        jobs_data = docs
                elif isinstance(data_obj, list):
                    jobs_data = data_obj

                if not isinstance(jobs_data, list):
                    continue

                for job in jobs_data:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or job.get("_id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    raw_title = job.get("role") or job.get("title")
                    title = raw_title if isinstance(raw_title, str) else "Untitled"

                    company_data = job.get("company")
                    if isinstance(company_data, dict):
                        comp_name = company_data.get("name")
                        company = comp_name if isinstance(comp_name, str) else "Unknown"
                    else:
                        company = str(company_data) if company_data else "Unknown"

                    city_data = job.get("city")
                    if isinstance(city_data, dict):
                        city_name = city_data.get("name")
                        location_str = city_name if isinstance(city_name, str) else default_loc
                    else:
                        location_str = str(city_data) if city_data else default_loc

                    salary_range = job.get("salaryRange")
                    salary = str(salary_range) if salary_range else "Not disclosed"

                    workplace_type = str(job.get("workplaceType") or "").lower()
                    if "remote" in workplace_type:
                        work_mode = "Remote"
                    elif "hybrid" in workplace_type:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    slug = job.get("slug") or raw_id
                    job_url = f"https://sejutacita.id/job/{slug}"

                    published_at = job.get("publishedAt") or job.get("createdAt")
                    published_at_str = published_at if isinstance(published_at, str) else ""
                    posted_at = published_at_str[:10] if len(published_at_str) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    job_type = job.get("employmentType") or job.get("type")
                    type_str = job_type if isinstance(job_type, str) and job_type else "Full-time"

                    item = {
                        "raw_id": raw_id,
                        "source": self.source_name,
                        "title": sanitize_text(title),
                        "company": sanitize_text(company),
                        "location": sanitize_text(location_str),
                        "salary": sanitize_text(salary),
                        "type": sanitize_text(type_str),
                        "work_mode": work_mode,
                        "url": job_url,
                        "posted_at": posted_at,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    }

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping SejutaCita for keyword {kw}: {e}")

        return scraped_jobs
