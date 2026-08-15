import hashlib
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper

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

        for kw in config.IT_KEYWORDS:
            params = {
                "cityIds[0]": "265",
                "published": "true",
                "limit": 20,
                "q": kw,
            }
            try:
                response = requests.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"SejutaCita returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                data_obj = data.get("data", {})
                jobs_data = data_obj.get("docs", []) if isinstance(data_obj, dict) else (data.get("data", []) if isinstance(data.get("data"), list) else [])

                for job in jobs_data:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or job.get("_id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title = job.get("role") or job.get("title") or "Untitled"

                    company_data = job.get("company")
                    if isinstance(company_data, dict):
                        company = company_data.get("name", "Unknown")
                    else:
                        company = str(company_data) if company_data else "Unknown"

                    city_data = job.get("city")
                    if isinstance(city_data, dict):
                        location_str = city_data.get("name", "Surabaya")
                    else:
                        location_str = str(city_data) if city_data else "Surabaya"

                    salary_range = job.get("salaryRange")
                    salary = str(salary_range) if salary_range else "Not disclosed"

                    workplace_type = str(job.get("workplaceType", "")).lower()
                    if "remote" in workplace_type:
                        work_mode = "Remote"
                    elif "hybrid" in workplace_type:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    slug = job.get("slug") or raw_id
                    job_url = f"https://sejutacita.id/job/{slug}"

                    published_at = job.get("publishedAt") or job.get("createdAt") or ""
                    posted_at = published_at[:10] if len(published_at) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    md5_hash = hashlib.md5(raw_id.encode("utf-8")).hexdigest()
                    job_hash_id = f"sejutacita_{md5_hash}"

                    item = {
                        "id": job_hash_id,
                        "title": title,
                        "company": company,
                        "location": location_str,
                        "salary": salary,
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
