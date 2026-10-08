import logging
import sys
import threading
from pathlib import Path

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "scraper.log",
            mode='a',
            encoding='utf-8'
        )
    ]
)

# Ensure the project root is on sys.path so that `python api/app.py`
# (used by Docker CMD, systemd ExecStart, and local dev) can resolve
# sibling top-level packages: config, storage, engine, scrapers, notifiers.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from config import config, random_scrape_interval_hours
from storage import StorageService
from engine.runner import ScraperRunner

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "static"), static_url_path="/static")

@app.route("/static/<path:filename>")
def custom_static(filename):
    from flask import send_from_directory
    return send_from_directory(str(PROJECT_ROOT / "static"), filename)

storage_service = StorageService()
last_scraped_at: Optional[str] = None

def scheduled_scrape_job():
    global last_scraped_at
    logger.info("Triggering scheduled scrape cycle...")
    try:
        runner = ScraperRunner()
        result = runner.run_cycle()
        last_scraped_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Scheduled scrape cycle finished: {result.get('new_jobs_count', 0)} new jobs found.")
    except Exception as e:
        logger.error(f"Error in scheduled scrape cycle: {e}", exc_info=True)


scheduler = BackgroundScheduler(daemon=True)
scrape_interval_hours = getattr(config, "SCRAPE_INTERVAL_HOURS", 6)
scheduler.add_job(
    scheduled_scrape_job,
    'interval',
    hours=scrape_interval_hours,
    id='scraper_cycle_job',
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1)
)
scheduler.start()

