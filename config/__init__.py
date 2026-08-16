import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

_default_keywords = "developer,engineer,programmer,backend,frontend,fullstack,mobile,data,devops,qa,tester,web"
_default_locations = "surabaya,sidoarjo,gresik,remote"

@dataclass
class Config:
    DISCORD_WEBHOOK_URL: str = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", ""))
    # Comma-separated list of Discord webhook URLs (supports notifying multiple
    # channels/servers). Falls back to the single DISCORD_WEBHOOK_URL.
    DISCORD_WEBHOOK_URLS: List[str] = field(default_factory=lambda: [u.strip() for u in os.getenv("DISCORD_WEBHOOK_URLS", "").split(",") if u.strip()])
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    DEEPL_API_KEY: str = field(default_factory=lambda: os.getenv("DEEPL_API_KEY", ""))
    DEEPL_API_URL: str = field(default_factory=lambda: os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate"))
    SCRAPE_INTERVAL_HOURS: int = field(default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_HOURS", "6")))
    # Random scrape interval range (hours). When both are set and
    # SCRAPE_INTERVAL_MAX_HOURS > SCRAPE_INTERVAL_MIN_HOURS, the scheduler
    # re-schedules each cycle with a random delay within [min, max].
    SCRAPE_INTERVAL_MIN_HOURS: int = field(default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_MIN_HOURS", "0")))
    SCRAPE_INTERVAL_MAX_HOURS: int = field(default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_MAX_HOURS", "0")))
    TRIGGER_TOKEN: str = field(default_factory=lambda: os.getenv("TRIGGER_TOKEN", ""))
    IT_KEYWORDS: List[str] = field(default_factory=lambda: [k.strip().lower() for k in os.getenv("IT_KEYWORDS", _default_keywords).split(",") if k.strip()])
    LOCATIONS: List[str] = field(default_factory=lambda: [l.strip().lower() for l in os.getenv("LOCATIONS", _default_locations).split(",") if l.strip()])
    
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    LOGS_DIR: Path = LOGS_DIR
    JOBS_FILE: Path = DATA_DIR / "jobs.json"
    SEEN_IDS_FILE: Path = DATA_DIR / "seen-ids.json"
    LOG_FILE: Path = LOGS_DIR / "scraper.log"

config = Config()


def random_scrape_interval_hours() -> int:
    """Return the scrape interval in hours, honoring the random [min, max] range
    when configured. Falls back to the fixed SCRAPE_INTERVAL_HOURS otherwise.
    """
    lo = config.SCRAPE_INTERVAL_MIN_HOURS
    hi = config.SCRAPE_INTERVAL_MAX_HOURS
    if lo > 0 and hi > lo:
        return random.randint(lo, hi)
    return config.SCRAPE_INTERVAL_HOURS


DISCORD_WEBHOOK_URL = config.DISCORD_WEBHOOK_URL
DISCORD_WEBHOOK_URLS = config.DISCORD_WEBHOOK_URLS
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
DEEPL_API_KEY = config.DEEPL_API_KEY
DEEPL_API_URL = config.DEEPL_API_URL
SCRAPE_INTERVAL_HOURS = config.SCRAPE_INTERVAL_HOURS
SCRAPE_INTERVAL_MIN_HOURS = config.SCRAPE_INTERVAL_MIN_HOURS
SCRAPE_INTERVAL_MAX_HOURS = config.SCRAPE_INTERVAL_MAX_HOURS
TRIGGER_TOKEN = config.TRIGGER_TOKEN
IT_KEYWORDS = config.IT_KEYWORDS
LOCATIONS = config.LOCATIONS
JOBS_FILE = config.JOBS_FILE
SEEN_IDS_FILE = config.SEEN_IDS_FILE
LOG_FILE = config.LOG_FILE

