import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from config import config
from scrapers.base import BaseScraper
from utils.text import sanitize_text

logger = logging.getLogger(__name__)

class LinkedInScraper(BaseScraper):
    ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    @property
    def source_name(self) -> str:
        return "LinkedIn"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

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
                response = self.session.get(self.ENDPOINT, headers=self.headers, params=params, timeout=10)
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

                    item = {
                        "raw_id": str(raw_id),
                        "source": self.source_name,
                        "title": sanitize_text(title),
                        "company": sanitize_text(company),
                        "location": sanitize_text(location_str),
                        "salary": "Not disclosed",
                        "type": "Full-time",
                        "work_mode": work_mode,
                        "url": job_url,
                        "posted_at": posted_at,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    }

                    scraped_jobs.append(item)
                    seen_job_ids.add(raw_id)

            except Exception as e:
                logger.error(f"Error scraping LinkedIn for keyword {kw}: {e}")

        return scraped_jobs
