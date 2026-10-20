import json
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from storage import StorageService


def test_cleanup_deletes_old_rows():
    s = StorageService()
    s.sqlite_file = Path(tempfile.mkdtemp()) / "jobs.db"
    s._init_sqlite()

    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(s.sqlite_file) as conn:
        for jid, ts in (("old1", old), ("old2", old), ("new", new)):
            conn.execute(
                "INSERT INTO jobs (id, created_at, posted_at, data_json) VALUES (?, ?, ?, ?)",
                (jid, ts, ts, json.dumps({"id": jid, "scraped_at": ts})),
            )

    s.cleanup_old_jobs(days=30)

    with sqlite3.connect(s.sqlite_file) as conn:
        assert [r[0] for r in conn.execute("SELECT id FROM jobs")] == ["new"]
