import logging
from typing import List, Dict, Any

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

    def run_cycle(self) -> Dict[str, Any]:
        """Runs one scraping cycle across all scrapers, filters, deduplicates, saves, and cleans up."""
        storage = StorageService()
        raw_jobs: List[Dict[str, Any]] = []

        for scraper in self.scrapers:
            scraper_name = scraper.__class__.__name__
            try:
                logger.info(f"Starting scraper: {scraper_name}")
                if hasattr(scraper, "fetch_jobs"):
                    jobs = scraper.fetch_jobs()
                elif hasattr(scraper, "scrape"):
                    jobs = getattr(scraper, "scrape")()
                else:
                    jobs = []
                if jobs:
                    raw_jobs.extend(jobs)
                logger.info(f"Finished {scraper_name}: fetched {len(jobs) if jobs else 0} jobs")
            except Exception as e:
                logger.error(f"Error running scraper {scraper_name}: {e}", exc_info=True)

        scraped_total = len(raw_jobs)
        
        # Ensure job ID exists on each raw job
        for job in raw_jobs:
            if not job.get("source"):
                job["source"] = "Unknown"
            if not job.get("id"):
                source = job.get("source", "unknown")
                raw_id = job.get("id") or job.get("url") or job.get("title") or ""
                job["id"] = generate_job_id(source, raw_id)

        # 4. Filter jobs
        filtered_jobs = filter_jobs(raw_jobs)
        filtered_total = len(filtered_jobs)

        # 5. Deduplicate jobs using StorageService & engine.dedup
        existing_seen_ids = storage.load_seen_ids()
        new_jobs, updated_seen_ids = deduplicate_jobs(filtered_jobs, existing_seen_ids)
        new_jobs_count = len(new_jobs)

        # 6. Save new jobs & update seen-ids
        if new_jobs:
            existing_jobs = storage.load_jobs()
            updated_jobs = existing_jobs + new_jobs
            storage.save_jobs(updated_jobs)
            storage.save_seen_ids(updated_seen_ids)

        # 7. Auto-cleanup
        try:
            storage.cleanup_old_jobs()
            storage.trim_seen_ids()
        except Exception as e:
            logger.error(f"Error during storage cleanup: {e}", exc_info=True)

        # 8. Return summary dictionary
        return {
            "scraped_total": scraped_total,
            "filtered_total": filtered_total,
            "new_jobs_count": new_jobs_count,
            "new_jobs": new_jobs,
        }
