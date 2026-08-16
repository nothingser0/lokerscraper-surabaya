# 🚀 LokerScraper Surabaya

LokerScraper Surabaya is a lightweight, automated IT job aggregator designed to run 24/7 on low-resource ARM devices (such as Armbian STBs / Raspberry Pi) or Docker containers.

It scrapes 5 job platforms (JobStreet, Kalibrr, Glints, LinkedIn, SejutaCita) without browser automation (No Puppeteer/Playwright), filters IT-specific jobs in the Surabaya area, deduplicates listings, sends rich Discord embeds for new jobs, and exposes a Flask REST API.

---

## 🌟 Key Features

- **Multi-Source Lightweight Scraping:** Parallel HTTP requests across 5 platforms.
- **Low Memory Footprint:** Idle `<50MB RAM`, Scraping `<120MB RAM` (Runs smoothly on Armbian STBs with <2GB RAM).
- **Strict IT & Location Filtering:** Filters IT roles (`developer`, `engineer`, `programmer`, `data`, `devops`, `qa`, etc.) located in `Surabaya`, `Sidoarjo`, `Gresik`, `Remote`, or `Hybrid`.
- **Deduplication Engine:** Deterministic MD5 hash ID tracking via `data/seen-ids.json`.
- **Rich Discord Notifications:** Automatic embeds with source-specific colors, salary range, job type, work mode, experience level, location, and direct links. Supports notifying **multiple Discord webhooks**.
- **Optional Bahasa Indonesia Translation:** Job descriptions can be auto-translated to Bahasa Indonesia via DeepL (opt-in — enabled only when `DEEPL_API_KEY` is set).
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

### Notify Multiple Discord Channels

To send notifications to more than one Discord channel/server, use the
comma-separated `DISCORD_WEBHOOK_URLS` variable (takes precedence over
`DISCORD_WEBHOOK_URL`):

```env
DISCORD_WEBHOOK_URLS=https://discord.com/api/webhooks/aaa/bbb,https://discord.com/api/webhooks/ccc/ddd
```

### Random Scrape Interval

By default the scraper runs every `SCRAPE_INTERVAL_HOURS`. To vary the delay
between runs (e.g. to look less bot-like), set a random range:

```env
SCRAPE_INTERVAL_MIN_HOURS=4
SCRAPE_INTERVAL_MAX_HOURS=8
```

When both are set and `MAX > MIN`, each cycle is scheduled with a random delay
between `MIN` and `MAX` hours. Leave both at `0` to use the fixed interval.

### Optional: Translate Job Descriptions to Bahasa Indonesia

By default, job descriptions are kept in their original language. To
auto-translate descriptions to Bahasa Indonesia, set a DeepL API key:

```env
DEEPL_API_KEY=your-deepl-auth-key
DEEPL_API_URL=https://api-free.deepl.com/v2/translate
```

- Leave `DEEPL_API_KEY` empty to disable translation (descriptions stay as-is).
- Free DeepL API uses `https://api-free.deepl.com/v2/translate`; DeepL Pro uses
  `https://api.deepl.com/v2/translate`.
- If the key is missing or the API call fails, descriptions are kept in the
  original language (notifications never break).

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
git clone https://github.com/nothingser0/lokerscraper-surabaya.git
cd lokerscraper-surabaya

# 2. Setup environment
cp .env.example .env
nano .env  # Add DISCORD_WEBHOOK_URL (and optionally TRIGGER_TOKEN)

# 3. Build & start container (detached)
docker compose up -d --build

# 4. Verify it is running
docker compose ps
docker compose logs -f job-scraper
```

The API is exposed on port `5000` of the host. Confirm with:

```bash
curl http://localhost:5000/health
```

> **Note:** Use `docker compose` (v2). If your system only has the legacy
> `docker-compose` (v1) binary, replace `docker compose` with `docker-compose`.

### Option B: Native Systemd Service (Low RAM <50MB)

On Debian/Armbian the system Python is often "externally managed", so install
dependencies into a virtualenv instead of using bare `pip3`:

```bash
# 1. Clone repo
git clone https://github.com/nothingser0/lokerscraper-surabaya.git
cd lokerscraper-surabaya

# 2. Create a virtualenv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
nano .env  # Add DISCORD_WEBHOOK_URL

# 4. Install & enable the systemd service
#    (edit lokerscraper.service first if your WorkingDirectory differs)
sudo cp lokerscraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lokerscraper

# 5. Verify
sudo systemctl status lokerscraper
curl http://localhost:5000/health
```

> **Note:** `lokerscraper.service` points `WorkingDirectory` and `ExecStart` at
> the install path. Update both to match your actual clone location (e.g. a USB
> mount such as `/media/devmon/sda1-usb-SanDisk_Cruzer_B/job-scraper`).

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

### 4. Manually Trigger a Scrape
The scraper normally runs automatically on startup and then every
`SCRAPE_INTERVAL_HOURS`. To run a cycle on demand (for testing), POST to the
trigger endpoint:

```http
POST /api/trigger
```

**Response (202 Accepted):**
```json
{
  "status": "started",
  "message": "Scrape cycle started in background",
  "timestamp": "2026-08-15T17:00:00Z"
}
```

The scrape runs in a background thread, so the endpoint returns immediately.
Watch the logs to see the result (new jobs found, Discord messages sent, etc.).

> **Optional protection:** set `TRIGGER_TOKEN` in `.env` to require the header
> `X-Trigger-Token: <your-token>` on this endpoint. If empty, the endpoint is
> unauthenticated.

---

## 🧪 Testing the Trigger

### Quick test (cURL)

```bash
# 1. Trigger a scrape cycle
curl -X POST http://localhost:5000/api/trigger

# 2. Watch the container/service logs for progress
docker compose logs -f job-scraper          # Docker
# or
sudo journalctl -u lokerscraper -f          # systemd

# 3. After a few seconds, confirm results via the API
curl http://localhost:5000/api/stats
```

If `TRIGGER_TOKEN` is set, include the header:

```bash
curl -X POST -H "X-Trigger-Token: YOUR_TOKEN" http://localhost:5000/api/trigger
```

**What to look for in the logs:**
- `Starting scraper: <ScraperName>` / `Finished <ScraperName>: fetched N jobs`
- `Manual scrape cycle finished: X new jobs found.`
- Discord webhook success (or errors) when new jobs are found.

---

## 📄 License
MIT License. Created for the Surabaya IT developer community.