@app.route("/", methods=["GET"])
def dashboard():
    """Serve a clean Swiss/editorial modern dashboard inspired by the reference design."""
    return """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LokerScraper Surabaya</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: { sans: ['"Plus Jakarta Sans"', 'sans-serif'] },
          colors: {
            cream: '#F4F4F0',
            ink: '#111111',
            limepill: '#D4F542',
            softgray: '#E6E6E1',
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #ECECE8; color: #111111; }
    .display-title { letter-spacing: -0.04em; line-height: 0.92; font-weight: 800; }
    .pill-btn { border-radius: 9999px; }
    .noise-bg {
      background-image: radial-gradient(rgba(0,0,0,0.06) 1px, transparent 0);
      background-size: 24px 24px;
    }
    /* Show side marquees ONLY on screen widths 1536px and above */
    .marquee-sidebar {
      display: none;
    }
    @media (min-width: 1536px) {
      .marquee-sidebar {
        display: flex;
      }
    }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    /* Left (-90 deg): Jalan dari Atas ke Bawah */
    @keyframes scrollKiriDown {
      0% { transform: translate(-50%, -50%) rotate(-90deg) translateX(70vh); }
      100% { transform: translate(-50%, -50%) rotate(-90deg) translateX(-70vh); }
    }
    /* Right (90 deg): Jalan dari Bawah ke Atas */
    @keyframes scrollKananUp {
      0% { transform: translate(-50%, -50%) rotate(90deg) translateX(70vh); }
      100% { transform: translate(-50%, -50%) rotate(90deg) translateX(-70vh); }
    }
    .text-kiri-sync {
      position: absolute;
      top: 50%;
      left: 50%;
      white-space: nowrap;
      will-change: transform;
      animation: scrollKiriDown 24s linear infinite;
    }
    .text-kanan-sync {
      position: absolute;
      top: 50%;
      left: 50%;
      white-space: nowrap;
      will-change: transform;
      animation: scrollKananUp 24s linear infinite;
    }
  </style>
</head>
<body class="p-3 sm:p-6 md:p-10 antialiased selection:bg-limepill selection:text-black noise-bg min-h-screen w-full overflow-x-hidden">
  
  <!-- 1. Kiri di tengah, -90 derajat, arah jalan atas ke bawah -->
  <div class="marquee-sidebar fixed left-0 top-0 bottom-0 w-[calc((100vw-1152px)/2)] pointer-events-none select-none z-0 overflow-hidden">
    <div class="text-kiri-sync text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter text-black/[0.13] uppercase select-none">
      BUILD THE FUTURE • SOLVE REAL PROBLEMS • NEVER SETTLE
    </div>
  </div>

  <!-- 2. Kanan di tengah, 90 derajat, arah jalan bawah ke atas -->
  <div class="marquee-sidebar fixed right-0 top-0 bottom-0 w-[calc((100vw-1152px)/2)] pointer-events-none select-none z-0 overflow-hidden">
    <div class="text-kanan-sync text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter text-black/[0.13] uppercase select-none">
      CREATE MASTERY • CODE WITH PURPOSE • SHIP WITH PRIDE
    </div>
  </div>

  <div class="max-w-6xl mx-auto space-y-4 md:space-y-6 relative z-10 w-full">
    
    <!-- Editorial Top Hero Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      
      <!-- Left Large Card (Typography & Stats) -->
      <div class="lg:col-span-8 bg-[#F8F8F5] rounded-3xl p-5 sm:p-7 md:p-10 border border-black/5 shadow-sm flex flex-col justify-between space-y-6 md:space-y-8">
        <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span id="heroStreamBadge" class="text-xs font-semibold tracking-wider uppercase text-neutral-500">Live Stream</span>
          </div>
          <!-- Desktop Nav Actions -->
          <div class="hidden sm:flex items-center gap-2">
            <button id="triggerBtn" onclick="triggerScrape()" class="pill-btn bg-limepill hover:brightness-95 text-black font-semibold px-4 py-2 text-xs flex items-center gap-1.5 transition">
            <span>Scrape Now</span>
              <span>↗</span>
          </button>
            <a href="/api/export" class="pill-btn bg-white hover:bg-neutral-100 text-black border border-black/10 px-3.5 py-2 text-xs font-medium transition flex items-center gap-1">
              <span>Export CSV</span>
              <span>↓</span>
            </a>
            <a href="/api/jobs" target="_blank" class="pill-btn bg-black text-white hover:bg-neutral-800 px-4 py-2 text-xs transition">API</a>
          </div>
          <!-- Mobile 3-Bar Hamburger Trigger -->
          <div class="relative sm:hidden">
            <button onclick="toggleMobileNav()" class="w-9 h-9 rounded-full bg-neutral-900 border border-neutral-800 text-white flex items-center justify-center text-sm focus:outline-none">
              ≡
          </button>
            <div id="mobileNavMenu" class="hidden absolute right-0 mt-2 w-44 bg-[#181818] border border-neutral-700/80 rounded-2xl shadow-2xl p-2 z-50 text-xs space-y-1">
              <button onclick="toggleMobileNav(); triggerScrape()" class="w-full text-left bg-limepill text-black font-bold px-3 py-2 rounded-xl flex items-center justify-between">
            <span>Scrape Now</span>
              <span>↗</span>
          </button>
              <a href="/api/export" class="block w-full text-left text-neutral-200 hover:bg-neutral-800 px-3 py-2 rounded-xl transition">
                Export CSV ↓
            </a>
              <a href="/api/jobs" target="_blank" class="block w-full text-left text-neutral-200 hover:bg-neutral-800 px-3 py-2 rounded-xl transition">
                JSON API ↗
            </a>
          </div>
          </div>
        </div>

        <div class="space-y-1.5 max-w-full">
          <h1 class="display-title font-black tracking-tight text-neutral-900 leading-none">
            <div id="heroWordMain" class="text-5xl sm:text-7xl md:text-8xl">Developer</div>
            <div class="flex items-end gap-3 text-4xl sm:text-6xl md:text-7xl mt-1">
              <span class="leading-none">Jobs</span>
              <span class="inline-flex items-center justify-center bg-black text-limepill font-black px-3.5 py-1 sm:px-4 sm:py-1.5 rounded-full text-base sm:text-2xl md:text-3xl shadow-sm tracking-normal leading-none mb-0.5">
              <span id="statTotal">-</span>
            </span>
            </div>
          </h1>
          <h2 id="heroSubtitle" class="display-title text-2xl sm:text-4xl md:text-5xl font-bold text-neutral-400 pt-1">
            Surabaya & Remote
          </h2>
        </div>

        <!-- Dynamic Tags from ENV: Matching Reference Poster Typography -->
        <div class="pt-3 border-t border-black/5 space-y-3 font-sans">
          <div class="space-y-1.5">
            <div class="font-bold tracking-widest text-[10px] text-neutral-400 uppercase">LOCATIONS</div>
            <div id="envLocations" class="flex flex-wrap gap-1.5">Loading...</div>
          </div>
          <div class="space-y-1.5">
            <div class="font-bold tracking-widest text-[10px] text-neutral-400 uppercase">KEYWORDS</div>
            <div id="envKeywords" class="flex flex-wrap gap-1.5">Loading...</div>
          </div>
        </div>

        <!-- 3 & 4. Bottom Stats: Last Update Real & Platform Counter Berkontras Jelas -->
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 pt-4 border-t border-black/5 text-xs">
          <div class="md:col-span-5">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Last Updated</div>
            <div id="statUpdated" class="font-semibold text-neutral-800 mt-1">-</div>
          </div>
          <div class="md:col-span-3">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Cycle Status</div>
            <div id="statScraped" class="font-semibold text-neutral-800 mt-1">-</div>
          </div>
          <div class="md:col-span-4">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Platforms</div>
            <div id="statSources" class="flex flex-wrap gap-1.5 mt-1.5 items-center">-</div>
          </div>
        </div>
      </div>

      <!-- Right Visual Hero Card: Real programmer typing at workstation -->
      <div class="lg:col-span-4 bg-neutral-900 rounded-3xl overflow-hidden relative min-h-[260px] sm:min-h-[320px] border border-black/10 shadow-sm group">
        <img src="/static/hero.gif" alt="Professional Developer at Work" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition duration-700 brightness-90">
        <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>
        <div class="absolute top-5 right-5 flex items-center gap-1.5 bg-black/60 backdrop-blur-md px-3 py-1 rounded-full border border-white/10 text-[11px] font-semibold text-limepill">
          <span class="w-2 h-2 rounded-full bg-limepill animate-ping"></span>
          <span>Online Radar</span>
        </div>
        <div class="absolute bottom-6 left-6 right-6 text-white space-y-2">
          <div id="platformCountBadge" class="inline-block px-2.5 py-0.5 rounded-full bg-limepill text-black text-[10px] font-black uppercase tracking-wider">
            Multi-Platform
          </div>
          <p id="platformNamesBanner" class="text-sm font-semibold leading-snug text-neutral-100">
            Continuous automated aggregation across registered platforms.
          </p>
        </div>
      </div>

    </div>

    <!-- Jobs Feed Section (Dark Contrast block as in reference) -->
    <div id="curatedSection" class="bg-[#111111] text-white rounded-3xl p-4 sm:p-6 md:p-8 space-y-5 md:space-y-6">
      
      <!-- Section Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800 pb-5">
        <div>
          <div class="inline-block px-3 py-1 rounded-full border border-neutral-700 text-[11px] uppercase tracking-wider text-neutral-400 mb-2">Curated Stream</div>
          <h3 class="text-2xl md:text-3xl font-bold tracking-tight">Active Opportunities</h3>
        </div>
        <div class="w-full md:w-auto flex flex-col md:flex-row md:items-center gap-2.5">
          <div class="grid grid-cols-2 sm:grid-cols-4 md:flex md:items-center gap-2 w-full md:w-auto">
          <button id="bookmarkToggle" onclick="toggleBookmarksOnly()" class="bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-4 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1.5 transition w-full md:w-auto">
            <span class="w-2 h-2 rounded-full border border-neutral-500" id="bookmarkIndicator"></span>
            <span>Saved</span>
            <span id="bookmarkCount" class="text-[10px] text-neutral-400 font-mono">(0)</span>
          </button>
          <div class="relative w-full md:w-auto col-span-1" id="customDropdownWrapper">
            <button id="sourceFilterBtn" onclick="togglePlatformMenu()" type="button" class="bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-7 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1 transition w-full md:w-auto">
              <span id="sourceFilterLabel">All Platforms</span>
              <span class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[9px] text-neutral-400">▼</span>
            </button>
            <div id="sourceFilterMenu" class="hidden absolute right-0 md:left-0 mt-2 w-48 bg-[#181818] border border-neutral-700/80 rounded-2xl shadow-2xl py-1.5 z-50 text-xs overflow-hidden backdrop-blur-md">
            </div>
          </div>

          <div class="relative w-full md:w-auto col-span-1" id="modeDropdownWrapper">
            <button onclick="toggleModeMenu()" type="button" class="bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-7 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1 transition w-full md:w-auto">
              <span id="modeFilterLabel">All Modes</span>
              <span class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[9px] text-neutral-400">▼</span>
            </button>
            <div id="modeFilterMenu" class="hidden absolute left-0 mt-2 w-44 bg-[#181818] border border-neutral-700/80 rounded-2xl shadow-2xl py-1.5 z-50 text-xs overflow-hidden backdrop-blur-md">
              <div onclick="selectMode('', 'All Modes')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-200 cursor-pointer transition">All Modes</div>
              <div onclick="selectMode('remote', 'Remote')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer transition">Remote</div>
              <div onclick="selectMode('hybrid', 'Hybrid')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer transition">Hybrid</div>
              <div onclick="selectMode('on-site', 'On-site')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer transition">On-site</div>
            </div>
          </div>

          <div class="relative w-full md:w-auto col-span-1" id="sortDropdownWrapper">
            <button onclick="toggleSortMenu()" type="button" class="bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-7 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1 transition w-full md:w-auto">
              <span id="sortFilterLabel">Newest</span>
              <span class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[9px] text-neutral-400">▼</span>
            </button>
            <div id="sortFilterMenu" class="hidden absolute right-0 mt-2 w-48 bg-[#181818] border border-neutral-700/80 rounded-2xl shadow-2xl py-1.5 z-50 text-xs overflow-hidden backdrop-blur-md">
              <div onclick="selectSort('newest', 'Newest')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-200 cursor-pointer transition">Newest First</div>
              <div onclick="selectSort('salary_high', 'Highest Salary')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer transition">Highest Salary</div>
              <div onclick="selectSort('title_asc', 'Title (A–Z)')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer transition">Title (A–Z)</div>
            </div>
          </div>
          </div>

          <div class="relative w-full md:w-56 md:flex-initial">
            <input type="text" id="searchInput" oninput="currentPage=1; renderJobs()" placeholder="Search jobs, tech..." class="w-full bg-[#1A1A1A] text-neutral-100 placeholder-neutral-500 border border-neutral-800 rounded-full pl-9 pr-4 py-2 text-xs font-medium focus:outline-none focus:border-limepill transition">
            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500 text-xs">⌕</span>
          </div>
        </div>
      </div>

      <!-- Job Cards Stream -->
      <div id="jobsList" class="space-y-2.5">
        <div class="text-neutral-500 text-sm py-8 text-center">Loading live positions...</div>
      </div>

      <!-- Pagination Controls (Editorial style as in reference bottom circles) -->
      <div id="paginationContainer" class="pt-6 pb-6 sm:pb-3 border-t border-neutral-800 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-neutral-400">
        <div id="paginationInfo">Showing 0-0 of 0</div>
        <div class="flex items-center gap-2">
          <button id="prevBtn" onclick="changePage(-1)" class="w-9 h-9 rounded-full bg-neutral-800 hover:bg-neutral-700 disabled:opacity-30 disabled:hover:bg-neutral-800 flex items-center justify-center text-white transition">
            ‹
          </button>
          <span id="pageBadge" class="px-3 py-1 bg-neutral-900 border border-neutral-800 rounded-full text-white font-medium">Page 1 / 1</span>
          <button id="nextBtn" onclick="changePage(1)" class="w-9 h-9 rounded-full bg-limepill hover:brightness-95 disabled:opacity-30 disabled:bg-neutral-800 flex items-center justify-center text-black font-bold transition">
            ›
          </button>
        </div>
      </div>

    </div>

  </div>

  <script>
    let allJobs = [];
    let currentPage = 1;
    const pageSize = 10;
    let showBookmarksOnly = false;
    let selectedPlatform = '';
    let selectedMode = '';
    let selectedSort = 'newest';

    function toggleMobileNav() {
      const m = document.getElementById('mobileNavMenu');
      if (m) m.classList.toggle('hidden');
    }

    function togglePlatformMenu() {
      const menu = document.getElementById('sourceFilterMenu');
      menu.classList.toggle('hidden');
    }

    function toggleModeMenu() {
      document.getElementById('modeFilterMenu').classList.toggle('hidden');
    }

    function toggleSortMenu() {
      document.getElementById('sortFilterMenu').classList.toggle('hidden');
    }

    function selectPlatform(val, label) {
      selectedPlatform = val;
      document.getElementById('sourceFilterLabel').innerText = label;
      document.getElementById('sourceFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    function selectMode(val, label) {
      selectedMode = val;
      document.getElementById('modeFilterLabel').innerText = label;
      document.getElementById('modeFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    function selectSort(val, label) {
      selectedSort = val;
      document.getElementById('sortFilterLabel').innerText = label;
      document.getElementById('sortFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
      const wrapper = document.getElementById('customDropdownWrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        document.getElementById('sourceFilterMenu').classList.add('hidden');
      }
      const modeW = document.getElementById('modeDropdownWrapper');
      if (modeW && !modeW.contains(e.target)) {
        document.getElementById('modeFilterMenu').classList.add('hidden');
      }
      const sortW = document.getElementById('sortDropdownWrapper');
      if (sortW && !sortW.contains(e.target)) {
        document.getElementById('sortFilterMenu').classList.add('hidden');
      }
    });

    function getSavedIds() {
      try { return JSON.parse(localStorage.getItem('saved_jobs') || '[]'); } catch { return []; }
    }

    function toggleSaveJob(id) {
      let saved = getSavedIds();
      if (saved.includes(id)) { saved = saved.filter(x => x !== id); }
      else { saved.push(id); }
      localStorage.setItem('saved_jobs', JSON.stringify(saved));
      updateBookmarkUI();
      renderJobs();
    }

    function updateBookmarkUI() {
      const count = getSavedIds().length;
      const badge = document.getElementById('bookmarkCount');
      if (badge) badge.innerText = count;
    }

    function toggleBookmarksOnly() {
      showBookmarksOnly = !showBookmarksOnly;
      currentPage = 1;
      const btn = document.getElementById('bookmarkToggle');
      const indicator = document.getElementById('bookmarkIndicator');
      if (showBookmarksOnly) {
        btn.className = 'bg-limepill text-black font-bold border border-limepill rounded-full pl-3.5 pr-4 py-2 text-xs tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1.5 transition w-full md:w-auto';
        if (indicator) indicator.className = 'w-2 h-2 rounded-full bg-black';
      } else {
        btn.className = 'bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-4 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center justify-between md:justify-start gap-1.5 transition w-full md:w-auto';
        if (indicator) indicator.className = 'w-2 h-2 rounded-full border border-neutral-500';
      }
      renderJobs();
    }
    
    function formatUpdatedDate(isoString) {
      if (!isoString) return '-';
      try {
        const d = new Date(isoString);
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        const dayName = days[d.getDay()];
        const date = d.getDate();
        const monthName = months[d.getMonth()];
        const year = d.getFullYear();
        const hours = String(d.getHours()).padStart(2, '0');
        const mins = String(d.getMinutes()).padStart(2, '0');
        return `${dayName}, ${date} ${monthName} ${year} • ${hours}:${mins} WIB`;
      } catch {
        return isoString;
      }
    }

    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('statTotal').innerText = data.totalJobs || '0';
        document.getElementById('statUpdated').innerText = formatUpdatedDate(data.lastUpdated);
        document.getElementById('statScraped').innerText = data.lastScrapedAt ? formatUpdatedDate(data.lastScrapedAt) : 'Running normally';
        
        // Dynamic Locations & Keywords from ENV
        if (data.locations && data.locations.length) {
          const primaryLoc = data.locations[0].charAt(0).toUpperCase() + data.locations[0].slice(1);
          document.getElementById('heroSubtitle').innerText = `${primaryLoc} & Remote`;
          document.getElementById('heroStreamBadge').innerText = `${primaryLoc} Opportunities`;
          document.getElementById('envLocations').innerHTML = data.locations.map(l => 
            `<span class="bg-black/5 border border-black/10 px-3 py-1 rounded-full capitalize font-extrabold text-[11px] tracking-tight text-neutral-500">${l}</span>`
          ).join('');
        }
        if (data.keywords && data.keywords.length) {
          const primaryKw = data.keywords[0].charAt(0).toUpperCase() + data.keywords[0].slice(1);
          document.getElementById('heroWordMain').innerText = primaryKw;
          document.getElementById('envKeywords').innerHTML = data.keywords.slice(0, 10).map(k => 
            `<span class="bg-limepill text-black border border-black/10 px-3 py-1 rounded-full font-extrabold text-[11px] tracking-tight shadow-sm">${k}</span>`
          ).join('') + (data.keywords.length > 10 ? `<span class="text-neutral-500 text-[11px] font-bold self-center">+${data.keywords.length - 10} more</span>` : '');
        }

        if (data.sourceCounts) {
          const sources = Object.keys(data.sourceCounts);
          document.getElementById('statSources').innerHTML = Object.entries(data.sourceCounts)
            .map(([k, v]) => `<span class="inline-flex items-center gap-1.5 bg-neutral-900 text-neutral-200 border border-neutral-700/80 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide"><span>${k}</span><span class="bg-limepill text-black font-black px-1.5 py-0.2 rounded-full text-[10px]">${v}</span></span>`).join('');
          
          if (sources.length) {
            document.getElementById('platformCountBadge').innerText = `${sources.length} Aggregators`;
            document.getElementById('platformNamesBanner').innerText = `Continuous automated aggregation across ${sources.join(', ')}.`;
            
            // Populate custom rounded popup menu
            const menuEl = document.getElementById('sourceFilterMenu');
            menuEl.innerHTML = `
              <div onclick="selectPlatform('', 'All Platforms')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-200 cursor-pointer flex items-center justify-between transition">
                <span>All Platforms</span>
              </div>` +
              sources.map(s => `
                <div onclick="selectPlatform('${s}', '${s} (${data.sourceCounts[s]})')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer flex items-center justify-between transition">
                  <span>${s}</span>
                  <span class="text-[10px] bg-neutral-800 px-1.5 py-0.5 rounded-full text-neutral-400">${data.sourceCounts[s]}</span>
                </div>
              `).join('');
          }
        }
      } catch (e) { console.error(e); }
    }

    async function loadJobs() {
      try {
        const res = await fetch('/api/jobs?limit=500');
        const data = await res.json();
        allJobs = data.jobs || [];
        currentPage = 1;
        renderJobs();
      } catch (e) {
        document.getElementById('jobsList').innerHTML = '<div class="text-neutral-500 text-sm py-4">Failed to load opportunities.</div>';
      }
    }

    function formatSalary(j) {
      if (j.salary) return j.salary;
      if (j.salary_min && j.salary_max) {
        const min = (j.salary_min / 1000000).toFixed(j.salary_min % 1000000 === 0 ? 0 : 1);
        const max = (j.salary_max / 1000000).toFixed(j.salary_max % 1000000 === 0 ? 0 : 1);
        return `IDR ${min}M – ${max}M`;
      }
      if (j.salary_min) return `IDR ${(j.salary_min / 1000000).toFixed(0)}M+`;
      return 'NOT DISCLOSED';
    }

    function translateWorkType(val) {
      if (!val) return null;
      const lower = val.toLowerCase();
      if (lower.includes('kontrak') || lower.includes('sementara')) return 'CONTRACT';
      if (lower.includes('penuh') || lower.includes('full')) return 'FULL TIME';
      if (lower.includes('paruh') || lower.includes('part')) return 'PART TIME';
      if (lower.includes('magang') || lower.includes('intern')) return 'INTERNSHIP';
      return val.toUpperCase();
    }

    function translateWorkMode(val) {
      if (!val) return null;
      const lower = val.toLowerCase();
      if (lower.includes('remote')) return 'REMOTE';
      if (lower.includes('hybrid')) return 'HYBRID';
      if (lower.includes('on-site') || lower.includes('onsite')) return 'ON-SITE';
      return val.toUpperCase();
    }

    function renderJobs() {
      const q = (document.getElementById('searchInput').value || '').toLowerCase();
      const src = (selectedPlatform || '').toLowerCase();
      const mode = (selectedMode || '').toLowerCase();
      const savedIds = getSavedIds();
      
      let filtered = allJobs.filter(j => {
        const matchText = (j.title || '').toLowerCase().includes(q) || 
                          (j.company || '').toLowerCase().includes(q);
        const matchSrc = !src || (j.source || '').toLowerCase() === src;
        const matchMode = !mode || (j.work_mode || '').toLowerCase().includes(mode);
        const matchBookmark = !showBookmarksOnly || savedIds.includes(j.id);
        return matchText && matchSrc && matchMode && matchBookmark;
      });

      // Sorting logic: Default terbaru
      filtered.sort((a, b) => {
        if (selectedSort === 'salary_high') {
          const salA = a.salary_max || a.salary_min || 0;
          const salB = b.salary_max || b.salary_min || 0;
          return salB - salA;
        }
        if (selectedSort === 'title_asc') {
          return (a.title || '').localeCompare(b.title || '');
        }
        // 'newest' sort by posted_at or scraped_at
        const dateA = a.posted_at || a.scraped_at || '';
        const dateB = b.posted_at || b.scraped_at || '';
        return dateB.localeCompare(dateA);
      });

      const total = filtered.length;
      const totalPages = Math.ceil(total / pageSize) || 1;
      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, total);
      const pageJobs = filtered.slice(startIdx, endIdx);

      // Update Pagination UI
      document.getElementById('paginationInfo').innerText = total ? `Showing ${startIdx + 1}–${endIdx} of ${total} jobs` : '0 jobs';
      document.getElementById('pageBadge').innerText = `Page ${currentPage} / ${totalPages}`;
      document.getElementById('prevBtn').disabled = currentPage <= 1;
      document.getElementById('nextBtn').disabled = currentPage >= totalPages;

      const el = document.getElementById('jobsList');
      if (!pageJobs.length) {
        el.innerHTML = '<div class="text-neutral-500 text-sm py-12 text-center font-medium">No opportunities match the selected criteria.</div>';
        return;
      }
      el.innerHTML = pageJobs.map(j => `
        <div class="p-5 bg-[#161616] hover:bg-[#1C1C1C] border border-neutral-800/80 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 transition group">
          <div class="space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[9px] font-black tracking-widest px-2.5 py-0.5 rounded-full uppercase bg-neutral-800 text-neutral-300 border border-neutral-700">${j.source || 'JOB'}</span>
              <span class="text-[9px] font-black tracking-wider px-2.5 py-0.5 rounded-full uppercase ${formatSalary(j) === 'NOT DISCLOSED' ? 'bg-neutral-800/80 text-neutral-400 border border-neutral-700/60' : 'bg-limepill text-black'}">${formatSalary(j)}</span>
              ${translateWorkMode(j.work_mode) ? `<span class="text-[9px] font-bold tracking-wider px-2 py-0.5 rounded-full uppercase border border-neutral-700 text-neutral-400">${translateWorkMode(j.work_mode)}</span>` : ''}
              ${translateWorkType(j.work_type) ? `<span class="text-[9px] font-medium tracking-wider px-2 py-0.5 rounded-full uppercase bg-neutral-900 text-neutral-400">${translateWorkType(j.work_type)}</span>` : ''}
            </div>
            <h4 class="font-bold text-white text-base md:text-xl tracking-tight group-hover:text-limepill transition">${j.title || 'Untitled'}</h4>
            <div class="text-xs text-neutral-400 flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-x-2">
              <span class="text-neutral-200 font-semibold text-[13px] sm:text-xs">${j.company || 'Unknown Company'}</span>
              <span class="hidden sm:inline text-neutral-600">/</span>
              <span class="text-neutral-400 text-xs">${j.location || 'Surabaya'}</span>
            </div>
          </div>
          <!-- Card Actions: Right-aligned on mobile for easy thumb reach -->
          <div class="flex items-center gap-2 self-end sm:self-center shrink-0 pt-1 sm:pt-0">
            <button onclick="toggleSaveJob('${j.id}')" title="Save job" class="w-9 h-9 rounded-full border ${savedIds.includes(j.id) ? 'border-limepill bg-limepill text-black' : 'border-neutral-700 bg-neutral-800/80 hover:bg-neutral-700 text-neutral-400 hover:text-white'} flex items-center justify-center transition">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="${savedIds.includes(j.id) ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
              </svg>
            </button>
            <a href="${j.url || '#'}" target="_blank" class="pill-btn bg-white hover:bg-limepill text-black font-bold text-xs px-5 py-2.5 transition shrink-0 flex items-center gap-1.5">
              <span>View Job</span>
              <span>↗</span>
            </a>
          </div>
        </div>
      `).join('');
    }

    function changePage(delta) {
      currentPage += delta;
      renderJobs();
      const target = document.getElementById('curatedSection');
      if (target) {
        const topOffset = target.getBoundingClientRect().top + window.pageYOffset - (window.innerHeight * 0.06);
        window.scrollTo({ top: topOffset, behavior: 'smooth' });
      }
    }

    async function triggerScrape() {
      const btn = document.getElementById('triggerBtn');
      btn.disabled = true;
      btn.innerHTML = '<span>Scraping...</span>';
      try {
        await fetch('/api/trigger', { method: 'POST' });
        setTimeout(() => { loadStats(); loadJobs(); btn.disabled = false; btn.innerHTML = '<span>Scrape Now</span><span>↗</span>'; }, 3000);
      } catch (e) {
        btn.disabled = false;
        btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
      }
    }

    loadStats();
    loadJobs();
    updateBookmarkUI();
  </script>
</body>
</html>"""

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def _run_scrape_async(force: bool = False):
    """Run a scrape cycle in a background thread (for manual trigger)."""
    global last_scraped_at
    try:
        runner = ScraperRunner()
        result = runner.run_cycle(force=force)
        last_scraped_at = datetime.now(timezone.utc).isoformat()
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
        
    last_updated = storage_service.get_last_updated()

    return jsonify({
        "totalJobs": total_jobs,
        "sourceCounts": source_counts,
        "lastUpdated": last_updated,
        "lastScrapedAt": last_scraped_at,
        "keywords": getattr(config, "IT_KEYWORDS", []),
        "locations": getattr(config, "LOCATIONS", [])
    })

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    keyword = request.args.get("keyword", "").strip().lower()
    source = request.args.get("source", "").strip().lower()
    
    days_param = request.args.get("days")
    days = int(days_param) if days_param and days_param.isdigit() else None

    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500

    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0

    total_count, paginated = storage_service.query_jobs(
        keyword=keyword,
        source=source,
        days=days,
        limit=limit,
        offset=offset
    )

    return jsonify({
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": paginated
    })

@app.route("/api/export", methods=["GET"])
def export_jobs_csv():
    """Export stored jobs to CSV format."""
    import csv
    import io
    from flask import Response

    jobs = storage_service.load_jobs()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Source", "Title", "Company", "Location", "Salary", "Work Mode", "URL", "Posted At"])

    for j in jobs:
        writer.writerow([
            j.get("id", ""),
            j.get("source", ""),
            j.get("title", ""),
            j.get("company", ""),
            j.get("location", ""),
            j.get("salary", ""),
            j.get("work_mode", ""),
            j.get("url", ""),
            j.get("posted_at", "")
        ])

    today_str = datetime.now().strftime("%Y-%m-%d")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=jobs-{today_str}.csv"}
    )

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000, threads=8)
