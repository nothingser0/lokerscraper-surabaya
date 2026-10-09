import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Set, Dict, Any, Union, Optional

from config import config
from utils.atomic import atomic_write

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, jobs_file: Path = config.JOBS_FILE, seen_ids_file: Path = config.SEEN_IDS_FILE):
        self.jobs_file = jobs_file
        self.seen_ids_file = seen_ids_file
        
        self.logs_dir = config.LOGS_DIR
        self.sqlite_file = config.DATA_DIR / "jobs.db"
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_ids_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        source TEXT,
                        title TEXT,
                        company TEXT,
                        location TEXT,
                        salary TEXT,
                        url TEXT,
                        posted_at TEXT,
                        data_json TEXT,
                        created_at TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {e}")

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
        """Load all jobs directly from SQLite database."""
        jobs = []
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                cursor = conn.execute("SELECT data_json FROM jobs ORDER BY rowid DESC")
                for row in cursor.fetchall():
                    try:
                        jobs.append(json.loads(row[0]))
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error loading jobs from SQLite: {e}")
        return jobs

    def query_jobs(
        self,
        keyword: str = "",
        source: str = "",
        days: Optional[int] = None,
        limit: int = 500,
        offset: int = 0
    ) -> tuple[int, List[Dict[str, Any]]]:
        where_clauses = []
        params: List[Any] = []

        if keyword:
            like_kw = f"%{keyword.lower()}%"
            where_clauses.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(data_json) LIKE ?)")
            params.extend([like_kw, like_kw, like_kw])

        if source:
            where_clauses.append("LOWER(source) = ?")
            params.append(source.lower())

        if days is not None and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where_clauses.append("(created_at >= ? OR posted_at >= ?)")
            params.extend([cutoff, cutoff[:10]])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        total = 0
        jobs = []
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                count_cursor = conn.execute(f"SELECT COUNT(*) FROM jobs {where_sql}", params)
                total = count_cursor.fetchone()[0]

                query_sql = f"SELECT data_json FROM jobs {where_sql} ORDER BY rowid DESC LIMIT ? OFFSET ?"
                cursor = conn.execute(query_sql, params + [limit, offset])
                for row in cursor.fetchall():
                    try:
                        jobs.append(json.loads(row[0]))
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error querying jobs from SQLite: {e}")

        return total, jobs

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """Save jobs list to SQLite and record lastUpdated timestamp."""
        self._sync_to_sqlite(jobs)
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('lastUpdated', ?)", (now_str,))
        except Exception as e:
            logger.error(f"Error updating meta in SQLite: {e}")

    def get_last_updated(self) -> Optional[str]:
        """Retrieve lastUpdated timestamp from SQLite meta table."""
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                row = conn.execute("SELECT value FROM meta WHERE key = 'lastUpdated'").fetchone()
                if row:
                    return row[0]
        except Exception as e:
            logger.error(f"Error reading lastUpdated from SQLite: {e}")
        return None

    def record_scraper_run(self, scraper_name: str, success: bool) -> int:
        """Track consecutive failure streaks per scraper in SQLite.
        
        Returns the current failure streak count for this scraper.
        """
        key = f"fail_streak_{scraper_name}"
        current_fails = 0
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
                if row and row[0].isdigit():
                    current_fails = int(row[0])
                
                if success:
                    new_fails = 0
                else:
                    new_fails = current_fails + 1
                
                conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(new_fails)))
                return new_fails
        except Exception as e:
            logger.error(f"Error tracking scraper streak for {scraper_name}: {e}")
            return 0

    def _sync_to_sqlite(self, jobs: List[Dict[str, Any]]) -> None:
        """Upsert jobs into SQLite database."""
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                for j in jobs:
                    jid = j.get("id")
                    if not jid:
                        continue
                    conn.execute("""
                        INSERT OR REPLACE INTO jobs (id, source, title, company, location, salary, url, posted_at, data_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        jid,
                        j.get("source"),
                        j.get("title"),
                        j.get("company"),
                        j.get("location"),
                        str(j.get("salary")) if j.get("salary") is not None else None,
                        j.get("url"),
                        j.get("posted_at"),
                        json.dumps(j, ensure_ascii=False),
                        j.get("scraped_at") or datetime.now(timezone.utc).isoformat()
                    ))
        except Exception as e:
            logger.error(f"Error syncing jobs to SQLite: {e}")

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
        self.cleanup_old_logs(days=days)
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cutoff_date = cutoff_iso[:10]
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                # Delete rows where created_at is older than cutoff or posted_at is older than cutoff date
                cursor = conn.execute("""
                    DELETE FROM jobs 
                    WHERE (created_at IS NOT NULL AND created_at != '' AND created_at < ?)
                       OR (created_at IS NULL AND posted_at IS NOT NULL AND posted_at != '' AND posted_at < ?)
                """, (cutoff_iso, cutoff_date))
                if cursor.rowcount > 0:
                    logger.info(f"Cleaned up {cursor.rowcount} old jobs from SQLite.")
                    conn.execute("VACUUM")
        except Exception as e:
            logger.error(f"Error deleting old jobs from SQLite: {e}")

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
            self.vacuum_database()

    def vacuum_database(self) -> None:
        """Reclaim unused disk space in SQLite database after deletion (VACUUM)."""
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                conn.execute("VACUUM")
            logger.info("SQLite database vacuumed successfully.")
        except Exception as e:
            logger.error(f"Error vacuuming SQLite database: {e}")

    def cleanup_old_logs(self, days: int = 30) -> None:
        """Delete daily log files older than specified days to preserve storage."""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            for log_file in self.logs_dir.glob("jobs-*"):
                try:
                    date_part = log_file.stem.replace("jobs-", "")
                    file_date = datetime.strptime(date_part, "%Y-%m-%d")
                    if file_date < cutoff:
                        log_file.unlink(missing_ok=True)
                        bak = log_file.with_suffix(log_file.suffix + ".bak")
                        bak.unlink(missing_ok=True)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error cleaning old logs: {e}")

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

    def log_daily_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """Save scraped jobs to daily JSON and TXT log files."""
        if not jobs:
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        json_path = self.logs_dir / f"jobs-{today_str}.json"
        txt_path = self.logs_dir / f"jobs-{today_str}.txt"

        existing_daily: List[Dict[str, Any]] = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        existing_daily = loaded
            except Exception as e:
                logger.error(f"Error reading daily jobs JSON {json_path}: {e}")

        existing_ids = {j.get("id") for j in existing_daily if j.get("id")}
        unique_additions = [j for j in jobs if j.get("id") not in existing_ids]

        if unique_additions:
            combined_json = existing_daily + unique_additions
            try:
                self._atomic_write_with_backup(json_path, json.dumps(combined_json, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Error writing daily jobs JSON {json_path}: {e}")

        try:
            lines = []
            for j in unique_additions:
                title = j.get("title", "No Title")
                company = j.get("company", "No Company")
                source = j.get("source", "Unknown")
                location = j.get("location", "-")
                url = j.get("url", "-")
                salary = j.get("salary") or "-"
                lines.append(f"[{source}] {title} | {company} | {location} | Gaji: {salary}\nURL: {url}\n")

            if lines:
                with open(txt_path, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        except Exception as e:
            logger.error(f"Error writing daily jobs TXT {txt_path}: {e}")
