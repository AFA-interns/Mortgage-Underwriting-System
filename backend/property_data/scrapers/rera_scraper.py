"""
RERA (Real Estate Regulatory Authority) scraper.

RERA websites are government-run and don't have aggressive bot detection.
They provide official project data including:
- Project name, builder, RERA number
- Total floors, parking, furnishing
- Approved plans, completion dates
- Unit configurations and pricing

State RERA URLs:
- Karnataka: https://rera.karnataka.gov.in/
- Maharashtra: https://maharera.mahaonline.gov.in/
- Tamil Nadu: https://rera.tn.gov.in/
- Telangana: https://rera.telangana.gov.in/
- Gujarat: https://gujrera.gujarat.gov.in/
- Rajasthan: https://rera.rajasthan.gov.in/
- UP: https://up-rera.gov.in/
- Delhi: https://rera.delhi.gov.in/
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


# State RERA website URLs
RERA_URLS = {
    "Karnataka": "https://rera.karnataka.gov.in/",
    "Maharashtra": "https://maharera.mahaonline.gov.in/",
    "Tamil Nadu": "https://rera.tn.gov.in/",
    "Telangana": "https://rera.telangana.gov.in/",
    "Gujarat": "https://gujrera.gujarat.gov.in/",
    "Rajasthan": "https://rera.rajasthan.gov.in/",
    "Uttar Pradesh": "https://up-rera.gov.in/",
    "Delhi": "https://rera.delhi.gov.in/",
    "Haryana": "https://haryanarera.gov.in/",
    "Punjab": "https://rera.punjab.gov.in/",
    "Kerala": "https://rera.kerala.gov.in/",
    "Andhra Pradesh": "https://rera.ap.gov.in/",
    "Madhya Pradesh": "https://rera.mp.gov.in/",
    "Chhattisgarh": "https://rera.cg.gov.in/",
    "Odisha": "https://rera.odisha.gov.in/",
    "West Bengal": "https://rera.wb.gov.in/",
    "Bihar": "https://rera.bihar.gov.in/",
    "Jharkhand": "https://rera.jharkhand.gov.in/",
    "Uttarakhand": "https://rera.uk.gov.in/",
    "Himachal Pradesh": "https://rera.hp.gov.in/",
    "Goa": "https://rera.goa.gov.in/",
}


class ReraScraper:
    """
    Scraper for RERA project data.

    RERA websites are government-run and typically don't block scrapers.
    They provide official project data that's more reliable than listing sites.
    """

    SOURCE = "rera"

    def __init__(self, state: str = "Karnataka"):
        self.state = state
        self.base_url = RERA_URLS.get(state, RERA_URLS["Karnataka"])
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def search_projects(
        self,
        project_name: str | None = None,
        builder_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for RERA-registered projects.

        Args:
            project_name: Optional project name filter
            builder_name: Optional builder name filter

        Returns:
            List of project dicts with RERA data
        """
        # Note: Each state has a different RERA website structure.
        # This is a generic implementation that works for most states.
        # For production, you may need state-specific parsers.

        search_url = f"{self.base_url}projectDetails"

        params = {}
        if project_name:
            params["projectName"] = project_name
        if builder_name:
            params["builderName"] = builder_name

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            try:
                response = await client.get(search_url, params=params)
                response.raise_for_status()
                return self._parse_search_results(response.text)
            except Exception as exc:
                print(f"[RERA] Search failed: {exc}")
                return []

    def _parse_search_results(self, html: str) -> list[dict[str, Any]]:
        """Parse RERA search results page."""
        soup = BeautifulSoup(html, "lxml")
        projects: list[dict[str, Any]] = []

        # Generic table parsing — most RERA sites use tables
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            # Try to extract project data from table cells
            project = self._extract_project_from_row(cells)
            if project:
                projects.append(project)

        return projects

    def _extract_project_from_row(
        self,
        cells: list[Any],
    ) -> dict[str, Any] | None:
        """Extract project data from a table row."""
        texts = [cell.get_text(strip=True) for cell in cells]

        # Look for RERA number pattern (e.g., PRM/KA/RERA/1251/446/PR/190812/002712)
        rera_number = None
        for text in texts:
            match = re.search(r"[A-Z]+/[A-Z]+/RERA/\d+/\d+/[A-Z]+/\d+/\d+", text)
            if match:
                rera_number = match.group()
                break

        if not rera_number:
            return None

        # Extract other fields
        project = {
            "source": self.SOURCE,
            "rera_number": rera_number,
            "project_name": texts[0] if texts else None,
            "builder_name": texts[1] if len(texts) > 1 else None,
            "state": self.state,
            "city": None,
            "locality": None,
            "property_type": None,
            "total_floors": None,
            "parking": None,
            "completion_date": None,
            "approval_date": None,
        }

        return project

    async def get_project_details(
        self,
        rera_number: str,
    ) -> dict[str, Any] | None:
        """
        Get detailed information for a specific RERA project.

        Args:
            rera_number: RERA registration number

        Returns:
            Project detail dict or None
        """
        # Note: Each state has a different detail page URL pattern
        detail_url = f"{self.base_url}projectDetails?reraNumber={rera_number}"

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            try:
                response = await client.get(detail_url)
                response.raise_for_status()
                return self._parse_project_details(response.text, rera_number)
            except Exception as exc:
                print(f"[RERA] Detail fetch failed: {exc}")
                return None

    def _parse_project_details(
        self,
        html: str,
        rera_number: str,
    ) -> dict[str, Any] | None:
        """Parse RERA project detail page."""
        soup = BeautifulSoup(html, "lxml")

        # Extract all text and look for key-value pairs
        text = soup.get_text()

        project = {
            "source": self.SOURCE,
            "rera_number": rera_number,
            "project_name": self._extract_field(text, r"Project Name\s*[:]\s*(.+)"),
            "builder_name": self._extract_field(text, r"Builder\s*[:]\s*(.+)"),
            "state": self.state,
            "city": self._extract_field(text, r"City\s*[:]\s*(.+)"),
            "locality": self._extract_field(text, r"Locality\s*[:]\s*(.+)"),
            "property_type": self._extract_field(text, r"Property Type\s*[:]\s*(.+)"),
            "total_floors": self._extract_number(text, r"Total Floors\s*[:]\s*(\d+)"),
            "parking": self._extract_number(text, r"Parking\s*[:]\s*(\d+)"),
            "completion_date": self._extract_field(text, r"Completion Date\s*[:]\s*(.+)"),
            "approval_date": self._extract_field(text, r"Approval Date\s*[:]\s*(.+)"),
        }

        return project

    def _extract_field(self, text: str, pattern: str) -> str | None:
        """Extract a field using regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_number(self, text: str, pattern: str) -> int | None:
        """Extract a number using regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else None


async def main():
    """Example usage."""
    scraper = ReraScraper(state="Karnataka")

    # Search for projects
    projects = await scraper.search_projects(
        project_name="Prestige",
    )

    print(f"Found {len(projects)} RERA projects")

    for project in projects[:5]:
        print(f"\n  {project.get('project_name')}")
        print(f"  RERA: {project.get('rera_number')}")
        print(f"  Builder: {project.get('builder_name')}")


if __name__ == "__main__":
    asyncio.run(main())
