import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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
    """Return a dictionary pre-populated with all 25 canonical job schema keys set to None,
    overridden by explicit kwargs.
    """
    job = {field: None for field in JOB_FIELDS}
    job.update(overrides)
    return job


class BaseScraper(ABC):
    # Minimum delay (seconds) between consecutive HTTP requests issued by a
    # single scraper instance. Subclasses that hit rate-limited endpoints
    # (e.g. LinkedIn) can raise this via their own constructor.
    request_delay: float = 0.0

    def __init__(self) -> None:
        # Per-instance session (NOT class-level): requests.Session is not
        # thread-safe, and each scraper runs on its own thread in the runner.
        self._session: Optional[requests.Session] = None
        self._last_request_ts: float = 0.0

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the scraper source."""
        pass

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            # Retry transient errors AND rate-limit (429). `respect_retry_after_header`
            # makes urllib3 honor the server's Retry-After value on 429/503.
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
        """Enforce `request_delay` between requests to avoid rate-limiting."""
        if self.request_delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.request_delay - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _get(self, url: str, **kwargs) -> requests.Response:
        """Throttled GET wrapper so every scraper request respects request_delay."""
        self._throttle()
        return self.session.get(url, **kwargs)

    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch and return standardized list of job dictionaries."""
        pass
