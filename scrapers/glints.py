import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import (
    sanitize_text,
    clean_description,
    format_job_type_id,
    decode_glints_education,
)

logger = logging.getLogger(__name__)

class GlintsScraper(BaseScraper):
    ENDPOINT = "https://glints.com/id/opportunities/jobs/explore"

    @property
    def source_name(self) -> str:
        return "Glints"

    def __init__(self):
        super().__init__()
        self.request_delay = 0.5
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
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
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
                    company_name = "Unknown"
                    logo_url = None
                    company_industry = None
                    if isinstance(company_info, dict):
                        cname = company_info.get("name")
                        if isinstance(cname, str) and cname:
                            company_name = cname
                        logo = company_info.get("logo") or company_info.get("logoUrl")
                        if isinstance(logo, str) and logo:
                            logo_url = logo
                        ind = company_info.get("industry")
                        if isinstance(ind, str) and ind:
                            company_industry = ind

                    location_info = job.get("location") or job.get("city")
                    if isinstance(location_info, dict):
                        loc_name = location_info.get("name") or location_info.get("formattedName")
                        location_str = loc_name if isinstance(loc_name, str) else default_loc
                    else:
                        location_str = str(location_info) if location_info else default_loc

                    sal_min = None
                    sal_max = None
                    sal_curr = None
                    salaries = job.get("salaries")
                    if isinstance(salaries, dict):
                        smin = salaries.get("minSalary") or salaries.get("min")
                        smax = salaries.get("maxSalary") or salaries.get("max")
                        sal_curr = salaries.get("currency") or "IDR"
                        try:
                            sal_min = int(smin) if smin is not None else None
                        except (ValueError, TypeError):
                            pass
                        try:
                            sal_max = int(smax) if smax is not None else None
                        except (ValueError, TypeError):
                            pass
                    elif job.get("minSalary") is not None or job.get("maxSalary") is not None:
                        mins = job.get("minSalary")
                        maxs = job.get("maxSalary")
                        try:
                            sal_min = int(mins) if mins is not None else None
                        except (ValueError, TypeError):
                            pass
                        try:
                            sal_max = int(maxs) if maxs is not None else None
                        except (ValueError, TypeError):
                            pass
                        sal_curr = "IDR"

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

                    job_type = format_job_type_id(str(job.get("type") or "FULL_TIME"))

                    skills_list = []
                    raw_skills = job.get("skills")
                    if isinstance(raw_skills, list):
                        for sk in raw_skills:
                            if isinstance(sk, dict):
                                sname = sk.get("name")
                                if isinstance(sname, str) and sname:
                                    skills_list.append(sname)

                    min_exp = job.get("minYearsOfExperience")
                    max_exp = job.get("maxYearsOfExperience")
                    experience = None
                    if min_exp is not None or max_exp is not None:
                        if min_exp is not None and max_exp is not None and min_exp != max_exp:
                            experience = f"{min_exp}-{max_exp} tahun"
                        elif min_exp is not None:
                            experience = f"{min_exp}+ tahun"
                        elif max_exp is not None:
                            experience = f"hingga {max_exp} tahun"

                    education = decode_glints_education(job.get("educationLevel"))
                    job_desc = clean_description(job.get("description")) or None
                    qualifications = clean_description(job.get("requirements")) or None

                    benefits_raw = job.get("benefits")
                    benefits = [sanitize_text(str(benefits_raw))] if benefits_raw else None

                    item = new_job_dict(
                        raw_id=raw_id,
                        source=self.source_name,
                        title=sanitize_text(title),
                        company=sanitize_text(company_name),
                        logo_url=logo_url,
                        company_industry=company_industry,
                        location=sanitize_text(location_str),
                        salary_min=sal_min,
                        salary_max=sal_max,
                        salary_currency=sal_curr if (sal_min or sal_max) else None,
                        work_type=job_type,
                        work_mode=work_mode,
                        posted_at=posted_at,
                        skills=skills_list if skills_list else None,
                        experience=experience,
                        education=education,
                        job_description=job_desc,
                        qualifications=qualifications,
                        benefits=benefits,
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping Glints for keyword {kw}: {e}")

        return scraped_jobs
