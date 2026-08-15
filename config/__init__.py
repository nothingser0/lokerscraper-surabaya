import os
from pathlib import Path
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

# Notification configs
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Scraper & Scheduler configs
SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))

# Keywords and Locations
_default_keywords = "developer,engineer,programmer,backend,frontend,fullstack,mobile,data,devops,qa,tester,web"
_default_locations = "surabaya,sidoarjo,gresik,remote"

IT_KEYWORDS = [k.strip().lower() for k in os.getenv("IT_KEYWORDS", _default_keywords).split(",") if k.strip()]
LOCATIONS = [l.strip().lower() for l in os.getenv("LOCATIONS", _default_locations).split(",") if l.strip()]

# Storage File Paths
JOBS_FILE = DATA_DIR / "jobs.json"
SEEN_IDS_FILE = DATA_DIR / "seen-ids.json"
LOG_FILE = LOGS_DIR / "scraper.log"
