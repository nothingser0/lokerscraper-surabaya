import hashlib
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class JobStreetScraper(BaseScraper):
    ENDPOINT = "https://id.jobstreet.com/api/jobsearch/v5/search"

    @property
    def source_name(self) -> str:
        return "JobStreet"

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
                "siteKey": "ID-Main",
                "sourcesystem": "chalice",
                "where": "Surabaya",
                "pageSize": 20,
                "keywords": kw,
            }
            try:
                response = requests.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"JobStreet returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                job_list = data.get("data", [])

                for job in job_list:
                    raw_id = str(job.get("id", ""))
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title = job.get("title", "Untitled")

                    # Advertiser / Company
                    advertiser = job.get("advertiser", {})
                    company = advertiser.get("description", "Unknown") if isinstance(advertiser, dict) else "Unknown"

                    # Locations
                    locations = job.get("locations", [])
                    if locations and isinstance(locations, list) and isinstance(locations[0], dict):
                        location_str = locations[0].get("label", "Surabaya")
                    else:
                        location_str = "Surabaya"

                    # Salary
                    salary = job.get("salaryLabel") or "Not disclosed"

                    # Work Mode / Arrangement
                    work_arrangements = job.get("workArrangements", {}).get("data", []) if isinstance(job.get("workArrangements"), dict) else []
                    work_mode = "On-site"
                    if work_arrangements:
                        arr_labels = [arr.get("label", {}).get("text", "") if isinstance(arr.get("label"), dict) else str(arr.get("label")) for arr in work_arrangements]
                        arr_str = " ".join(arr_labels).lower()
                        if "remote" in arr_str:
                            work_mode = "Remote"
                        elif "hybrid" in arr_str:
                            work_mode = "Hybrid"

                    # Job URL
                    job_url = f"https://id.jobstreet.com/job/{raw_id}"

                    # Posted Date
                    listing_date = job.get("listingDate", "")
                    posted_at = listing_date[:10] if len(listing_date) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    # Hash ID: jobstreet_{md5}
                    md5_hash = hashlib.md5(raw_id.encode("utf-8")).hexdigest()
                    job_hash_id = f"jobstreet_{md5_hash}"

                    item = {
                        "id": job_hash_id,
                        "source": self.source_name,
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
                logger.error(f"Error scraping JobStreet for keyword {kw}: {e}")

        return scraped_jobs
