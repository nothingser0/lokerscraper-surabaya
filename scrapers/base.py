from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the scraper source."""
        pass

    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch and return standardized list of job dictionaries."""
        pass
