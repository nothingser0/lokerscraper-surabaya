import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

JOB_FIELDS = [
    "raw_id",
    "source",
    "title",
    "company",
    "logo_url",
    "company_industry",
    "company_description",
    "location",
    "salary_min",
    "salary_max",
    "salary_currency",
    "work_type",
    "work_mode",
    "posted_at",
    "application_deadline",
    "applicant_count",
    "number_of_openings",
    "skills",
    "experience",
    "education",
    "job_description",
    "qualifications",
    "benefits",
    "url",
    "scraped_at",
]


def new_job_dict(**overrides) -> Dict[str, Any]:
    job = {field: None for field in JOB_FIELDS}
    job.update(overrides)
    return job


class BaseScraper(ABC):
    request_delay: float = 0.0

    def __init__(self) -> None:
        self._session: Optional[requests.Session] = None
        self._last_request_ts: float = 0.0
        self.seen_ids: Set[str] = set()

    def is_seen(self, raw_id: str) -> bool:
        if not self.seen_ids:
            return False
        from engine.dedup import generate_job_id
        return generate_job_id(self.source_name, raw_id) in self.seen_ids

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            adapter = HTTPAdapter(
                max_retries=Retry(
                    total=4,
                    connect=4,
                    read=4,
                    status=4,
                    backoff_factor=1.0,
                    status_forcelist=[429, 500, 502, 503, 504],
                    respect_retry_after_header=True,
                )
            )
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def _throttle(self) -> None:
        if self.request_delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.request_delay - elapsed
        if wait > 0:
            time.sleep(wait)

    def _get(self, url: str, **kwargs) -> requests.Response:
        self._throttle()
        try:
            return self.session.get(url, **kwargs)
        finally:
            self._last_request_ts = time.monotonic()

    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        pass
