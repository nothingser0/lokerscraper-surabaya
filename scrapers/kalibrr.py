import hashlib
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class KalibrrScraper(BaseScraper):
    ENDPOINT = "https://www.kalibrr.com/kjs/job_board/search"

    @property
    def source_name(self) -> str:
        return "Kalibrr"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

    def _format_salary(self, min_sal: Any, max_sal: Any) -> str:
        if not min_sal and not max_sal:
            return "Not disclosed"
        
        def to_m(val):
            if not val:
                return None
            val_num = float(val)
            if val_num >= 1_000_000:
                return f"{val_num / 1_000_000:.1f}".rstrip('0').rstrip('.') + "M"
            return str(int(val_num))

        min_str = to_m(min_sal)
        max_str = to_m(max_sal)

        if min_str and max_str:
            return f"IDR {min_str} - {max_str}"
        elif min_str:
            return f"IDR {min_str}+"
        elif max_str:
            return f"IDR up to {max_str}"
        return "Not disclosed"

    def _get_work_mode(self, job: Dict[str, Any]) -> str:
        if job.get("is_work_from_home"):
            return "Remote"
        elif job.get("is_hybrid"):
            return "Hybrid"
        return "On-site"

    def _get_location(self, job: Dict[str, Any]) -> str:
        google_loc = job.get("google_location", {})
        if isinstance(google_loc, dict):
            address_comps = google_loc.get("address_components", {})
            if isinstance(address_comps, dict) and "city" in address_comps:
                return address_comps["city"]
        return "Surabaya"

    def _format_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            # Parses e.g. "2026-08-14T08:00:00Z" or similar
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return date_str[:10] if len(date_str) >= 10 else date_str

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()

        for kw in config.IT_KEYWORDS:
            params = {
                "keyword": kw,
                "location": "Surabaya",
                "limit": 20,
                "offset": 0
            }
            try:
                response = requests.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Kalibrr returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                jobs_data = data.get("jobs", []) if isinstance(data, dict) else []

                for job in jobs_data:
                    raw_id = job.get("id")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    location_str = self._get_location(job)
                    
                    # Filter location
                    loc_lower = location_str.lower()
                    allowed_locations = [loc.lower() for loc in config.LOCATIONS]
                    if not any(loc in loc_lower for loc in allowed_locations):
                        # Extra check: job description or title location
                        if not any(loc in job.get("name", "").lower() for loc in allowed_locations):
                            continue

                    # Hash ID
                    hash_str = f"{self.source_name}{raw_id}"
                    job_hash_id = f"kalibrr_{hashlib.md5(hash_str.encode()).hexdigest()[:12]}"

                    company_name = job.get("company_name", "Unknown")
                    company_code = job.get("company_code") or job.get("company_info", {}).get("code") or "company"
                    job_slug = job.get("slug") or str(raw_id)
                    job_url = f"https://www.kalibrr.com/c/{company_code}/jobs/{raw_id}/{job_slug}"

                    item = {
                        "id": job_hash_id,
                        "source": self.source_name,
                        "title": job.get("name", "Untitled"),
                        "company": company_name,
                        "location": location_str,
                        "salary": self._format_salary(job.get("base_salary"), job.get("maximum_salary")),
                        "type": job.get("tenure", "Full-time") or "Full-time",
                        "work_mode": self._get_work_mode(job),
                        "url": job_url,
                        "posted_at": self._format_date(job.get("created_at", "")),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "keyword": kw
                    }

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping Kalibrr for keyword {kw}: {e}")

        return scraped_jobs
