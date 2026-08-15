from typing import List, Dict, Any
from config import config

def is_it_job(job: Dict[str, Any]) -> bool:
    """Checks if title or keyword contains any IT keywords from config.IT_KEYWORDS."""
    title = str(job.get("title") or "").lower()
    keyword = str(job.get("keyword") or "").lower()
    text = f"{title} {keyword}"
    
    keywords = getattr(config, "IT_KEYWORDS", [
        "developer", "engineer", "programmer", "backend", "frontend",
        "fullstack", "mobile", "data", "devops", "qa", "tester", "web",
        "software", "code", "tech", "it"
    ])
    
    return any(kw.lower() in text for kw in keywords)

def is_valid_location(job: Dict[str, Any]) -> bool:
    """Checks if location, title, or work_mode contains any allowed location from config.LOCATIONS."""
    location = str(job.get("location") or "").lower()
    title = str(job.get("title") or "").lower()
    work_mode = str(job.get("work_mode") or "").lower()
    text = f"{location} {title} {work_mode}"
    
    locations = getattr(config, "LOCATIONS", ["surabaya", "sidoarjo", "gresik", "remote", "hybrid"])
    
    return any(loc.lower() in text for loc in locations)

def filter_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Applies both IT job check and location check, returning filtered jobs."""
    return [job for job in jobs if is_it_job(job) and is_valid_location(job)]
