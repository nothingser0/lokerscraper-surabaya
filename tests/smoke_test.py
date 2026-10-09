#!/usr/bin/env python3

import sys
import json
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage import StorageService
from engine.runner import ScraperRunner
from scrapers.base import BaseScraper

def test_database():
    print("[1/3] Testing SQLite Storage Layer...")
    s = StorageService()
    
    jobs = s.load_jobs()
    assert isinstance(jobs, list), "load_jobs must return a list"
    assert len(jobs) > 0, "jobs table should contain seeded/scraped records"
    
    total, paginated = s.query_jobs(limit=5, offset=0)
    assert total >= len(paginated), "total count must be >= paginated length"
    assert len(paginated) <= 5, "paginated results must honor limit"
    
    s.vacuum_database()
    print("  -> Storage tests passed: SQLite reads, pagination, and VACUUM OK.")

def test_scraper_registry():
    print("[2/3] Testing Scraper Registry & Auto-Discovery...")
    runner = ScraperRunner()
    scrapers = runner.scrapers
    assert len(scrapers) >= 5, f"Expected at least 5 scrapers, found {len(scrapers)}"
    names = [s.__class__.__name__ for s in scrapers]
    for expected in ["JobStreetScraper", "LinkedInScraper", "KalibrrScraper", "GlintsScraper", "SejutaCitaScraper"]:
        assert expected in names, f"Missing expected scraper: {expected}"
    print(f"  -> Registry tests passed: {len(scrapers)} scrapers discovered cleanly.")

def test_api_endpoints():
    print("[3/3] Testing Live HTTP API Endpoints (http://127.0.0.1:5000)...")
    base_url = "http://127.0.0.1:5000"
    
    with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
        assert resp.status == 200, f"/health returned {resp.status}"
        data = json.loads(resp.read().decode())
        assert data.get("status") == "ok", "health payload status must be ok"

    with urllib.request.urlopen(f"{base_url}/api/stats", timeout=5) as resp:
        assert resp.status == 200, f"/api/stats returned {resp.status}"
        data = json.loads(resp.read().decode())
        assert "totalJobs" in data, "stats payload missing totalJobs"
        assert "sourceCounts" in data, "stats payload missing sourceCounts"

    with urllib.request.urlopen(f"{base_url}/api/jobs?limit=2", timeout=5) as resp:
        assert resp.status == 200, f"/api/jobs returned {resp.status}"
        data = json.loads(resp.read().decode())
        assert "total" in data and "jobs" in data, "jobs payload missing total or jobs list"

    with urllib.request.urlopen(f"{base_url}/", timeout=5) as resp:
        assert resp.status == 200, f"Dashboard returned {resp.status}"
        html = resp.read().decode()
        assert "Tech Jobs" in html or "Active Opportunities" in html, "Dashboard HTML content missing key elements"

    print("  -> API tests passed: /health, /api/stats, /api/jobs, and / OK.")

if __name__ == "__main__":
    print("=" * 60)
    print("LOKERSCRAPER SURABAYA - SMOKE TEST SUITE")
    print("=" * 60)
    try:
        test_database()
        test_scraper_registry()
        test_api_endpoints()
        print("=" * 60)
        print("ALL SMOKE TESTS PASSED (100% HEALTHY)")
        print("=" * 60)
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
