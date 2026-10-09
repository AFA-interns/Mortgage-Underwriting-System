from abc import ABC, abstractmethod
from typing import Any


class BasePropertyScraper(ABC):

    @abstractmethod
    async def fetch_listings(
        self,
        city: str,
        locality: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch raw property listings from a permitted source."""
        raise NotImplementedError