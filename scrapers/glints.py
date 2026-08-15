import hashlib
import json
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper

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
                return json.loads(script.string)
            except Exception as e:
                logger.error(f"Failed to parse __NEXT_DATA__ JSON in Glints: {e}")
        return {}

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()

        for kw in config.IT_KEYWORDS:
            params = {
                "keyword": kw,
                "country": "ID",
                "locationName": "Surabaya"
            }
            try:
                response = requests.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Glints returned status {response.status_code} for keyword {kw}")
                    continue

                next_data = self._extract_next_data(response.text)
                props = next_data.get("props", {}).get("pageProps", {})

                initial_jobs = props.get("initialJobs", {})
                jobs_data = (
                    initial_jobs.get("jobsInPage", []) if isinstance(initial_jobs, dict) else (
                        initial_jobs if isinstance(initial_jobs, list) else []
                    )
                )

                if not jobs_data:
                    # Alternative structure checks
                    jobs_data = (
                        props.get("initialState", {}).get("jobs", {}).get("data", []) or
                        props.get("jobs", []) or
                        props.get("data", {}).get("jobs", [])
                    )

                for job in jobs_data:
                    if not isinstance(job, dict):
                        continue

                    raw_id = str(job.get("id", ""))
                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title = job.get("title", "Untitled")

                    company_info = job.get("company", {}) or job.get("Company", {})
                    company = company_info.get("name", "Unknown") if isinstance(company_info, dict) else "Unknown"

                    location_info = job.get("location", {}) or job.get("city", {})
                    if isinstance(location_info, dict):
                        location_str = location_info.get("name") or location_info.get("formattedName") or "Surabaya"
                    else:
                        location_str = str(location_info) if location_info else "Surabaya"

                    # Salary
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

                    # Work Mode
                    arrangement = str(job.get("workArrangementOption") or job.get("workMode") or "").upper()
                    if "REMOTE" in arrangement or job.get("isRemote"):
                        work_mode = "Remote"
                    elif "HYBRID" in arrangement:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    job_url = f"https://glints.com/id/opportunities/jobs/{raw_id}"

                    created_at = job.get("createdAt") or job.get("updatedAt") or ""
                    posted_at = created_at[:10] if len(created_at) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    md5_hash = hashlib.md5(raw_id.encode("utf-8")).hexdigest()
                    job_hash_id = f"glints_{md5_hash}"

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
                logger.error(f"Error scraping Glints for keyword {kw}: {e}")

        return scraped_jobs
