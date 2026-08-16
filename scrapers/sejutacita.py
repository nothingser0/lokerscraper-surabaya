import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text, format_job_type_id, decode_benefit

logger = logging.getLogger(__name__)

class SejutaCitaScraper(BaseScraper):
    ENDPOINT = "https://api.sejutacita.id/v1/explore-job/job"

    @property
    def source_name(self) -> str:
        return "SejutaCita"

    def __init__(self):
        super().__init__()
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
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
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

                    company_name = "Unknown"
                    logo_url = None
                    company_industry = None
                    benefits_data = None
                    company_data = job.get("company")
                    if isinstance(company_data, dict):
                        cname = company_data.get("name")
                        if isinstance(cname, str) and cname:
                            company_name = cname
                        logo = company_data.get("logoUrl")
                        if isinstance(logo, str) and logo:
                            logo_url = logo
                        sector = company_data.get("sector")
                        if isinstance(sector, str) and sector:
                            company_industry = sector
                        insight_obj = company_data.get("insight")
                        if isinstance(insight_obj, dict):
                            bdata = insight_obj.get("benefits")
                            if isinstance(bdata, list):
                                benefits_data = bdata
                    elif company_data:
                        company_name = str(company_data)

                    city_data = job.get("city")
                    country_data = job.get("country")
                    loc_parts = []
                    if isinstance(city_data, dict):
                        cname = city_data.get("name")
                        if isinstance(cname, str) and cname:
                            loc_parts.append(cname)
                    if isinstance(country_data, dict):
                        cname = country_data.get("name")
                        if isinstance(cname, str) and cname:
                            loc_parts.append(cname)
                    location_str = ", ".join(loc_parts) if loc_parts else default_loc

                    sal_min = None
                    sal_max = None
                    salary_range = job.get("salaryRange")
                    if isinstance(salary_range, dict):
                        smin = salary_range.get("start") or salary_range.get("min")
                        smax = salary_range.get("end") or salary_range.get("max")
                        try:
                            sal_min = int(smin) if smin is not None else None
                        except (ValueError, TypeError):
                            pass
                        try:
                            sal_max = int(smax) if smax is not None else None
                        except (ValueError, TypeError):
                            pass

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

                    deadline_raw = job.get("lastActivelyHiringAt")
                    application_deadline = str(deadline_raw)[:10] if isinstance(deadline_raw, str) and len(deadline_raw) >= 10 else None

                    emp_types = job.get("employmentTypes")
                    if isinstance(emp_types, list) and emp_types:
                        raw_type = emp_types[0]
                    else:
                        raw_type = job.get("employmentType") or job.get("type") or "Full-time"
                    work_type = format_job_type_id(str(raw_type))

                    stats = job.get("stats")
                    applicant_count = None
                    if isinstance(stats, dict):
                        acount = stats.get("applicantCount")
                        if isinstance(acount, (int, float)):
                            applicant_count = int(acount)

                    openings = job.get("applicantPrioritySlots")
                    number_of_openings = int(openings) if isinstance(openings, (int, float)) else None

                    skills_list = []
                    raw_skills = job.get("skills")
                    if isinstance(raw_skills, list):
                        for sk in raw_skills:
                            if isinstance(sk, dict):
                                sk_name = sk.get("name")
                                if isinstance(sk_name, str) and sk_name:
                                    skills_list.append(sk_name)

                    cand_pref = job.get("candidatePreference")
                    # SejutaCita exposes education as raw integer codes (lastEducations)
                    # whose scale is not publicly documented, so we cannot map them to
                    # a reliable label. Drop the field instead of leaking raw numbers.
                    edu_str = None
                    qualifications = None
                    if isinstance(cand_pref, dict):
                        qual_parts = []
                        major = cand_pref.get("major")
                        if major:
                            qual_parts.append(f"Major: {major}")
                        uni = cand_pref.get("university")
                        if uni:
                            qual_parts.append(f"University: {uni}")
                        gpa = cand_pref.get("minimumGpa")
                        if gpa:
                            qual_parts.append(f"Min GPA: {gpa}")
                        if qual_parts:
                            qualifications = "; ".join(qual_parts)

                    benefits = None
                    if isinstance(benefits_data, list):
                        decoded = [decode_benefit(b) for b in benefits_data]
                        benefits = [b for b in decoded if b] or None

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
                        salary_currency="IDR" if (sal_min or sal_max) else None,
                        work_type=work_type,
                        work_mode=work_mode,
                        posted_at=posted_at,
                        application_deadline=application_deadline,
                        applicant_count=applicant_count,
                        number_of_openings=number_of_openings,
                        skills=skills_list if skills_list else None,
                        education=edu_str,
                        qualifications=qualifications,
                        benefits=benefits,
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping SejutaCita for keyword {kw}: {e}")

        return scraped_jobs
