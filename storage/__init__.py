import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Set, Dict, Any, Union

from config import config
from utils.atomic import atomic_write

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, jobs_file: Path = config.JOBS_FILE, seen_ids_file: Path = config.SEEN_IDS_FILE):
        self.jobs_file = jobs_file
        self.seen_ids_file = seen_ids_file
        
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_ids_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_json_with_recovery(self, filepath: Path) -> Dict[str, Any]:
        bak_file = filepath.with_suffix(filepath.suffix + ".bak")
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"JSONDecodeError loading {filepath}: {e}. Attempting recovery from backup.")
                if bak_file.exists():
                    try:
                        with open(bak_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            logger.info(f"Successfully recovered JSON data from backup {bak_file}")
                            return data
                    except Exception as bak_err:
                        logger.error(f"Failed to load backup {bak_file}: {bak_err}")
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")

        if bak_file.exists():
            try:
                with open(bak_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading backup {bak_file}: {e}")

        return {}

    def _atomic_write_with_backup(self, filepath: Path, content: str) -> None:
        bak_file = filepath.with_suffix(filepath.suffix + ".bak")
        if filepath.exists():
            try:
                shutil.copy2(filepath, bak_file)
            except Exception as e:
                logger.warning(f"Failed to create backup for {filepath}: {e}")
        atomic_write(filepath, content)

    def load_jobs(self) -> List[Dict[str, Any]]:
        """Load jobs list from jobs.json."""
        data = self._load_json_with_recovery(self.jobs_file)
        jobs = data.get("jobs", [])
        return jobs if isinstance(jobs, list) else []

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """Save jobs list to jobs.json."""
        payload = {
            "jobs": jobs,
            "lastUpdated": datetime.now(timezone.utc).isoformat()
        }
        try:
            content = json.dumps(payload, indent=2, ensure_ascii=False)
            self._atomic_write_with_backup(self.jobs_file, content)
        except Exception as e:
            logger.error(f"Error saving jobs to {self.jobs_file}: {e}")

    def load_seen_ids(self) -> Set[str]:
        """Load set of seen job IDs from seen-ids.json."""
        data = self._load_json_with_recovery(self.seen_ids_file)
        ids = data.get("ids", [])
        return set(ids) if isinstance(ids, list) else set()

    def save_seen_ids(self, ids: Set[str]) -> None:
        """Save set of seen job IDs to seen-ids.json."""
        last_cleanup = datetime.now(timezone.utc).isoformat()
        old_data = self._load_json_with_recovery(self.seen_ids_file)
        if isinstance(old_data, dict) and "lastCleanup" in old_data:
            last_cleanup = old_data["lastCleanup"]

        payload = {
            "ids": list(ids),
            "lastCleanup": last_cleanup
        }
        try:
            content = json.dumps(payload, indent=2, ensure_ascii=False)
            self._atomic_write_with_backup(self.seen_ids_file, content)
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
        """Remove jobs older than specified days."""
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
        """Trim seen IDs to target_limit if max_limit is exceeded."""
        seen_ids = list(self.load_seen_ids())
        if len(seen_ids) > max_limit:
            trimmed_ids = set(seen_ids[-target_limit:])
            
            payload = {
                "ids": list(trimmed_ids),
                "lastCleanup": datetime.now(timezone.utc).isoformat()
            }
            try:
                content = json.dumps(payload, indent=2, ensure_ascii=False)
                self._atomic_write_with_backup(self.seen_ids_file, content)
                logger.info(f"Trimmed seen_ids from {len(seen_ids)} to {len(trimmed_ids)}.")
            except Exception as e:
                logger.error(f"Error trimming seen IDs: {e}")
