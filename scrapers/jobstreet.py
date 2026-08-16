import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text, clean_description, parse_salary_label, format_job_type_id

logger = logging.getLogger(__name__)

class JobStreetScraper(BaseScraper):
    ENDPOINT = "https://id.jobstreet.com/api/jobsearch/v5/search"

    @property
    def source_name(self) -> str:
        return "JobStreet"

    def __init__(self):
        super().__init__()
        # JobStreet detail pages are fetched per job (N+1); throttle to avoid
        # tripping their anti-bot limits.
        self.request_delay = 1.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    def _fetch_job_detail(self, raw_id: str) -> Dict[str, Any]:
        """Fetch detail HTML from https://id.jobstreet.com/job/{raw_id} and extract structured fields."""
        url = f"https://id.jobstreet.com/job/{raw_id}"
        details: Dict[str, Any] = {
            "job_description": None,
            "qualifications": None,
            "skills": None,
            "experience": None,
            "education": None,
            "application_deadline": None,
        }
        try:
            resp = self._get(url, headers={"User-Agent": self.headers["User-Agent"]}, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Check for JSON-LD for deadline / validThrough
                scripts = soup.find_all("script", type="application/ld+json")
                for s in scripts:
                    if s.string and "validThrough" in s.string:
                        m = re.search(r'"validThrough"\s*:\s*"([^"]+)"', s.string)
                        if m:
                            details["application_deadline"] = m.group(1)[:10]
                            break

                # Extract description & qualifications
                desc_el = soup.find("div", {"data-automation": "jobDescription"}) or soup.find("div", class_=re.compile(r"jobDescription|Description"))
                if desc_el:
                    # Pass raw HTML (not get_text) so clean_description can
                    # convert <br>/<li>/<ul>/<p> into newlines & bullets.
                    full_text = clean_description(str(desc_el))
                    if full_text:
                        details["job_description"] = full_text

                # NOTE: JobStreet's detail page exposes no structured experience/education
                # value. The "How many years' experience…" / "Which of the following…
                # qualifications…" strings are screening-question labels shown to every
                # applicant, NOT the job's actual requirement. Do not scrape them; leave
                # experience/education as None (consistent with other sources that lack
                # the data) rather than leaking misleading boilerplate.

        except Exception as e:
            logger.debug(f"JobStreet detail fetch skipped for {raw_id}: {e}")

        return details

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
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
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

                    company = "Unknown"
                    advertiser = job.get("advertiser")
                    if isinstance(advertiser, dict):
                        raw_company = advertiser.get("description")
                        company = raw_company if isinstance(raw_company, str) else "Unknown"

                    branding = job.get("branding")
                    logo_url = None
                    if isinstance(branding, dict):
                        logo = branding.get("serpLogoUrl")
                        if isinstance(logo, str) and logo:
                            logo_url = logo

                    company_industry = None
                    classifications = job.get("classifications")
                    if isinstance(classifications, list) and classifications:
                        first_c = classifications[0]
                        if isinstance(first_c, dict):
                            class_obj = first_c.get("classification")
                            if isinstance(class_obj, dict):
                                cdesc = class_obj.get("description")
                                if isinstance(cdesc, str) and cdesc:
                                    company_industry = cdesc

                    locations = job.get("locations")
                    location_str = default_loc
                    if isinstance(locations, list) and locations and isinstance(locations[0], dict):
                        raw_loc = locations[0].get("label")
                        if isinstance(raw_loc, str) and raw_loc:
                            location_str = raw_loc

                    salary_raw = job.get("salaryLabel")
                    sal_min, sal_max = parse_salary_label(salary_raw if isinstance(salary_raw, str) else None)
                    sal_curr = "IDR" if (sal_min or sal_max) else None

                    work_types = job.get("workTypes")
                    raw_type = work_types[0] if (isinstance(work_types, list) and work_types) else "Full-time"
                    work_type = format_job_type_id(str(raw_type))

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

                    # Fetch optional detail HTML
                    details = self._fetch_job_detail(raw_id)

                    # JobStreet's detail page is a JS-rendered SPA with no static
                    # full body. Fall back to the list endpoint's `teaser`
                    # (intro paragraph) + `bulletPoints` (highlights) so the
                    # notification still carries a readable summary.
                    job_desc = details.get("job_description")
                    if not job_desc:
                        parts = []
                        teaser = job.get("teaser")
                        if isinstance(teaser, str) and teaser.strip():
                            parts.append(teaser.strip())
                        bullets = job.get("bulletPoints")
                        if isinstance(bullets, list):
                            for b in bullets:
                                if isinstance(b, str) and b.strip():
                                    parts.append(f"• {b.strip()}")
                        if parts:
                            job_desc = "\n\n".join(parts)

                    item = new_job_dict(
                        raw_id=raw_id,
                        source=self.source_name,
                        title=sanitize_text(title),
                        company=sanitize_text(company),
                        logo_url=logo_url,
                        company_industry=company_industry,
                        location=sanitize_text(location_str),
                        salary_min=sal_min,
                        salary_max=sal_max,
                        salary_currency=sal_curr,
                        work_type=work_type,
                        work_mode=work_mode,
                        posted_at=posted_at,
                        application_deadline=details.get("application_deadline"),
                        job_description=job_desc,
                        qualifications=details.get("qualifications"),
                        skills=details.get("skills"),
                        experience=details.get("experience"),
                        education=details.get("education"),
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping JobStreet for keyword {kw}: {e}")

        return scraped_jobs
