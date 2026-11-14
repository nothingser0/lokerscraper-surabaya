# 🚀 LokerScraper Surabaya

<p align="center">
  <img src="docs/assets/dashboard-preview.png" alt="LokerScraper Surabaya Dashboard Preview" width="80%">
</p>

LokerScraper Surabaya is an ultra-lightweight, automated job vacancy aggregator engineered in **Golang** for 24/7 continuous operation on low-resource devices (Armbian TV boxes, Raspberry Pi, 512MB VPS) and Docker containers.

The engine harvests job opportunities across 8 major recruitment platforms concurrently using lightweight goroutines, performs deterministic deduplication and regional/keyword filtering, dispatches real-time alerts to Discord & Telegram, and serves a modern Swiss-editorial web dashboard alongside a JSON REST API.

---

## ✨ Key Features

- **8-Platform Parallel Scraping**: Concurrent data ingestion from Glints, JobStreet, Kalibrr, Karir.com, LinkedIn, RemoteOK, SejutaCita, and Tech in Asia — entirely headless, zero heavy browser dependencies (no Puppeteer/Playwright overhead).
- **Ultra-Low Memory Footprint (Golang)**: Idles at **`~10-12 MB`** RAM, peaks under **`<25 MB`** during active parallel scraping cycles.
- **Single Self-Contained Binary**: Zero runtime interpreter overhead, instant sub-second startup, compiled static executable (~12.5MB).
- **Deterministic Deduplication & Storage**: Pure SQLite database (`data/jobs.db`) with WAL mode (`PRAGMA journal_mode=WAL`), indexed queries, automatic VACUUM pruning, and configurable 30-day retention.
- **Smart N+1 Skipping**: Known jobs recorded in `seen_ids` table bypass detail HTTP roundtrips entirely on repeat runs.
- **Real-Time Notification Dispatch**: Rich embeds delivered to multi-channel Discord Webhooks and Telegram bots with automated error alerting.
- **Editorial Responsive Dashboard**:
  - Live typewriter keyword cycler with responsive font-scaling and lime-highlight emphasis.
  - Interactive search, work mode filters (Remote, Hybrid, On-site), salary sorting, and bookmarks.
  - Built-in live terminal log widget (`scraper.log`) with live polling and auto-fit row trimming.
  - Page jump pagination controls (`Go # →`).
  - Native vertical typographic motivation marquees with edge fade masks.
  - CSV export endpoint (`/api/export`).
- **Secure Remote Access**: Ready for Cloudflare Tunnels (included in Docker compose profile) and private mesh networks (Tailscale/WireGuard). Manual triggers secured via `TRIGGER_TOKEN`.
- **Fault-Tolerant Scheduling**: Built-in background goroutine scheduler with randomized intervals, individual scraper timeouts, and graceful shutdown signal handlers.

---

## 🛠️ System Requirements

- **Go 1.27+** (for bare-metal execution) **or**
- **Docker & Docker Compose** (recommended for 24/7 server / SBC deployment)

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended for Production & TV Boxes)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nothingser0/lokerscraper-surabaya.git
   cd lokerscraper-surabaya
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   *At minimum, set `DISCORD_WEBHOOK_URL` and `TRIGGER_TOKEN`.*

3. **Start the service in background**:
   ```bash
   docker compose up -d --build
   ```

4. **Verify container status**:
   ```bash
   docker compose ps
   docker compose logs -f job-scraper
   ```
   Access the dashboard at `http://localhost:5000` (or `http://[YOUR-DEVICE-IP]:5000`).

---

### Option 2: Native Go Execution (Bare-Metal)

1. **Build the optimized binary**:
   ```bash
   go build -ldflags="-s -w" -o lokerscraper ./cmd/server
   ```

2. **Run the application**:
   ```bash
   ./lokerscraper        # Linux / macOS
   .\lokerscraper.exe    # Windows
   ```

   *Or run directly in development mode:*
   ```bash
   go run ./cmd/server
   ```
   Access the dashboard at `http://127.0.0.1:5000`.

---

## ⚙️ Environment Configuration (`.env`)

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DISCORD_WEBHOOK_URL` | Primary Discord Webhook URL for alerts | `https://discord.com/api/webhooks/...` |
| `DISCORD_WEBHOOK_URLS` | Comma-separated list for multi-channel broadcast | *Optional* |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | *Optional* |
| `TELEGRAM_CHAT_ID` | Target Telegram chat ID | *Optional* |
| `TRIGGER_TOKEN` | Secret token required for manual `/api/trigger` | `yoursecrettoken123` |
| `SCRAPE_INTERVAL_HOURS` | Fixed scrape cycle interval (hours) | `6` |
| `SCRAPE_INTERVAL_MIN_HOURS` | Minimum hours for randomized interval | `3` |
| `SCRAPE_INTERVAL_MAX_HOURS` | Maximum hours for randomized interval | `6` |
| `JOB_RETENTION_DAYS` | Automatically prune jobs older than N days | `30` |
| `KEYWORDS` | Target job title / tech keywords (comma-separated) | `developer,engineer,backend,frontend,...` |
| `LOCATIONS` | Accepted geographical locations and work modes | `surabaya,sidoarjo,gresik,remote` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Zero Trust tunnel token for public domain | *Optional* |

---

## 🌐 Public Domain Access (Cloudflare Tunnel)

Expose the dashboard securely without router port-forwarding or public IP exposure:

### Via Docker Compose:
```bash
# Add CLOUDFLARE_TUNNEL_TOKEN to your .env, then run:
docker compose --profile tunnel up -d
```

### Via Native Systemd Service:
```bash
sudo cp deploy/systemd/cloudflared.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Interactive modern web dashboard |
| `/health` | `GET` | Engine health check & scheduler status |
| `/api/stats` | `GET` | Aggregated statistics, platform counts, DB storage & retention |
| `/api/jobs` | `GET` | Filtered job vacancies (`?keyword=`, `?source=`, `?days=`, `?limit=`, `?offset=`) |
| `/api/logs` | `GET` | Real-time scraper log tail (`?lines=60`) |
| `/api/trigger` | `POST` / `GET` | Manually dispatch a scrape cycle (`X-Trigger-Token` header or `?token=`) |
| `/api/export` | `GET` | Download full vacancies dataset in CSV format |

---

## 🧪 System Verification (Smoke Tests)

Validate SQLite storage operations, scraper registry discovery, and live HTTP API endpoints:

```bash
go test -v ./tests
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
