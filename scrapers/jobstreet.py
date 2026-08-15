import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper
from utils.text import sanitize_text

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
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"

        for kw in config.IT_KEYWORDS:
            params = {
                "siteKey": "ID-Main",
                "sourcesystem": "chalice",
                "where": default_loc,
                "pageSize": 20,
                "keywords": kw,
            }
            try:
                response = self.session.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"JobStreet returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                job_list = data.get("data", []) if isinstance(data, dict) else []
                if not isinstance(job_list, list):
                    continue

                for job in job_list:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    raw_title = job.get("title")
                    title = raw_title if isinstance(raw_title, str) else "Untitled"

                    advertiser = job.get("advertiser")
                    if isinstance(advertiser, dict):
                        raw_company = advertiser.get("description")
                        company = raw_company if isinstance(raw_company, str) else "Unknown"
                    else:
                        company = "Unknown"

                    locations = job.get("locations")
                    location_str = default_loc
                    if isinstance(locations, list) and locations and isinstance(locations[0], dict):
                        raw_loc = locations[0].get("label")
                        if isinstance(raw_loc, str) and raw_loc:
                            location_str = raw_loc

                    salary_raw = job.get("salaryLabel")
                    salary = salary_raw if isinstance(salary_raw, str) and salary_raw else "Not disclosed"

                    work_arrangements_obj = job.get("workArrangements")
                    work_arrangements = work_arrangements_obj.get("data", []) if isinstance(work_arrangements_obj, dict) else []
                    work_mode = "On-site"
                    if isinstance(work_arrangements, list) and work_arrangements:
                        arr_labels = []
                        for arr in work_arrangements:
                            if isinstance(arr, dict):
                                lbl = arr.get("label")
                                if isinstance(lbl, dict):
                                    text = lbl.get("text")
                                    if isinstance(text, str):
                                        arr_labels.append(text)
                                elif isinstance(lbl, str):
                                    arr_labels.append(lbl)
                        arr_str = " ".join(arr_labels).lower()
                        if "remote" in arr_str:
                            work_mode = "Remote"
                        elif "hybrid" in arr_str:
                            work_mode = "Hybrid"

                    job_url = f"https://id.jobstreet.com/job/{raw_id}"

                    listing_date = job.get("listingDate")
                    listing_date_str = listing_date if isinstance(listing_date, str) else ""
                    posted_at = listing_date_str[:10] if len(listing_date_str) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    item = {
                        "raw_id": raw_id,
                        "source": self.source_name,
                        "title": sanitize_text(title),
                        "company": sanitize_text(company),
                        "location": sanitize_text(location_str),
                        "salary": sanitize_text(salary),
                        "type": "Full-time",
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
