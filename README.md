# 🚀 LokerScraper Surabaya

<p align="center">
  <img src="docs/assets/dashboard-preview.png" alt="LokerScraper Surabaya Dashboard Preview" width="100%">
</p>

LokerScraper Surabaya adalah aplikasi agregator lowongan kerja otomatis yang dirancang ringan, efisien, dan dapat berjalan 24/7 di perangkat berdaya rendah (seperti STB Armbian, Raspberry Pi, server mini) maupun container Docker.

Aplikasi ini mengumpulkan data lowongan kerja dari berbagai platform populer, menyaring posisi dan lokasi target secara otomatis, mencegah duplikasi data, mengirim notifikasi embed ke Discord/Telegram, serta menyediakan dashboard web modern dan REST API.

---

## ✨ Fitur Utama

- **Multi-Platform Scraper**: Pengambilan data secara paralel dari 6 platform (JobStreet, LinkedIn, Glints, Kalibrr, SejutaCita, dan Tech in Asia) tanpa browser automation berat (bebas Puppeteer/Playwright).
- **Sangat Hemat Resource**: Penggunaan RAM idle `<50MB` dan saat aktif scraping `<120MB`.
- **Filtering & Deduplikasi Cerdas**: Menyaring lowongan berdasarkan kata kunci (`KEYWORDS`) dan wilayah target (`LOCATIONS`). Dilengkapi sistem hashing deterministik untuk mencegah data ganda.
- **Penyimpanan SQLite Andal**: Menggunakan database SQLite lokal (`data/jobs.db`) dengan indexed query dan auto-pruning VACUUM.
- **Notifikasi Real-time**: Mengirim alert embed kaya informasi ke Discord Webhook (mendukung multi-channel) dan Telegram Bot.
- **Dashboard Web Responsif**: Tampilan web modern bergaya editorial poster dengan pencarian real-time, filter mode kerja (Remote/Hybrid/On-site), sortir gaji, tombol simpan favorit (bookmark privat), dan ekspor CSV.
- **Aman Diakses Jarak Jauh**: Siap diakses melalui jaringan lokal maupun VPN mesh privat (seperti Tailscale). Tombol trigger manual dilindungi oleh `TRIGGER_TOKEN`.
- **Auto-Recovery**: Penjadwalan otomatis berkala via background scheduler dengan toleransi kegagalan dan auto-restart.

---

## 🛠️ Persyaratan Sistem

- Python 3.10+ (untuk instalasi native) **atau**
- Docker & Docker Compose (rekomendasi untuk server / STB)

---

## 🚀 Panduan Menjalankan

### Opsi 1: Menggunakan Docker (Rekomendasi untuk STB / Server)

1. **Clone repositori**:
   ```bash
   git clone https://github.com/nothingser0/lokerscraper-surabaya.git
   cd lokerscraper-surabaya
   ```

2. **Salin dan sesuaikan konfigurasi environment**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   *Isi minimal `DISCORD_WEBHOOK_URL` dan `TRIGGER_TOKEN`.*

3. **Jalankan container di latar belakang**:
   ```bash
   docker compose up -d --build
   ```

4. **Periksa status dan log**:
   ```bash
   docker compose ps
   docker compose logs -f job-scraper
   ```
   Dashboard dapat diakses di browser melalui `http://localhost:5000` (atau `http://[IP-STB-ANDA]:5000`).

---

### Opsi 2: Instalasi Lokal (Python Langsung)

1. **Persiapan virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate       # Linux / macOS
   # venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

2. **Siapkan file `.env`**:
   ```bash
   cp .env.example .env
   ```

3. **Jalankan server aplikasi**:
   ```bash
   python api/app.py
   ```
   Aplikasi dan scheduler otomatis berjalan di `http://localhost:5000`.

---

## ⚙️ Konfigurasi Environment (`.env`)

| Variabel | Keterangan | Nilai Bawaan / Contoh |
| :--- | :--- | :--- |
| `DISCORD_WEBHOOK_URL` | URL Webhook Discord untuk notifikasi | `https://discord.com/api/webhooks/...` |
| `DISCORD_WEBHOOK_URLS`| Daftar multi-webhook Discord (pisahkan dengan koma) | Opsi jika ingin kirim ke banyak channel |
| `TELEGRAM_BOT_TOKEN`  | Token bot Telegram (opsional) | Kosongkan jika tidak dipakai |
| `TELEGRAM_CHAT_ID`    | ID chat Telegram (opsional) | Kosongkan jika tidak dipakai |
| `TRIGGER_TOKEN`       | Kata sandi untuk memicu scraping manual | Bebas (contoh: `kuncirahasia123`) |
| `SCRAPE_INTERVAL_HOURS` | Interval jeda scraping otomatis (jam) | `6` |
| `SCRAPE_INTERVAL_MIN_HOURS` | Batas minimal interval acak | `3` |
| `SCRAPE_INTERVAL_MAX_HOURS` | Batas maksimal interval acak | `6` |
| `KEYWORDS`            | Kata kunci pencarian judul lowongan | `developer,engineer,programmer,data,qa,...` |
| `LOCATIONS`           | Wilayah dan mode kerja yang diterima | `surabaya,sidoarjo,gresik,remote` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token Cloudflare Zero Trust (opsional jika pakai domain sendiri) | `eyJh...` |

---

## 🌐 Mengakses Publik Menggunakan Domain Sendiri (Cloudflare Tunnel)

Jika Anda ingin dashboard dapat diakses publik dari mana saja dengan domain Anda (misal `https://loker.omahkene.my.id`) tanpa membuka port router / port forwarding:

### Menggunakan Docker Compose (Profile Tunnel):
1. Tambahkan token tunnel Cloudflare di `.env`:
   ```env
   CLOUDFLARE_TUNNEL_TOKEN=eyJh...
   ```
2. Jalankan container scraper sekaligus tunnel-nya:
   ```bash
   docker compose --profile tunnel up -d
   ```

### Menggunakan Native Systemd Service:
1. Pasang file service tunnel ke direktori systemd:
   ```bash
   sudo cp cloudflared.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared.service
   ```

---

## 📡 REST API Endpoint

Aplikasi ini menyediakan antarmuka API siap pakai:

- `GET /` — Halaman antarmuka web dashboard interaktif.
- `GET /health` — Status kesehatan aplikasi & background scheduler.
- `GET /api/stats` — Statistik total lowongan, daftar platform aktif, dan waktu update terakhir.
- `GET /api/jobs` — Mengambil data lowongan dengan parameter pencarian:
  - `?keyword=...` (filter posisi / teknologi)
  - `?source=...` (filter platform tertentu)
  - `?limit=...` & `?offset=...` (paginasi data)
- `POST /api/trigger` — Memicu siklus scraping secara instan (memerlukan header `X-Trigger-Token: <token>` jika `TRIGGER_TOKEN` diatur).
- `GET /api/export` — Mengunduh seluruh data lowongan dalam format file CSV.

---

## 🧪 Pengujian Sistem (Smoke Test)

Untuk memastikan seluruh koneksi scraper, database SQLite, dan endpoint API berfungsi normal:

```bash
python tests/smoke_test.py
```

---

## 📄 Lisensi

Proyek ini didistribusikan di bawah lisensi [MIT License](LICENSE).
