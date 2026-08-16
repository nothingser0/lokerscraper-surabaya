import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper, new_job_dict
from utils.text import sanitize_text, clean_description

logger = logging.getLogger(__name__)

class LinkedInScraper(BaseScraper):
    ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    @property
    def source_name(self) -> str:
        return "LinkedIn"

    def __init__(self):
        super().__init__()
        # LinkedIn aggressively rate-limits unauthenticated requests (429).
        # Space out keyword + detail requests generously to stay under the
        # threshold, and back off hard when a 429 does occur.
        self.request_delay = 30.0
        self._rate_limit_backoff = 120.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch_job_detail(self, raw_id: str) -> Dict[str, Any]:
        """Fetch detail HTML from https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{raw_id}"""
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{raw_id}"
        details: Dict[str, Any] = {
            "job_description": None,
            "qualifications": None,
            "skills": None,
            "experience": None,
            "company_industry": None,
        }
        try:
            resp = self._get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Description section
                desc_el = soup.find("div", class_=re.compile(r"show-more-less-html__markup|description__text"))
                if desc_el:
                    # Pass raw HTML (not get_text) so clean_description can
                    # convert <br>/<li>/<ul>/<p> into newlines & bullets.
                    full_desc = clean_description(str(desc_el))
                    if full_desc:
                        details["job_description"] = full_desc

                # Seniority level (experience)
                criteria_list = soup.find_all("li", class_=re.compile(r"description__job-criteria-item"))
                for item in criteria_list:
                    header = item.find("h3")
                    val = item.find("span")
                    if header and val:
                        htext = header.get_text(strip=True).lower()
                        vtext = val.get_text(strip=True)
                        if "seniority" in htext:
                            # LinkedIn uses "Not Applicable" when no seniority level
                            # is set; treat it as no data instead of a raw label.
                            details["experience"] = vtext if vtext and vtext.strip().lower() != "not applicable" else None
                        elif "industries" in htext or "industry" in htext:
                            details["company_industry"] = vtext

        except Exception as e:
            logger.debug(f"LinkedIn detail fetch skipped for {raw_id}: {e}")

        return details

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        scraped_jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()
        default_loc = config.LOCATIONS[0] if config.LOCATIONS else "Surabaya"

        for kw in config.IT_KEYWORDS:
            params = {
                "keywords": kw,
                "location": default_loc,
                "start": 0
            }
            try:
                response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)

                # On a 429, wait out LinkedIn's cooldown then retry once before
                # giving up on this cycle. This trades time for stability.
                if response.status_code == 429:
                    logger.warning(
                        f"LinkedIn returned 429 for keyword {kw}; backing off "
                        f"{self._rate_limit_backoff:.0f}s then retrying once."
                    )
                    time.sleep(self._rate_limit_backoff)
                    response = self._get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
                    if response.status_code == 429:
                        logger.warning("LinkedIn still rate-limited after backoff; stopping this cycle.")
                        break

                if response.status_code != 200:
                    logger.warning(f"LinkedIn returned status {response.status_code} for keyword {kw}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("li")

                for card in job_cards:
                    entity_urn = card.find("div", {"data-entity-urn": True})
                    raw_id = None
                    if entity_urn:
                        urn_str = entity_urn.get("data-entity-urn", "")
                        match = re.search(r"jobPosting:(\d+)", urn_str)
                        if match:
                            raw_id = match.group(1)

                    if not raw_id:
                        link = card.find("a", class_=re.compile(r"base-card__full-link|job-search-card__link"))
                        if link and link.get("href"):
                            match = re.search(r"view/(\d+)", link.get("href"))
                            if match:
                                raw_id = match.group(1)

                    if not raw_id or raw_id in seen_job_ids:
                        continue

                    title_el = card.find("h3", class_=re.compile(r"base-search-card__title|job-search-card__title"))
                    title = title_el.get_text(strip=True) if title_el else "Untitled"

                    company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle|job-search-card__subtitle"))
                    if not company_el:
                        company_el = card.find("a", class_=re.compile(r"hidden-nested-link"))
                    company = company_el.get_text(strip=True) if company_el else "Unknown"

                    logo_el = card.find("img")
                    logo_url = None
                    if logo_el and logo_el.get("data-delayed-url"):
                        logo_url = logo_el.get("data-delayed-url")
                    elif logo_el and logo_el.get("src"):
                        logo_url = logo_el.get("src")

                    loc_el = card.find("span", class_=re.compile(r"job-search-card__location"))
                    location_str = loc_el.get_text(strip=True) if loc_el else default_loc

                    url_el = card.find("a", class_=re.compile(r"base-card__full-link|job-search-card__link"))
                    job_url = url_el.get("href").split("?")[0] if url_el and url_el.get("href") else f"https://www.linkedin.com/jobs/view/{raw_id}"

                    time_el = card.find("time")
                    posted_at = ""
                    if time_el and time_el.get("datetime"):
                        posted_at = time_el.get("datetime")
                    elif time_el:
                        posted_at = time_el.get_text(strip=True)

                    if posted_at and len(posted_at) >= 10 and "-" in posted_at[:10]:
                        posted_at = posted_at[:10]
                    else:
                        posted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    title_lower = title.lower()
                    if "remote" in title_lower:
                        work_mode = "Remote"
                    elif "hybrid" in title_lower:
                        work_mode = "Hybrid"
                    else:
                        work_mode = "On-site"

                    # Parse applicant count if available
                    applicant_count = None
                    app_el = card.find("span", class_=re.compile(r"job-search-card__num-applicants"))
                    if app_el:
                        app_text = app_el.get_text(strip=True)
                        m = re.search(r"(\d+)", app_text)
                        if m:
                            applicant_count = int(m.group(1))

                    # Fetch optional detail HTML
                    details = self._fetch_job_detail(raw_id)

                    item = new_job_dict(
                        raw_id=str(raw_id),
                        source=self.source_name,
                        title=sanitize_text(title),
                        company=sanitize_text(company),
                        logo_url=logo_url,
                        company_industry=details.get("company_industry"),
                        location=sanitize_text(location_str),
                        work_type="Full-time",
                        work_mode=work_mode,
                        posted_at=posted_at,
                        applicant_count=applicant_count,
                        experience=details.get("experience"),
                        job_description=details.get("job_description"),
                        qualifications=details.get("qualifications"),
                        skills=details.get("skills"),
                        url=job_url,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    )

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping LinkedIn for keyword {kw}: {e}")

        return scraped_jobs
