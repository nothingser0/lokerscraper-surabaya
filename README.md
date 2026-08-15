# 🚀 LokerScraper Surabaya

LokerScraper Surabaya is a lightweight, automated IT job aggregator designed to run 24/7 on low-resource ARM devices (such as Armbian STBs / Raspberry Pi) or Docker containers.

It scrapes 5 job platforms (JobStreet, Kalibrr, Glints, LinkedIn, SejutaCita) without browser automation (No Puppeteer/Playwright), filters IT-specific jobs in the Surabaya area, deduplicates listings, sends rich Discord embeds for new jobs, and exposes a Flask REST API.

---

## 🌟 Key Features

- **Multi-Source Lightweight Scraping:** Parallel HTTP requests across 5 platforms.
- **Low Memory Footprint:** Idle `<50MB RAM`, Scraping `<120MB RAM` (Runs smoothly on Armbian STBs with <2GB RAM).
- **Strict IT & Location Filtering:** Filters IT roles (`developer`, `engineer`, `programmer`, `data`, `devops`, `qa`, etc.) located in `Surabaya`, `Sidoarjo`, `Gresik`, `Remote`, or `Hybrid`.
- **Deduplication Engine:** Deterministic MD5 hash ID tracking via `data/seen-ids.json`.
- **Rich Discord Notifications:** Automatic embeds with source-specific colors, salary range, job type, work mode, location, and direct links.
- **Built-in REST API & Scheduler:** Lightweight Flask API (`/api/jobs`, `/api/stats`, `/health`) with integrated background `APScheduler` (every 6 hours).
- **Crash-Resilient Storage:** Atomic file writes with `.bak` backup auto-recovery.

---

## 🛠️ Architecture Overview

```text
[5 Job Scrapers] (Parallel ThreadPool)
  │ Kalibrr | JobStreet | Glints | LinkedIn | SejutaCita
  ▼
[Filter Engine] (Pre-compiled Regex)
  │ IT Keyword Match + Target Location Match
  ▼
[Deduplication Engine] (MD5 Hash Lookup)
  │ Checks seen-ids.json
  ▼
[Atomic Flat File Store] (jobs.json & seen-ids.json)
  ├── Notifies Discord Webhook (New Jobs Only)
  └── Exposes Flask REST API (/api/jobs, /api/stats, /health)
```

---

## 🚀 Quick Start (Local Development)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/nothingser0/lokerscraper-surabaya.git
cd lokerscraper-surabaya
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file:
```bash
cp .env.example .env
```
Edit `.env` and paste your Discord Webhook URL:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your/webhook/url
SCRAPE_INTERVAL_HOURS=6
IT_KEYWORDS=developer,engineer,programmer,backend,frontend,fullstack,mobile,data,devops,qa,tester,web
LOCATIONS=surabaya,sidoarjo,gresik,remote
```

### 3. Run Flask API & Scheduler
```bash
python api/app.py
```
API runs on `http://localhost:5000`.

---

## 📦 Deployment on Armbian STB / Raspberry Pi

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone repo
git clone https://github.com/nothingser0/lokerscraper-surabaya.git /opt/job-scraper
cd /opt/job-scraper

# 2. Setup environment
cp .env.example .env
nano .env  # Add DISCORD_WEBHOOK_URL

# 3. Start container
docker-compose up -d --build
```

### Option B: Native Systemd Service (Low RAM <50MB)

```bash
# 1. Clone repo
git clone https://github.com/nothingser0/lokerscraper-surabaya.git /opt/job-scraper
cd /opt/job-scraper

# 2. Install requirements & configure .env
pip3 install -r requirements.txt
cp .env.example .env
nano .env

# 3. Enable Systemd Service
cp lokerscraper.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now lokerscraper
```

---

## 📡 REST API Documentation

### 1. Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-08-15T17:00:00Z"
}
```

### 2. Aggregated Statistics
```http
GET /api/stats
```
**Response:**
```json
{
  "totalJobs": 78,
  "lastUpdated": "2026-08-15T17:00:00Z",
  "sourceCounts": {
    "JobStreet": 35,
    "LinkedIn": 25,
    "Glints": 14,
    "SejutaCita": 3,
    "Kalibrr": 1
  }
}
```

### 3. Search & Filter Jobs
```http
GET /api/jobs?keyword=developer&source=JobStreet&limit=20&offset=0
```
**Query Parameters:**
- `keyword` (optional): Filter job title by keyword (e.g. `backend`, `flutter`, `react`).
- `source` (optional): Filter by platform (`JobStreet`, `Kalibrr`, `Glints`, `LinkedIn`, `SejutaCita`).
- `days` (optional): Filter jobs scraped within last N days (default: `30`).
- `limit` (optional): Page size limit (default: `20`).
- `offset` (optional): Pagination offset (default: `0`).

---

## 📄 License
MIT License. Created for the Surabaya IT developer community.
