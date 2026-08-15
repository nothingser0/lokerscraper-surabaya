from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class BaseScraper(ABC):
    _session: Optional[requests.Session] = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the scraper source."""
        pass

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            adapter = HTTPAdapter(
                max_retries=Retry(
                    total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
                )
            )
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch and return standardized list of job dictionaries."""
        pass
