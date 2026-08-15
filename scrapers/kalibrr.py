import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper
from utils.text import sanitize_text, format_salary_id

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
            try:
                val_num = float(val)
                if val_num >= 1_000_000:
                    return f"{val_num / 1_000_000:.1f}".rstrip('0').rstrip('.') + "M"
                return str(int(val_num))
            except (ValueError, TypeError):
                return None

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
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"
        google_loc = job.get("google_location")
        if isinstance(google_loc, dict):
            address_comps = google_loc.get("address_components")
            if isinstance(address_comps, dict) and "city" in address_comps:
                city = address_comps.get("city")
                if isinstance(city, str) and city:
                    return city
        return default_loc

    def _format_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return date_str[:10] if len(date_str) >= 10 else date_str

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"

        for kw in config.IT_KEYWORDS:
            params = {
                "keyword": kw,
                "location": default_loc,
                "limit": 20,
                "offset": 0
            }
            try:
                response = self.session.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Kalibrr returned status {response.status_code} for keyword {kw}")
                    continue

                data = response.json()
                jobs_data = data.get("jobs", []) if isinstance(data, dict) else []
                if not isinstance(jobs_data, list):
                    continue

                for job in jobs_data:
                    if not isinstance(job, dict):
                        continue
                    raw_id = job.get("id")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    location_str = self._get_location(job)
                    
                    loc_lower = location_str.lower()
                    allowed_locations = [loc.lower() for loc in config.LOCATIONS]
                    job_name = job.get("name")
                    job_name_str = job_name if isinstance(job_name, str) else ""
                    if not any(loc in loc_lower for loc in allowed_locations):
                        if not any(loc in job_name_str.lower() for loc in allowed_locations):
                            continue

                    company_name = job.get("company_name")
                    company_name = company_name if isinstance(company_name, str) else "Unknown"
                    
                    company_info = job.get("company_info")
                    company_code = (
                        job.get("company_code") 
                        or (company_info.get("code") if isinstance(company_info, dict) else None)
                        or "company"
                    )
                    
                    slug = job.get("slug")
                    job_slug = slug if isinstance(slug, str) else str(raw_id)
                    job_url = f"https://www.kalibrr.com/c/{company_code}/jobs/{raw_id}/{job_slug}"

                    tenure = job.get("tenure")
                    job_type = tenure if isinstance(tenure, str) and tenure else "Full-time"

                    created_at = job.get("created_at")
                    created_at_str = created_at if isinstance(created_at, str) else ""

                    item = {
                        "raw_id": str(raw_id),
                        "source": self.source_name,
                        "title": sanitize_text(job_name_str or "Untitled"),
                        "company": sanitize_text(company_name),
                        "location": sanitize_text(location_str),
                        "salary": format_salary_id(self._format_salary(job.get("base_salary"), job.get("maximum_salary"))),
                        "type": sanitize_text(job_type),
                        "work_mode": self._get_work_mode(job),
                        "url": job_url,
                        "posted_at": self._format_date(created_at_str),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "keyword": kw
                    }

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping Kalibrr for keyword {kw}: {e}")

        return scraped_jobs
