import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Path setups
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Load .env file
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

_default_keywords = "developer,engineer,programmer,backend,frontend,fullstack,mobile,data,devops,qa,tester,web"
_default_locations = "surabaya,sidoarjo,gresik,remote"

@dataclass
class Config:
    DISCORD_WEBHOOK_URL: str = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", ""))
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    SCRAPE_INTERVAL_HOURS: int = field(default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_HOURS", "6")))
    IT_KEYWORDS: List[str] = field(default_factory=lambda: [k.strip().lower() for k in os.getenv("IT_KEYWORDS", _default_keywords).split(",") if k.strip()])
    LOCATIONS: List[str] = field(default_factory=lambda: [l.strip().lower() for l in os.getenv("LOCATIONS", _default_locations).split(",") if l.strip()])
    
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    LOGS_DIR: Path = LOGS_DIR
    JOBS_FILE: Path = DATA_DIR / "jobs.json"
    SEEN_IDS_FILE: Path = DATA_DIR / "seen-ids.json"
    LOG_FILE: Path = LOGS_DIR / "scraper.log"

config = Config()

# Export variables for direct module-level import as well
DISCORD_WEBHOOK_URL = config.DISCORD_WEBHOOK_URL
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
SCRAPE_INTERVAL_HOURS = config.SCRAPE_INTERVAL_HOURS
IT_KEYWORDS = config.IT_KEYWORDS
LOCATIONS = config.LOCATIONS
JOBS_FILE = config.JOBS_FILE
SEEN_IDS_FILE = config.SEEN_IDS_FILE
LOG_FILE = config.LOG_FILE

