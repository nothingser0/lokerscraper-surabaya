# 🚀 LokerScraper Surabaya

<p align="center">
  <img src="docs/assets/dashboard-preview.png" alt="LokerScraper Surabaya Dashboard Preview" width="80%">
</p>

LokerScraper Surabaya is an ultra-lightweight, automated job vacancy aggregator engineered in **Golang** for 24/7 continuous operation on low-resource devices (Armbian TV boxes, Raspberry Pi, 512MB VPS) and Docker containers.

The engine harvests job opportunities across 8 major recruitment platforms concurrently using lightweight goroutines, performs deterministic 2-layer deduplication and regional/keyword filtering, dispatches real-time alerts to Discord & Telegram, and serves a modern Swiss-editorial web dashboard alongside a JSON REST API.

---

## ✨ Key Features

- **8-Platform Parallel Scraping**: Concurrent data ingestion from **Glints** (GraphQL API), **JobStreet**, **Kalibrr**, **Karir.com**, **LinkedIn**, **RemoteOK**, **SejutaCita**, and **Tech in Asia** — entirely headless, zero heavy browser dependencies (no Puppeteer/Playwright overhead).
- **Ultra-Low Memory Footprint (Golang)**: Idles at **`~10-12 MB`** RAM, peaks under **`<25 MB`** during active parallel scraping cycles.
- **Multi-Arch Docker & Single Binary**: Prebuilt multi-arch Docker images (`linux/amd64` & `linux/arm64`) published to GitHub Container Registry (`ghcr.io`), or compile as a single self-contained binary (~12.5MB) with zero runtime dependencies.
- **2-Layer Deterministic Deduplication & Storage**:
  - **Layer 1 (URL ID Hash)** + **Layer 2 (Content Signature `title + company + location`)** to prevent duplicate alerts even when job URLs change or cross-post across platforms.
  - Pure SQLite database (`data/jobs.db`) with WAL mode (`PRAGMA journal_mode=WAL`), indexed queries, automatic VACUUM pruning, and configurable 30-day retention.
  - Automatic cleanup of daily text logs (`data/jobs_YYYY-MM-DD.txt`) and auto-rotation of `logs/scraper.log` (capped at 5MB) to protect SD cards / eMMC storage.
- **Smart N+1 Skipping**: Known jobs recorded in `seen_ids` or `jobs` bypass detail HTTP roundtrips entirely on repeat runs, plus early keyword pre-filtering before fetching detail pages.
- **Real-Time Notification Dispatch**: Rich embeds delivered to multi-channel Discord Webhooks and Telegram bots with dedicated error-alerting channels.
- **Editorial Responsive Dashboard**:
  - Live typewriter keyword cycler with responsive font-scaling and lime-highlight emphasis.
  - Interactive search, work mode filters (Remote, Hybrid, On-site), salary sorting, and bookmarks.
  - Built-in live terminal log widget (`scraper.log`) with 64KB tail-seek API, color-coded Go logs, and tab-visibility polling pause.
  - Page jump pagination controls (`Go # →`) and CSV export endpoint (`/api/export`).
- **Secure Remote Access**: Ready for Cloudflare Tunnels (included in Docker Compose profile) and private mesh networks (Tailscale/WireGuard). Manual triggers secured via `TRIGGER_TOKEN`.
- **Fault-Tolerant Scheduling**: Built-in background goroutine scheduler with randomized intervals, individual scraper timeouts, and graceful shutdown signal handlers.

---

## 🛠️ System Requirements

- **Docker & Docker Compose** (recommended for 24/7 server / Armbian STB / Raspberry Pi deployment) **or**
- **Go 1.25+** (for bare-metal execution)

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended for Production & TV Boxes)

Prebuilt multi-arch images (`linux/amd64` & `linux/arm64`) are automatically published to `ghcr.io/nothingser0/lokerscraper-surabaya:latest`.

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

3. **Pull prebuilt image & start in background** *(no local compilation needed)*:
   ```bash
   docker compose pull
   docker compose up -d
   ```
   *(Or build locally from source with `docker compose up -d --build`)*

4. **Verify container status**:
   ```bash
   docker compose ps
   docker compose logs -f job-scraper
   ```
   Access the dashboard at `http://localhost:5000` (or `http://[YOUR-DEVICE-IP]:5000`).

---

### Option 2: Native Go Execution (Bare-Metal / Systemd)

1. **Build the optimized binary**:
   ```bash
   go build -buildvcs=false -ldflags="-s -w" -o lokerscraper ./cmd/server
   ```

2. **Run the application**:
   ```bash
   ./lokerscraper        # Linux / macOS
   .\lokerscraper.exe    # Windows
   ```

   *Or install as a native Linux systemd service:*
   ```bash
   sudo cp deploy/systemd/lokerscraper.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now lokerscraper.service
   ```
   Access the dashboard at `http://127.0.0.1:5000`.

---

## ⚙️ Environment Configuration (`.env`)

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DISCORD_WEBHOOK_URL` | Primary Discord Webhook URL for job alerts | `https://discord.com/api/webhooks/...` |
| `DISCORD_WEBHOOK_URLS` | Comma-separated list for multi-channel broadcast | *Optional* |
| `DISCORD_ERROR_WEBHOOK_URL` | Dedicated Discord Webhook URL for scraper error alerts | *Optional (falls back to primary)* |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | *Optional* |
| `TELEGRAM_CHAT_ID` | Target Telegram chat ID for job alerts | *Optional* |
| `TELEGRAM_ERROR_CHAT_ID` | Dedicated Telegram chat ID for scraper error alerts | *Optional (falls back to primary)* |
| `TRIGGER_TOKEN` | Secret token required for manual `/api/trigger` | `yoursecrettoken123` |
| `SCRAPE_INTERVAL_HOURS` | Fixed scrape cycle interval (hours) | `6` |
| `SCRAPE_INTERVAL_MIN_HOURS` | Minimum hours for randomized interval | `3` |
| `SCRAPE_INTERVAL_MAX_HOURS` | Maximum hours for randomized interval | `6` |
| `MAX_WORKERS` | Maximum concurrent platform scrapers | `4` |
| `JOB_RETENTION_DAYS` | Automatically prune jobs & daily logs older than N days | `30` |
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
| `/api/jobs` | `GET` | Filtered job vacancies (`?keyword=`, `?source=`, `?days=`, `?limit=`, `?offset=`, `?full=1`) |
| `/api/logs` | `GET` | Real-time scraper log tail (`?lines=60`, fast 64KB tail seek) |
| `/api/trigger` | `POST` / `GET` | Manually dispatch a scrape cycle (`X-Trigger-Token` header, `?token=`, `?force=true`) |
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

