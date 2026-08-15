import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from config import config
from scrapers import (
    KalibrrScraper,
    JobStreetScraper,
    GlintsScraper,
    LinkedInScraper,
    SejutaCitaScraper,
)
from storage import StorageService
from engine.filter import filter_jobs
from engine.dedup import generate_job_id, deduplicate_jobs
from notifiers import notify_new_jobs

logger = logging.getLogger(__name__)

class ScraperRunner:
    def __init__(self):
        self.scrapers = [
            KalibrrScraper(),
            JobStreetScraper(),
            GlintsScraper(),
            LinkedInScraper(),
            SejutaCitaScraper(),
        ]

    def _run_single_scraper(self, scraper: Any) -> List[Dict[str, Any]]:
        scraper_name = scraper.__class__.__name__
        try:
            logger.info(f"Starting scraper: {scraper_name}")
            if hasattr(scraper, "fetch_jobs"):
                jobs = scraper.fetch_jobs()
            elif hasattr(scraper, "scrape"):
                jobs = getattr(scraper, "scrape")()
            else:
                jobs = []
            logger.info(f"Finished {scraper_name}: fetched {len(jobs) if jobs else 0} jobs")
            return jobs or []
        except Exception as e:
            logger.error(f"Error running scraper {scraper_name}: {e}", exc_info=True)
            return []

    def run_cycle(self) -> Dict[str, Any]:
        """Run one scraping cycle across all scrapers in parallel."""
        storage = StorageService()
        raw_jobs: List[Dict[str, Any]] = []

        max_workers = getattr(config, "MAX_WORKERS", 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_scraper = {
                executor.submit(self._run_single_scraper, scraper): scraper 
                for scraper in self.scrapers
            }
            for future in as_completed(future_to_scraper):
                jobs = future.result()
                if jobs:
                    raw_jobs.extend(jobs)

        scraped_total = len(raw_jobs)
        
        filtered_jobs = filter_jobs(raw_jobs)
        filtered_total = len(filtered_jobs)

        for job in filtered_jobs:
            if not job.get("source"):
                job["source"] = "Unknown"
            if not job.get("id"):
                source = job.get("source", "unknown")
                raw_id = job.get("raw_id") or job.get("id") or job.get("url") or job.get("title") or ""
                job["id"] = generate_job_id(source, raw_id)

        existing_seen_ids = storage.load_seen_ids()
        new_jobs, updated_seen_ids = deduplicate_jobs(filtered_jobs, existing_seen_ids)
        new_jobs_count = len(new_jobs)

        if new_jobs:
            existing_jobs = storage.load_jobs()
            updated_jobs = existing_jobs + new_jobs
            storage.save_jobs(updated_jobs)
            storage.save_seen_ids(updated_seen_ids)
            notify_new_jobs(new_jobs)

        try:
            storage.cleanup_old_jobs()
            storage.trim_seen_ids()
        except Exception as e:
            logger.error(f"Error during storage cleanup: {e}", exc_info=True)

        return {
            "scraped_total": scraped_total,
            "filtered_total": filtered_total,
            "new_jobs_count": new_jobs_count,
            "new_jobs": new_jobs,
        }
