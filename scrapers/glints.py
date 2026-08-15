import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class GlintsScraper(BaseScraper):
    ENDPOINT = "https://glints.com/id/opportunities/jobs/explore"

    @property
    def source_name(self) -> str:
        return "Glints"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _extract_next_data(self, html_content: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html_content, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                res = json.loads(script.string)
                return res if isinstance(res, dict) else {}
            except Exception as e:
                logger.error(f"Failed to parse __NEXT_DATA__ JSON in Glints: {e}")
        return {}

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"

        for kw in config.IT_KEYWORDS:
            params = {
                "keyword": kw,
                "country": "ID",
                "locationName": default_loc
            }
            try:
                response = self.session.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Glints returned status {response.status_code} for keyword {kw}")
                    continue

                next_data = self._extract_next_data(response.text)
                props = next_data.get("props") if isinstance(next_data, dict) else {}
                page_props = props.get("pageProps") if isinstance(props, dict) else {}

                jobs_data = []
                if isinstance(page_props, dict):
                    initial_jobs = page_props.get("initialJobs")
                    if isinstance(initial_jobs, dict):
                        jobs_data = initial_jobs.get("jobsInPage", [])
                    elif isinstance(initial_jobs, list):
                        jobs_data = initial_jobs

                    if not jobs_data:
                        init_state = page_props.get("initialState")
                        if isinstance(init_state, dict):
                            jobs_obj = init_state.get("jobs")
                            if isinstance(jobs_obj, dict):
                                jobs_data = jobs_obj.get("data", [])
                        if not jobs_data:
                            jobs_data = page_props.get("jobs", [])
                        if not jobs_data:
                            data_obj = page_props.get("data")
                            if isinstance(data_obj, dict):
                                jobs_data = data_obj.get("jobs", [])

                if not isinstance(jobs_data, list):
                    continue

                for job in jobs_data:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id") or "")
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title_raw = job.get("title")
                    title = title_raw if isinstance(title_raw, str) else "Untitled"

                    company_info = job.get("company") or job.get("Company")
                    if isinstance(company_info, dict):
                        comp_name = company_info.get("name")
                        company = comp_name if isinstance(comp_name, str) else "Unknown"
                    else:
                        company = "Unknown"

                    location_info = job.get("location") or job.get("city")
                    if isinstance(location_info, dict):
                        loc_name = location_info.get("name") or location_info.get("formattedName")
                        location_str = loc_name if isinstance(loc_name, str) else default_loc
                    else:
                        location_str = str(location_info) if location_info else default_loc

                    salaries = job.get("salaries")
                    if isinstance(salaries, dict):
                        sal_min = salaries.get("minSalary") or salaries.get("min")
                        sal_max = salaries.get("maxSalary") or salaries.get("max")
                        sal_curr = salaries.get("currencyCode") or salaries.get("currency") or "IDR"
                        salary = f"{sal_curr} {sal_min} - {sal_max}" if sal_min or sal_max else "Not disclosed"
                    elif isinstance(job.get("minSalary"), (int, float)) or isinstance(job.get("maxSalary"), (int, float)):
                        sal_min = job.get("minSalary")
                        sal_max = job.get("maxSalary")
                        sal_curr = job.get("salariesCurrency") or "IDR"
                        salary = f"{sal_curr} {sal_min} - {sal_max}"
                    else:
                        salary = "Not disclosed"

                    arrangement = str(job.get("workArrangementOption") or job.get("workMode") or "").upper()
                    if "REMOTE" in arrangement or job.get("isRemote"):
                        work_mode = "Remote"
                    elif "HYBRID" in arrangement:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    job_url = f"https://glints.com/id/opportunities/jobs/{raw_id}"

                    created_at = job.get("createdAt") or job.get("updatedAt")
                    created_at_str = created_at if isinstance(created_at, str) else ""
                    posted_at = created_at_str[:10] if len(created_at_str) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    job_type = job.get("type")
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
                logger.error(f"Error scraping Glints for keyword {kw}: {e}")

        return scraped_jobs
