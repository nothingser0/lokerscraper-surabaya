import re
from typing import List, Dict, Any
from config import config

NON_IT_EXCEPTIONS = [
    "sales engineer", "civil engineer", "mechanical engineer", 
    "chemical engineer", "electrical engineer", "site engineer", 
    "sound engineer", "materials engineer", "supplier quality engineer",
    "quality control engineer", "process engineer", "maintenance engineer",
    "project engineer", "field engineer", "service engineer"
]

NON_IT_EXCEPTIONS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(exc) for exc in NON_IT_EXCEPTIONS) + r")\b",
    re.IGNORECASE
)

IT_OVERRIDE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in ["software", "it", "web", "data", "system", "app"]) + r")\b",
    re.IGNORECASE
)

KEYWORDS = getattr(config, "KEYWORDS", [
    "developer", "engineer", "programmer", "backend", "frontend",
    "fullstack", "mobile", "data", "devops", "qa", "tester", "web",
    "software", "code", "tech", "it"
])

KEYWORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in KEYWORDS) + r")\b",
    re.IGNORECASE
)

LOCATIONS = getattr(config, "LOCATIONS", ["surabaya", "sidoarjo", "gresik", "remote", "hybrid"])

LOCATIONS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(loc) for loc in LOCATIONS) + r")\b",
    re.IGNORECASE
)

def matches_keywords(job: Dict[str, Any]) -> bool:
    if not KEYWORDS:
        return True
    title = str(job.get("title") or "")
    return bool(KEYWORDS_RE.search(title))

is_it_job = matches_keywords

def is_valid_location(job: Dict[str, Any]) -> bool:
    location = str(job.get("location") or "")
    title = str(job.get("title") or "")
    work_mode = str(job.get("work_mode") or "")
    text = f"{location} {title} {work_mode}"
    return bool(LOCATIONS_RE.search(text))

def filter_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [job for job in jobs if matches_keywords(job) and is_valid_location(job)]
