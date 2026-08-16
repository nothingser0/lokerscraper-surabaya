import logging
import sys
import threading
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Ensure the project root is on sys.path so that `python api/app.py`
# (used by Docker CMD, systemd ExecStart, and local dev) can resolve
# sibling top-level packages: config, storage, engine, scrapers, notifiers.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from config import config, random_scrape_interval_hours
from storage import StorageService
from engine.runner import ScraperRunner

logger = logging.getLogger(__name__)

app = Flask(__name__)
storage_service = StorageService()

def scheduled_scrape_job():
    logger.info("Triggering scheduled scrape cycle...")
    try:
        runner = ScraperRunner()
        result = runner.run_cycle()
        logger.info(f"Scheduled scrape cycle finished: {result.get('new_jobs_count', 0)} new jobs found.")
    except Exception as e:
        logger.error(f"Error in scheduled scrape cycle: {e}", exc_info=True)
    finally:
        _reschedule_next_run()


def _reschedule_next_run():
    """Re-arm the scheduled job with a fresh (possibly random) interval.

    Uses a one-shot 'date' trigger computed from a random [min, max] interval
    (or the fixed SCRAPE_INTERVAL_HOURS), so each cycle can vary instead of
    being locked to a single interval at startup.
    """
    interval_hours = random_scrape_interval_hours()
    run_at = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
    try:
        scheduler.add_job(
            scheduled_scrape_job,
            'date',
            run_date=run_at,
            id='scraper_cycle_job',
            replace_existing=True,
        )
        logger.info(f"Next scrape scheduled at ~{run_at.isoformat()} ({interval_hours}h).")
    except Exception as e:
        logger.error(f"Failed to reschedule scrape job: {e}", exc_info=True)


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    scheduled_scrape_job,
    'date',
    run_date=datetime.now(timezone.utc) + timedelta(hours=random_scrape_interval_hours()),
    id='scraper_cycle_job',
    replace_existing=True
)
scheduler.start()

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def _run_scrape_async(force: bool = False):
    """Run a scrape cycle in a background thread (for manual trigger)."""
    try:
        runner = ScraperRunner()
        result = runner.run_cycle(force=force)
        logger.info(f"Manual scrape cycle finished: {result.get('new_jobs_count', 0)} new jobs found.")
    except Exception as e:
        logger.error(f"Error in manual scrape cycle: {e}", exc_info=True)

@app.route("/api/trigger", methods=["GET", "POST"])
def trigger_scrape():
    """Manually trigger a scrape cycle without waiting for the scheduler.

    Use POST, or open the URL directly with GET. Add `?force=true` to also send the freshly fetched batch to Discord even if
    no new jobs were found (useful for testing the notification path).
    """
    if getattr(config, "TRIGGER_TOKEN", "") and request.headers.get("X-Trigger-Token") != config.TRIGGER_TOKEN:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    thread = threading.Thread(target=_run_scrape_async, kwargs={"force": force}, daemon=True)
    thread.start()
    return jsonify({
        "status": "started",
        "message": "Scrape cycle started in background",
        "force": force,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 202

@app.route("/api/stats", methods=["GET"])
def get_stats():
    jobs = storage_service.load_jobs()
    total_jobs = len(jobs)
    
    source_counts: Dict[str, int] = {}
    for job in jobs:
        src = job.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        
    data = storage_service._load_json_with_recovery(storage_service.jobs_file)
    last_updated = data.get("lastUpdated")

    return jsonify({
        "totalJobs": total_jobs,
        "sourceCounts": source_counts,
        "lastUpdated": last_updated
    })

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    keyword = request.args.get("keyword", "").strip().lower()
    source = request.args.get("source", "").strip().lower()
    
    try:
        days = int(request.args.get("days", 30))
    except ValueError:
        days = 30

    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0

    jobs = storage_service.load_jobs()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []
    for job in jobs:
        date_str = job.get("scraped_at") or job.get("posted_at")
        if date_str:
            try:
                if "T" in date_str:
                    dt = datetime.fromisoformat(date_str)
                else:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                pass
        filtered.append(job)

    if keyword:
        filtered = [
            j for j in filtered
            if keyword in (j.get("title") or "").lower()
            or keyword in (j.get("company") or "").lower()
            or keyword in (j.get("job_description") or j.get("description") or "").lower()
            or keyword in (j.get("qualifications") or "").lower()
        ]

    if source:
        filtered = [
            j for j in filtered
            if source == j.get("source", "").lower()
        ]

    total_count = len(filtered)
    paginated = filtered[offset:offset + limit]

    return jsonify({
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": paginated
    })

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000, threads=8)
