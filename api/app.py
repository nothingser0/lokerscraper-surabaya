import logging
import collections
from logging.handlers import RotatingFileHandler
import os
import signal
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "scraper.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
    ]
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from config import config as app_config, random_scrape_interval_hours
from storage import StorageService
from engine.runner import ScraperRunner
import scrapers
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)

@app.route("/static/<path:filename>")
def custom_static(filename):
    from flask import send_from_directory, make_response
    resp = make_response(send_from_directory(str(PROJECT_ROOT / "static"), filename))
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp

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
scrape_interval_hours = getattr(app_config, "SCRAPE_INTERVAL_HOURS", 6)
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
    from flask import make_response
    resp = make_response("""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <title>LokerScraper Surabaya</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='10' fill='%23111111'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%23D4F542'/%3E%3Cpath d='M16 4v4M16 24v4M4 16h4M24 16h4' stroke='%23D4F542' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E">
  <link rel="preload" as="image" href="/static/hero_poster.jpg">
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
    .hero-word-line { height: 66px; line-height: 66px; }
    @media (min-width: 640px) { .hero-word-line { height: 76px; line-height: 76px; } }
    @media (min-width: 768px) { .hero-word-line { height: 102px; line-height: 102px; } }
    .hero-word-line #heroWordMain { line-height: inherit; }
    #heroWordMain:empty::before { content: '\00a0'; visibility: hidden; }
    .hero-highlight {
      background: linear-gradient(180deg, transparent 62%, #D4F542 62%);
      padding: 0 0.08em 0 0;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }
    .noise-bg {
      background-image: radial-gradient(rgba(0,0,0,0.09) 1px, transparent 0);
      background-size: 24px 24px;
    }
    @keyframes badgeGlow {
      0%, 100% { border-color: rgba(0, 0, 0, 0.08); box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
      50% { border-color: rgba(16, 185, 129, 0.4); box-shadow: 0 0 12px rgba(16, 185, 129, 0.12); }
    }
    .badge-animated {
      animation: badgeGlow 3s ease-in-out infinite;
    }
    @keyframes radarPulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(212, 245, 66, 0.7); }
      70% { transform: scale(1.15); box-shadow: 0 0 0 8px rgba(212, 245, 66, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(212, 245, 66, 0); }
    }
    .radar-dot {
      animation: radarPulse 2.2s cubic-bezier(0.23, 1, 0.32, 1) infinite;
    }
    .cursor-blink {
      display: inline-block;
      width: 3px;
      height: 0.85em;
      background-color: #111111;
      margin-left: 4px;
      vertical-align: baseline;
      animation: blink 1s steps(2, start) infinite;
    }
    @keyframes blink {
      to { visibility: hidden; }
    }
    .marquee-sidebar {
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      z-index: 0;
      overflow: hidden;
      -webkit-mask-image: linear-gradient(180deg, transparent, #000 14%, #000 86%, transparent);
      mask-image: linear-gradient(180deg, transparent, #000 14%, #000 86%, transparent);
    }
    @media (max-width: 1279px) {
      .marquee-sidebar {
        display: none !important;
      }
    }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    .marquee-track {
      position: absolute;
      top: 50%;
      left: 50%;
      white-space: nowrap;
      will-change: transform;
    }
    .marquee-left {
      transform: translate(-50%, -50%) rotate(-90deg);
      animation: marqueeLeftDown 65s linear infinite;
    }
    .marquee-right {
      transform: translate(-50%, -50%) rotate(90deg);
      animation: marqueeRightUp 65s linear infinite;
    }
    @keyframes marqueeLeftDown {
      0%   { transform: translate(-50%, -50%) rotate(-90deg) translateX(25%); }
      100% { transform: translate(-50%, -50%) rotate(-90deg) translateX(-25%); }
    }
    @keyframes marqueeRightUp {
      0%   { transform: translate(-50%, -50%) rotate(90deg) translateX(25%); }
      100% { transform: translate(-50%, -50%) rotate(90deg) translateX(-25%); }
    }
  </style>
</head>
<body class="p-3 sm:p-6 md:p-10 antialiased selection:bg-limepill selection:text-black noise-bg min-h-screen w-full overflow-x-hidden">
  
  <div class="marquee-sidebar fixed left-0 top-0 bottom-0 w-[max(80px,calc((100vw-1152px)/2))] select-none">
    <div class="marquee-track marquee-left text-4xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-black/[0.26] uppercase select-none">
      <span class="font-mono text-xs tracking-widest text-neutral-400 font-semibold">[01/EAST-JAVA]</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span>BUILD THE FUTURE</span>
      <span class="text-neutral-300">•</span>
      <span>SOLVE REAL PROBLEMS</span>
      <span class="text-neutral-300">•</span>
      <span>NEVER SETTLE</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span class="font-mono text-xs tracking-widest text-neutral-400 font-semibold">[01/EAST-JAVA]</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span>BUILD THE FUTURE</span>
      <span class="text-neutral-300">•</span>
      <span>SOLVE REAL PROBLEMS</span>
      <span class="text-neutral-300">•</span>
      <span>NEVER SETTLE</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
    </div>
  </div>

  <div class="marquee-sidebar fixed right-0 top-0 bottom-0 w-[max(80px,calc((100vw-1152px)/2))] select-none">
    <div class="marquee-track marquee-right text-4xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-black/[0.26] uppercase select-none">
      <span class="font-mono text-xs tracking-widest text-neutral-400 font-semibold">[02/ENGINEERING]</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span>CREATE MASTERY</span>
      <span class="text-neutral-300">•</span>
      <span>CODE WITH PURPOSE</span>
      <span class="text-neutral-300">•</span>
      <span>SHIP WITH PRIDE</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span class="font-mono text-xs tracking-widest text-neutral-400 font-semibold">[02/ENGINEERING]</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
      <span>CREATE MASTERY</span>
      <span class="text-neutral-300">•</span>
      <span>CODE WITH PURPOSE</span>
      <span class="text-neutral-300">•</span>
      <span>SHIP WITH PRIDE</span>
      <span class="inline-block w-8 h-[2px] bg-neutral-300"></span>
    </div>
  </div>

  <div id="tokenModal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
    <div class="bg-[#181818] border border-neutral-700/80 rounded-3xl p-6 md:p-8 max-w-sm w-full space-y-5 shadow-2xl text-white">
      <div class="space-y-1">
        <div class="text-[10px] uppercase tracking-widest font-bold text-limepill">Security Check</div>
        <h3 class="text-xl font-bold tracking-tight">Manual Trigger</h3>
        <p class="text-xs text-neutral-400">Enter your trigger token to execute on-demand scraping across all platforms.</p>
      </div>
      <div class="space-y-2">
        <input type="password" id="modalTokenInput" placeholder="Enter trigger token..." class="w-full bg-neutral-900 border border-neutral-700 rounded-full px-4 py-2.5 text-xs text-white focus:outline-none focus:border-limepill transition">
        <div id="modalErrorMsg" class="hidden text-[11px] text-rose-400 font-semibold px-2"></div>
      </div>
      <div class="flex items-center justify-end gap-2 pt-2 border-t border-neutral-800">
        <button onclick="closeTokenModal()" class="pill-btn px-4 py-2 text-xs text-neutral-400 hover:text-white transition">Cancel</button>
        <button id="modalConfirmBtn" onclick="confirmTriggerScrape()" class="pill-btn bg-limepill hover:brightness-95 text-black font-bold px-5 py-2 text-xs transition">Confirm ↗</button>
      </div>
    </div>
  </div>

  <div id="toastNotification" class="hidden fixed bottom-6 right-6 z-50 bg-[#181818] border border-neutral-700 text-white px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-3 text-xs transition">
    <span class="w-2 h-2 rounded-full bg-limepill animate-ping" id="toastDot"></span>
    <span id="toastMsg" class="font-medium">Notification</span>
  </div>

  <div class="max-w-6xl mx-auto space-y-4 md:space-y-6 relative z-10 w-full">
    
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      
      <div class="lg:col-span-8 bg-[#F8F8F5] rounded-3xl p-5 sm:p-7 md:p-9 border border-black/5 shadow-sm flex flex-col justify-start space-y-4 md:space-y-5">
        <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-neutral-900 border border-neutral-800 text-white shadow-xs transition cursor-default">
              <span class="w-2 h-2 rounded-full bg-limepill radar-dot"></span>
              <span id="heroStreamBadge" class="text-[11px] font-bold tracking-widest uppercase text-neutral-200">Surabaya Opportunities</span>
            </span>
          </div>
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
          <div class="relative sm:hidden">
            <button onclick="toggleMobileNav()" class="w-9 h-9 rounded-full bg-neutral-900 border border-neutral-800 text-white flex items-center justify-center text-sm focus:outline-none">
              ≡
          </button>
            <div id="mobileNavMenu" class="hidden absolute right-0 mt-2 w-44 bg-[#181818] border border-neutral-700/80 rounded-2xl shadow-2xl p-2 z-50 text-xs space-y-1">
              <button id="triggerBtnMobile" onclick="toggleMobileNav(); triggerScrape()" class="w-full text-left bg-limepill text-black font-bold px-3 py-2 rounded-xl flex items-center justify-between">
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
            <div class="hero-word-line text-6xl sm:text-7xl md:text-8xl flex items-center justify-start leading-none overflow-hidden">
              <span id="heroWordMain" class="hero-highlight inline-block whitespace-nowrap text-left leading-none">Developer</span><span class="cursor-blink"></span>
            </div>
            <div class="flex items-end gap-2.5 sm:gap-3 text-5xl sm:text-6xl md:text-7xl mt-1">
              <span class="leading-none">Jobs</span>
              <span class="inline-flex items-center justify-center bg-black text-limepill font-black px-3 py-1 sm:px-4 sm:py-1.5 rounded-full text-base sm:text-xl md:text-2xl shadow-sm tracking-normal leading-none">
              <span id="statTotal">-</span>
            </span>
            </div>
          </h1>
          <h2 id="heroSubtitle" class="display-title text-3xl sm:text-4xl md:text-5xl font-bold text-neutral-400 pt-0.5">
            Surabaya & Remote
          </h2>
        </div>

        <div class="pt-2.5 border-t border-black/5 font-sans min-w-0">
          <div class="bg-black/[0.04] border border-black/[0.06] rounded-2xl p-3 space-y-2.5 min-w-0">
          <div class="space-y-1.5 min-w-0">
            <div class="font-bold tracking-widest text-[10px] text-neutral-400 uppercase">LOCATIONS</div>
            <div id="envLocations" class="flex flex-wrap gap-1.5 min-w-0">Loading...</div>
          </div>
          <div class="space-y-1.5 min-w-0">
            <div class="font-bold tracking-widest text-[10px] text-neutral-400 uppercase">KEYWORDS</div>
            <div id="envKeywords" class="flex flex-wrap gap-1.5 min-w-0">Loading...</div>
          </div>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-12 gap-4 pt-2.5 border-t border-black/5 text-xs">
          <div class="sm:col-span-3">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Last Updated</div>
            <div id="statUpdated" class="font-semibold text-neutral-800 mt-1">-</div>
          </div>
          <div class="sm:col-span-2">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Cycle Status</div>
            <div id="statScraped" class="font-semibold text-neutral-800 mt-1">-</div>
            <div id="statRetention" class="text-[10px] text-neutral-400 mt-0.5" title="Old jobs are deleted automatically to keep storage flat">-</div>
          </div>
          <div class="sm:col-span-7">
            <div class="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Platforms</div>
            <div id="statSources" class="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mt-1.5">-</div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-4 flex flex-col gap-4 min-h-0">

        <div class="bg-neutral-900 rounded-3xl overflow-hidden relative min-h-[180px] sm:min-h-[220px] lg:min-h-0 lg:h-[230px] shrink-0 border border-black/10 shadow-sm group">
          <video autoplay loop muted playsinline preload="metadata" poster="/static/hero_poster.jpg"
                 class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition duration-700 brightness-90">
            <source src="/static/hero_small.mp4" type="video/mp4">
          </video>
          <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>
          <div class="absolute top-5 right-5 flex items-center gap-1.5 bg-black/60 backdrop-blur-md px-3 py-1 rounded-full border border-white/10 text-[11px] font-semibold text-limepill">
            <span class="w-2 h-2 rounded-full bg-limepill radar-dot"></span>
            <span>Online Radar</span>
          </div>
          <div class="absolute bottom-5 left-6 right-6 text-white space-y-2">
            <div id="platformCountBadge" class="inline-block px-2.5 py-0.5 rounded-full bg-limepill text-black text-[10px] font-black uppercase tracking-wider">
              Multi-Platform
            </div>
            <p id="platformNamesBanner" class="text-sm font-semibold leading-snug text-neutral-100">
              Continuous automated aggregation across registered platforms.
            </p>
          </div>
        </div>

        <div class="bg-[#0B0B0B] rounded-3xl border border-black/10 shadow-sm overflow-hidden flex flex-col h-[260px] lg:h-auto lg:flex-1 lg:basis-0 lg:min-h-[200px]">
          <div class="flex items-center gap-1.5 px-4 py-2.5 border-b border-neutral-800 bg-[#151515] shrink-0">
            <span class="w-2.5 h-2.5 rounded-full bg-[#FF5F56]"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-[#27C93F]"></span>
            <span class="ml-2 text-[11px] font-semibold text-neutral-400 font-mono">scraper.log</span>
            <span class="ml-auto flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-limepill">
              <span class="w-1.5 h-1.5 rounded-full bg-limepill radar-dot"></span>live
            </span>
          </div>
          <div id="logTerminal" class="flex-1 min-h-0 overflow-hidden px-3 py-2.5 font-mono text-[10px] leading-tight text-neutral-400 space-y-0.5"></div>
        </div>

      </div>

    </div>

    <div id="curatedSection" class="bg-[#111111] text-white rounded-3xl p-4 sm:p-6 md:p-8 space-y-5 md:space-y-6">
      
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800 pb-5">
        <div class="flex flex-col items-start gap-1.5 min-w-0">
          <span class="inline-block px-2.5 py-0.5 rounded-full border border-neutral-700 text-[10px] uppercase tracking-wider text-neutral-400 shrink-0">Curated Stream</span>
          <h3 class="text-2xl md:text-3xl font-bold tracking-tight whitespace-nowrap">Active Opportunities</h3>
        </div>
        <div class="w-full md:w-auto flex flex-col md:flex-row md:items-center gap-2.5">
          <div class="grid grid-cols-2 sm:grid-cols-4 md:flex md:items-center gap-2 w-full md:w-auto">
          <button id="bookmarkToggle" onclick="toggleBookmarksOnly()" class="bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-4 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center gap-1.5 transition w-full md:w-auto">
            <span class="w-2 h-2 rounded-full border border-neutral-500" id="bookmarkIndicator"></span>
            <span>Saved</span>
            <span id="bookmarkCount" class="ml-auto md:ml-0 text-[10px] text-limepill font-mono font-bold">0</span>
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

      <div id="jobsList" class="space-y-2.5">
        <div class="text-neutral-500 text-sm py-8 text-center">Loading live positions...</div>
      </div>

      <div id="paginationContainer" class="pt-6 pb-6 sm:pb-3 border-t border-neutral-800 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-neutral-400">
        <div id="paginationInfo">Showing 0-0 of 0</div>
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded-full pl-3 pr-1 py-1 mr-1">
            <label for="pageJump" class="text-[10px] uppercase tracking-wider text-neutral-500 font-bold">Go</label>
            <input id="pageJump" type="number" min="1" inputmode="numeric" placeholder="#"
                   onkeydown="if(event.key==='Enter'){jumpToPage(this.value)}"
                   class="w-10 bg-transparent text-white text-xs font-semibold text-center focus:outline-none [appearance:textfield] [&amp;::-webkit-outer-spin-button]:appearance-none [&amp;::-webkit-inner-spin-button]:appearance-none">
            <button onclick="jumpToPage(document.getElementById('pageJump').value)" aria-label="Go to page" class="w-6 h-6 rounded-full bg-limepill text-black hover:brightness-95 transition flex items-center justify-center p-0">
              <svg class="w-3.5 h-3.5 block" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </div>
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

    <footer class="pt-8 pb-14 border-t border-black/5 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left text-xs text-neutral-500">
      <div class="flex flex-col sm:flex-row items-center gap-1 sm:gap-2">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-limepill radar-dot shrink-0"></span>
          <span class="font-bold text-neutral-800">LokerScraper Surabaya</span>
        </div>
        <span class="hidden sm:inline text-neutral-300">•</span>
        <span class="text-neutral-400 text-[11px] sm:text-xs">Automated Regional Tech Aggregator</span>
      </div>
      <div class="flex flex-col sm:flex-row items-center gap-1 sm:gap-3 text-neutral-400 text-[11px]">
        <span>SQLite WAL • Auto-Prune 30d</span>
        <div class="flex items-center gap-2 text-neutral-400">
          <span class="hidden sm:inline">•</span>
          <a href="/health" target="_blank" class="hover:text-neutral-700 transition">/health</a>
          <span>•</span>
          <a href="/api/stats" target="_blank" class="hover:text-neutral-700 transition">/api/stats</a>
        </div>
      </div>
    </footer>

  </div>

  <script>
    let allJobs = [];
    let currentPage = 1;
    const pageSize = 10;
    let filteredTotal = 0;
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
      const badge = document.getElementById('bookmarkCount');
      if (showBookmarksOnly) {
        btn.className = 'bg-limepill text-black font-bold border border-limepill rounded-full pl-3.5 pr-4 py-2 text-xs tracking-wide focus:outline-none flex items-center gap-1.5 transition w-full md:w-auto';
        badge.className = 'ml-auto md:ml-0 text-[10px] text-black/60 font-mono font-bold';
        if (indicator) indicator.className = 'w-2 h-2 rounded-full bg-black';
      } else {
        btn.className = 'bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-4 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center gap-1.5 transition w-full md:w-auto';
        badge.className = 'ml-auto md:ml-0 text-[10px] text-limepill font-mono font-bold';
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
        const retEl = document.getElementById('statRetention');
        if (retEl && data.retentionDays) {
          const mb = data.dbBytes ? ` · ${(data.dbBytes / 1024 / 1024).toFixed(1)} MB` : '';
          retEl.innerText = `Auto-prune ${data.retentionDays}d${mb}`;
        }
        
        if (data.locations && data.locations.length) {
          const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
          const primaryLoc = cap(data.locations[0]);
          const modeEntry = data.locations.find(l => ['remote', 'hybrid', 'wfh'].includes(l.toLowerCase()));
          document.getElementById('heroSubtitle').innerText = `${primaryLoc} & ${cap(modeEntry || 'remote')}`;
          document.getElementById('heroStreamBadge').innerText = `${primaryLoc} Opportunities`;
          document.getElementById('envLocations').innerHTML = data.locations.map(l => 
            `<span class="bg-white border border-black/10 px-3 py-1 rounded-full capitalize font-extrabold tracking-tight text-neutral-600 shadow-sm" style="font-size:${chipFontSize(l)}">${l}</span>`
          ).join('');
        }
        if (data.keywords && data.keywords.length) {
          const toTitleCase = (s) => (s || '').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
          const words = data.keywords.map(toTitleCase);
          initTypewriter(words);
          document.getElementById('envKeywords').innerHTML = data.keywords.slice(0, 10).map(k => 
            `<span class="bg-limepill text-black border border-black/10 px-3 py-1 rounded-full font-extrabold tracking-tight shadow-sm whitespace-nowrap" style="font-size:${chipFontSize(k)}">${k}</span>`
          ).join('') + (data.keywords.length > 10 ? `<span class="text-neutral-500 text-[11px] font-bold self-center">+${data.keywords.length - 10} more</span>` : '');
        }

        const platforms = data.platforms || (data.sourceCounts ? Object.keys(data.sourceCounts) : []);
        if (data.sourceCounts) {
          const gridEl = document.getElementById('statSources');
          const rows = 2;
          const cols = Math.max(2, Math.ceil(platforms.length / rows));
          gridEl.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
          document.getElementById('statSources').innerHTML = Object.entries(data.sourceCounts)
            .map(([k, v]) => `<span class="flex items-center justify-between bg-neutral-900 text-neutral-200 border border-neutral-700/80 px-2 py-1 rounded-full text-[11px] font-semibold tracking-wide min-w-0"><span class="truncate">${k}</span><span class="bg-limepill text-black font-black px-1.5 py-0.2 rounded-full text-[10px] ml-auto shrink-0">${v}</span></span>`).join('');
          
          if (platforms.length) {
            document.getElementById('platformCountBadge').innerText = `${platforms.length} Aggregators`;
            const displayedPlatforms = platforms.length > 6 
              ? `${platforms.slice(0, 6).join(', ')} +${platforms.length - 6} more`
              : platforms.join(', ');
            document.getElementById('platformNamesBanner').innerText = `Continuous automated aggregation across ${displayedPlatforms}.`;
            
            const menuEl = document.getElementById('sourceFilterMenu');
            menuEl.innerHTML = `
              <div onclick="selectPlatform('', 'All Platforms')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-200 cursor-pointer flex items-center justify-between transition">
                <span>All Platforms</span>
              </div>` +
              platforms.map(s => `
                <div onclick="selectPlatform('${s}', '${s} (${data.sourceCounts[s] || 0})')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer flex items-center justify-between transition">
                  <span>${s}</span>
                  <span class="text-[10px] bg-neutral-800 px-1.5 py-0.5 rounded-full text-neutral-400">${data.sourceCounts[s] || 0}</span>
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

      filtered.sort((a, b) => {
        if (selectedSort === 'salary_high') {
          const salA = a.salary_max || a.salary_min || 0;
          const salB = b.salary_max || b.salary_min || 0;
          return salB - salA;
        }
        if (selectedSort === 'title_asc') {
          return (a.title || '').localeCompare(b.title || '');
        }
        const dateA = a.posted_at || a.scraped_at || '';
        const dateB = b.posted_at || b.scraped_at || '';
        return dateB.localeCompare(dateA);
      });

      const total = filtered.length;
      filteredTotal = total;
      const totalPages = Math.ceil(total / pageSize) || 1;
      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, total);
      const pageJobs = filtered.slice(startIdx, endIdx);

      document.getElementById('paginationInfo').innerText = total ? `Showing ${startIdx + 1}–${endIdx} of ${total} jobs` : '0 jobs';
      document.getElementById('pageBadge').innerText = `Page ${currentPage} / ${totalPages}`;
      document.getElementById('prevBtn').disabled = currentPage <= 1;
      document.getElementById('nextBtn').disabled = currentPage >= totalPages;
      const jump = document.getElementById('pageJump');
      if (jump) { jump.max = totalPages; jump.placeholder = `1-${totalPages}`; }

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
      scrollToFeed();
    }

    function jumpToPage(value) {
      const totalPages = Math.ceil(filteredTotal / pageSize) || 1;
      const n = Math.floor(Number(value));
      if (!Number.isFinite(n) || n < 1) return;
      currentPage = Math.min(n, totalPages);
      renderJobs();
      scrollToFeed();
    }

    function scrollToFeed() {
      const target = document.getElementById('curatedSection');
      if (!target) return;
      const topOffset = target.getBoundingClientRect().top + window.pageYOffset - (window.innerHeight * 0.06);
      window.scrollTo({ top: topOffset, behavior: 'smooth' });
    }

    function chipFontSize(text) {
      const len = (text || '').length;
      if (len <= 10) return '11px';
      if (len <= 14) return '10px';
      if (len <= 18) return '9px';
      return '8px';
    }
    function chipClass(text) {
      return `inline-flex items-center px-3 py-1 rounded-full font-extrabold tracking-tight shadow-sm whitespace-nowrap`;
    }

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toastNotification');
      const text = document.getElementById('toastMsg');
      const dot = document.getElementById('toastDot');
      text.innerText = msg;
      dot.className = isError ? 'w-2 h-2 rounded-full bg-rose-500' : 'w-2 h-2 rounded-full bg-limepill animate-ping';
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 3500);
    }

    function triggerScrape() {
      document.getElementById('modalTokenInput').value = '';
      document.getElementById('modalErrorMsg').classList.add('hidden');
      document.getElementById('tokenModal').classList.remove('hidden');
      document.getElementById('modalTokenInput').focus();
    }

    function closeTokenModal() {
      document.getElementById('tokenModal').classList.add('hidden');
    }

    async function confirmTriggerScrape() {
      const input = document.getElementById('modalTokenInput');
      const token = input.value.trim();
      if (!token) {
        document.getElementById('modalErrorMsg').innerText = 'Token cannot be empty.';
        document.getElementById('modalErrorMsg').classList.remove('hidden');
        return;
      }

      const confirmBtn = document.getElementById('modalConfirmBtn');
      confirmBtn.disabled = true;
      confirmBtn.innerText = 'Verifying...';

      const btn = document.getElementById('triggerBtn');
      const btnMobile = document.getElementById('triggerBtnMobile');
      btn.disabled = true;
      btn.innerHTML = '<span>Scraping...</span>';
      if (btnMobile) {
        btnMobile.disabled = true;
        btnMobile.innerHTML = '<span>Scraping...</span>';
      }
      try {
        const res = await fetch('/api/trigger', {
          method: 'POST',
          headers: { 'X-Trigger-Token': token }
        });
        if (res.status === 401) {
          document.getElementById('modalErrorMsg').innerText = 'Invalid token. Authorization failed.';
          document.getElementById('modalErrorMsg').classList.remove('hidden');
          confirmBtn.disabled = false;
          confirmBtn.innerText = 'Confirm ↗';
          btn.disabled = false;
          btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          if (btnMobile) {
            btnMobile.disabled = false;
            btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          }
          return;
        }
        closeTokenModal();
        showToast('Scraping initiated across all 6 platforms.');
        setTimeout(() => {
          loadStats();
          loadJobs();
          btn.disabled = false;
          btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          if (btnMobile) {
            btnMobile.disabled = false;
            btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          }
        }, 3000);
      } catch (e) {
        closeTokenModal();
        showToast('Network error triggering scraper.', true);
        btn.disabled = false;
        btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
        if (btnMobile) {
          btnMobile.disabled = false;
          btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
        }
      }
    }

    let typewriterTimeout = null;
    function initTypewriter(words) {
      if (typewriterTimeout) clearTimeout(typewriterTimeout);
      if (!Array.isArray(words)) words = [words];
      if (!words.length) return;
      const target = document.getElementById('heroWordMain');
      let wordIdx = 0;
      let idx = 0;
      let isDeleting = false;

      function fitFont(word) {
        const box = target.parentElement;
        const max = box.clientWidth;
        if (!max) return;
        const base = window.innerWidth >= 768 ? 96 : (window.innerWidth >= 640 ? 72 : 60);
        let size = base;
        target.style.fontSize = size + 'px';
        const prev = target.textContent;
        target.textContent = word;
        let guard = 0;
        while (target.scrollWidth > max && size > 24 && guard < 40) {
          size -= 4;
          target.style.fontSize = size + 'px';
          guard++;
        }
        target.textContent = prev;
      }

      function tick() {
        const word = words[wordIdx];
        if (idx === 0 && !isDeleting) fitFont(word);
        if (!isDeleting) {
          idx++;
          const nextText = word.substring(0, idx);
          target.textContent = nextText || '\u00A0';
          target.classList.toggle('hero-highlight', Boolean(nextText));
          if (idx === word.length) {
            typewriterTimeout = setTimeout(() => { isDeleting = true; tick(); }, 2000);
            return;
          }
          typewriterTimeout = setTimeout(tick, 140);
        } else {
          idx--;
          const nextText = word.substring(0, idx);
          target.textContent = nextText || '\u00A0';
          target.classList.toggle('hero-highlight', Boolean(nextText));
          if (idx === 0) {
            isDeleting = false;
            wordIdx = (wordIdx + 1) % words.length;
            typewriterTimeout = setTimeout(tick, 500);
            return;
          }
          typewriterTimeout = setTimeout(tick, 70);
        }
      }
      tick();
    }

    const logEl = document.getElementById('logTerminal');
    const logLevelClass = (line) => {
      if (line.includes('ERROR') || line.includes('Traceback')) return 'text-[#FF6B6B]';
      if (line.includes('WARNING')) return 'text-[#FFBD2E]';
      if (line.includes('INFO')) return 'text-neutral-400';
      return 'text-neutral-500';
    };
    let logLines = [];
    let logSig = '';
    const logRowHtml = (l) => {
      const safe = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return `<div class="truncate ${logLevelClass(l)}">${safe}</div>`;
    };
    function renderLogs() {
      if (!logLines.length) return;
      logEl.innerHTML = logLines.map(logRowHtml).join('');
      let guard = logLines.length;
      while (logEl.scrollHeight > logEl.clientHeight && logEl.firstChild && guard--) {
        logEl.removeChild(logEl.firstChild);
      }
    }
    async function loadLogs() {
      try {
        const res = await fetch('/api/logs?lines=80');
        const data = await res.json();
        logLines = data.lines || [];
        const sig = logLines.join('\\n');
        if (sig === logSig) return;
        logSig = sig;
        renderLogs();
      } catch (e) { }
    }
    if (window.ResizeObserver) new ResizeObserver(renderLogs).observe(logEl);

    loadStats();
    loadJobs();
    updateBookmarkUI();
    loadLogs();
    setInterval(loadLogs, 3000);
  </script>
</body>
</html>""")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def _run_scrape_async(force: bool = False):
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
    configured_token = str(getattr(app_config, "TRIGGER_TOKEN", "") or os.getenv("TRIGGER_TOKEN", "")).strip()
    req_token = (request.headers.get("X-Trigger-Token") or request.args.get("token", "")).strip()
    logger.info(f"Trigger check -> configured: '{configured_token}', req: '{req_token}'")
    if configured_token:
        if not req_token or req_token != configured_token:
            return jsonify({"status": "error", "message": "Unauthorized: invalid or missing trigger token"}), 401
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
    
    registered_platforms = sorted([cls().source_name for cls in BaseScraper.__subclasses__()])
    
    source_counts: Dict[str, int] = {}
    for p in registered_platforms:
        source_counts[p] = 0
    for job in jobs:
        src = job.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        
    last_updated = storage_service.get_last_updated()

    db_path = storage_service.sqlite_file
    db_bytes = db_path.stat().st_size if db_path.exists() else 0

    return jsonify({
        "totalJobs": total_jobs,
        "sourceCounts": source_counts,
        "platforms": registered_platforms,
        "platformCount": len(registered_platforms),
        "lastUpdated": last_updated,
        "lastScrapedAt": last_scraped_at,
        "retentionDays": getattr(app_config, "JOB_RETENTION_DAYS", 30),
        "dbBytes": db_bytes,
        "keywords": getattr(app_config, "KEYWORDS", []),
        "locations": getattr(app_config, "LOCATIONS", [])
    })

@app.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        lines = int(request.args.get("lines", 40))
    except ValueError:
        lines = 40
    lines = max(1, min(lines, 200))

    log_path = app_config.LOG_FILE
    if not log_path.exists():
        return jsonify({"lines": []})

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            tail = collections.deque(fh, maxlen=lines)
    except OSError as exc:
        logger.warning("Unable to read log file: %s", exc)
        return jsonify({"lines": []})

    return jsonify({"lines": [ln.rstrip("\n") for ln in tail]})

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
    def _graceful_exit(signum, frame):
        logger.info(f"Signal {signum} received. Shutting down scheduler...")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _graceful_exit)
    signal.signal(signal.SIGINT, _graceful_exit)

    from waitress import serve
    serve(app, host="0.0.0.0", port=5000, threads=8)
