import hashlib
from typing import List, Set, Tuple, Dict, Any

def generate_job_id(source: str, raw_identifier: str) -> str:
    """Generates deterministic unique hash ID if missing: f"{source.lower()}_{md5(source+raw_identifier)[:12]}"."""
    src = (source or "unknown").lower()
    raw = str(raw_identifier or "")
    combined = f"{src}{raw}".encode("utf-8")
    hash_str = hashlib.md5(combined).hexdigest()[:12]
    return f"{src}_{hash_str}"

class Deduplicator:
    @staticmethod
    def generate_job_id(source: str, raw_identifier: str) -> str:
        return generate_job_id(source, raw_identifier)

    @staticmethod
    def deduplicate_jobs(jobs: List[Dict[str, Any]], seen_ids: Set[str]) -> Tuple[List[Dict[str, Any]], Set[str]]:
        return deduplicate_jobs(jobs, seen_ids)

def deduplicate_jobs(jobs: List[Dict[str, Any]], seen_ids: Set[str]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Deduplicates jobs based on job 'id' or generated ID against seen_ids and within current batch.
    Returns (new_jobs, updated_seen_ids)."""
    updated_seen = set(seen_ids)
    new_jobs = []

    for job in jobs:
        source = job.get("source", "unknown")
        raw_id = job.get("id") or job.get("url") or job.get("title") or ""
        
        job_id = job.get("id")
        if not job_id:
            job_id = generate_job_id(source, raw_id)
            job["id"] = job_id

        if job_id not in updated_seen:
            updated_seen.add(job_id)
            new_jobs.append(job)

    return new_jobs, updated_seen
