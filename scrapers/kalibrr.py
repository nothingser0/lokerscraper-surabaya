import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import (
    sanitize_text,
    clean_description,
    format_job_type_id,
    decode_kalibrr_experience,
    decode_kalibrr_education,
    decode_benefit,
)

logger = logging.getLogger(__name__)

class KalibrrScraper(BaseScraper):
    ENDPOINT = "https://www.kalibrr.com/kjs/job_board/search"

    @property
    def source_name(self) -> str:
        return "Kalibrr"

    def __init__(self):
        super().__init__()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

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

    def _format_date(self, date_str: Any) -> str:
        if not date_str or not isinstance(date_str, str):
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
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
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
                    company_info_dict = company_info if isinstance(company_info, dict) else {}
                    company_code = (
                        job.get("company_code") 
                        or company_info_dict.get("code")
                        or "company"
                    )
                    
                    logo_url = company_info_dict.get("logo") or company_info_dict.get("logo_small")
                    company_industry = company_info_dict.get("industry")
                    company_description = company_info_dict.get("description")

                    slug = job.get("slug")
                    job_slug = slug if isinstance(slug, str) else str(raw_id)
                    job_url = f"https://www.kalibrr.com/c/{company_code}/jobs/{raw_id}/{job_slug}"

                    tenure = job.get("tenure")
                    job_type = format_job_type_id(tenure if isinstance(tenure, str) and tenure else "Full-time")

                    created_at_str = self._format_date(job.get("created_at"))
                    posted_at = created_at_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    deadline_str = self._format_date(job.get("application_end_date"))
                    application_deadline = deadline_str if deadline_str else None

                    sal_min = None
                    sal_max = None
                    base_sal = job.get("base_salary")
                    max_sal = job.get("maximum_salary")
                    try:
                        sal_min = int(base_sal) if base_sal is not None else None
                    except (ValueError, TypeError):
                        pass
                    try:
                        sal_max = int(max_sal) if max_sal is not None else None
                    except (ValueError, TypeError):
                        pass
                    sal_curr = job.get("salary_currency") or ("IDR" if (sal_min or sal_max) else None)

                    openings = job.get("number_of_openings")
                    number_of_openings = int(openings) if isinstance(openings, (int, float)) else None

                    skills_list = []
                    sds_skills = job.get("job_sds_skills")
                    if isinstance(sds_skills, list):
                        for sk in sds_skills:
                            if isinstance(sk, dict):
                                sds_obj = sk.get("sds_skill")
                                if isinstance(sds_obj, dict):
                                    sname = sds_obj.get("name")
                                    if isinstance(sname, str) and sname:
                                        skills_list.append(sname)

                    experience = decode_kalibrr_experience(job.get("work_experience"))
                    education = decode_kalibrr_education(job.get("education_level"))

                    job_desc = clean_description(job.get("description")) or None
                    qualifications = clean_description(job.get("qualifications")) or None

                    benefits = []
                    perks = job.get("perks")
                    if isinstance(perks, dict):
                        ptypes = perks.get("types")
                        if isinstance(ptypes, list):
                            for p in ptypes:
                                if isinstance(p, str) and p:
                                    benefits.append(decode_benefit(p))
                        pother = perks.get("other")
                        if isinstance(pother, str) and pother:
                            decoded_other = decode_benefit(pother)
                            if decoded_other:
                                benefits.append(decoded_other)

                    item = new_job_dict(
                        raw_id=str(raw_id),
                        source=self.source_name,
                        title=sanitize_text(job_name_str or "Untitled"),
                        company=sanitize_text(company_name),
                        logo_url=logo_url,
                        company_industry=company_industry,
                        company_description=company_description,
                        location=sanitize_text(location_str),
                        salary_min=sal_min,
                        salary_max=sal_max,
                        salary_currency=sal_curr,
                        work_type=job_type,
                        work_mode=self._get_work_mode(job),
                        posted_at=posted_at,
                        application_deadline=application_deadline,
                        applicant_count=None,
                        number_of_openings=number_of_openings,
                        skills=skills_list if skills_list else None,
                        experience=experience,
                        education=education,
                        job_description=job_desc,
                        qualifications=qualifications,
                        benefits=benefits if benefits else None,
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping Kalibrr for keyword {kw}: {e}")

        return scraped_jobs
