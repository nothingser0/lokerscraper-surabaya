import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Set, Dict, Any

from config import config

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, jobs_file: Path = config.JOBS_FILE, seen_ids_file: Path = config.SEEN_IDS_FILE):
        self.jobs_file = jobs_file
        self.seen_ids_file = seen_ids_file
        
        # Ensure parent directories exist
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_ids_file.parent.mkdir(parents=True, exist_ok=True)

    def load_jobs(self) -> List[Dict[str, Any]]:
        """Load jobs list from jobs.json."""
        if not self.jobs_file.exists():
            return []
        try:
            with open(self.jobs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("jobs", [])
        except Exception as e:
            logger.error(f"Error loading jobs from {self.jobs_file}: {e}")
            return []

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """Save jobs list to jobs.json with lastUpdated ISO8601 timestamp."""
        payload = {
            "jobs": jobs,
            "lastUpdated": datetime.now(timezone.utc).isoformat()
        }
        try:
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving jobs to {self.jobs_file}: {e}")

    def load_seen_ids(self) -> Set[str]:
        """Load set of seen job IDs from seen-ids.json."""
        if not self.seen_ids_file.exists():
            return set()
        try:
            with open(self.seen_ids_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("ids", []))
        except Exception as e:
            logger.error(f"Error loading seen IDs from {self.seen_ids_file}: {e}")
            return set()

    def save_seen_ids(self, ids: Set[str]) -> None:
        """Save set of seen job IDs to seen-ids.json with lastCleanup timestamp."""
        # Preserving existing lastCleanup if available
        last_cleanup = datetime.now(timezone.utc).isoformat()
        if self.seen_ids_file.exists():
            try:
                with open(self.seen_ids_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    if "lastCleanup" in old_data:
                        last_cleanup = old_data["lastCleanup"]
            except Exception:
                pass

        payload = {
            "ids": list(ids),
            "lastCleanup": last_cleanup
        }
        try:
            with open(self.seen_ids_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving seen IDs to {self.seen_ids_file}: {e}")

    def filter_new_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out already seen jobs, return new jobs, and update seen_ids.json."""
        seen_ids = self.load_seen_ids()
        new_jobs = []
        for job in jobs:
            job_id = job.get("id")
            if job_id and job_id not in seen_ids:
                new_jobs.append(job)
                seen_ids.add(job_id)
        
        if new_jobs:
            self.save_seen_ids(seen_ids)
        
        return new_jobs

    def cleanup_old_jobs(self, days: int = 30) -> None:
        """Remove jobs older than specified days (default: 30) from jobs.json."""
        jobs = self.load_jobs()
        if not jobs:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        valid_jobs = []

        for job in jobs:
            date_str = job.get("scraped_at") or job.get("posted_at")
            if not date_str:
                valid_jobs.append(job)
                continue
            
            try:
                # Parse ISO8601 or YYYY-MM-DD
                if "T" in date_str:
                    job_dt = datetime.fromisoformat(date_str)
                else:
                    job_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                
                if job_dt.tzinfo is None:
                    job_dt = job_dt.replace(tzinfo=timezone.utc)

                if job_dt >= cutoff:
                    valid_jobs.append(job)
            except Exception:
                valid_jobs.append(job)

        if len(valid_jobs) < len(jobs):
            logger.info(f"Cleaned up {len(jobs) - len(valid_jobs)} old jobs.")
            self.save_jobs(valid_jobs)

    def trim_seen_ids(self, max_limit: int = 10000, target_limit: int = 5000) -> None:
        """If seen IDs count exceeds max_limit, trim to target_limit oldest entries."""
        seen_ids = list(self.load_seen_ids())
        if len(seen_ids) > max_limit:
            # Keep target_limit entries (assuming slice preserves order/newest at end)
            trimmed_ids = set(seen_ids[-target_limit:])
            
            payload = {
                "ids": list(trimmed_ids),
                "lastCleanup": datetime.now(timezone.utc).isoformat()
            }
            try:
                with open(self.seen_ids_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                logger.info(f"Trimmed seen_ids from {len(seen_ids)} to {len(trimmed_ids)}.")
            except Exception as e:
                logger.error(f"Error trimming seen IDs: {e}")
