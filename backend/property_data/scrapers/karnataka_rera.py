"""
Karnataka RERA scraper — state-specific parser.

Karnataka RERA website: https://rera.karnataka.gov.in/
This is a government website with official project data.

Note: The website structure may change. This parser is based on
the current structure as of 2026.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


KARNATAKA_RERA_URL = "https://rera.karnataka.gov.in/"


class KarnatakaReraScraper:
    """
    Karnataka RERA scraper — extracts official project data.

    Data available:
    - Project name, RERA number
    - Builder/promoter name
    - Project location (city, locality)
    - Total units, area
    - Approval date, completion date
    """

    SOURCE = "karnataka_rera"
    BASE_URL = KARNATAKA_RERA_URL

    def __init__(self):
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
        rera_number: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for RERA-registered projects in Karnataka.

        Args:
            project_name: Optional project name filter
            builder_name: Optional builder name filter
            rera_number: Optional RERA number filter

        Returns:
            List of project dicts
        """
        # Karnataka RERA uses a search endpoint
        search_url = f"{self.BASE_URL}projectDetails"

        params: dict[str, str] = {}
        if project_name:
            params["projectName"] = project_name
        if builder_name:
            params["builderName"] = builder_name
        if rera_number:
            params["reraNumber"] = rera_number

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
                print(f"[KARNATAKA RERA] Search failed: {exc}")
                return []

    def _parse_search_results(self, html: str) -> list[dict[str, Any]]:
        """Parse Karnataka RERA search results."""
        soup = BeautifulSoup(html, "lxml")
        projects: list[dict[str, Any]] = []

        # Look for project cards or table rows
        # Karnataka RERA uses a card-based layout
        for card in soup.find_all("div", class_=re.compile(r"project|card|item")):
            project = self._extract_project_from_card(card)
            if project:
                projects.append(project)

        # Fallback: try table rows
        if not projects:
            for row in soup.find_all("tr"):
                project = self._extract_project_from_row(row)
                if project:
                    projects.append(project)

        return projects

    def _extract_project_from_card(self, card: Any) -> dict[str, Any] | None:
        """Extract project data from a card element."""
        text = card.get_text()

        # Look for RERA number
        rera_match = re.search(
            r"[A-Z]+/[A-Z]+/RERA/\d+/\d+/[A-Z]+/\d+/\d+",
            text,
        )
        if not rera_match:
            return None

        return {
            "source": self.SOURCE,
            "rera_number": rera_match.group(),
            "project_name": self._extract_field(text, r"Project Name\s*[:]\s*(.+)"),
            "builder_name": self._extract_field(text, r"Builder\s*[:]\s*(.+)"),
            "city": self._extract_field(text, r"City\s*[:]\s*(.+)"),
            "locality": self._extract_field(text, r"Locality\s*[:]\s*(.+)"),
            "total_units": self._extract_number(text, r"Total Units\s*[:]\s*(\d+)"),
            "area_sqft": self._extract_number(text, r"Area\s*[:]\s*(\d+)"),
            "approval_date": self._extract_field(text, r"Approval Date\s*[:]\s*(.+)"),
            "completion_date": self._extract_field(text, r"Completion Date\s*[:]\s*(.+)"),
        }

    def _extract_project_from_row(self, row: Any) -> dict[str, Any] | None:
        """Extract project data from a table row."""
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            return None

        texts = [cell.get_text(strip=True) for cell in cells]

        # Look for RERA number
        rera_number = None
        for text in texts:
            match = re.search(
                r"[A-Z]+/[A-Z]+/RERA/\d+/\d+/[A-Z]+/\d+/\d+",
                text,
            )
            if match:
                rera_number = match.group()
                break

        if not rera_number:
            return None

        return {
            "source": self.SOURCE,
            "rera_number": rera_number,
            "project_name": texts[0] if texts else None,
            "builder_name": texts[1] if len(texts) > 1 else None,
            "city": None,
            "locality": None,
            "total_units": None,
            "area_sqft": None,
            "approval_date": None,
            "completion_date": None,
        }

    def _extract_field(self, text: str, pattern: str) -> str | None:
        """Extract a field using regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_number(self, text: str, pattern: str) -> int | None:
        """Extract a number using regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    async def get_project_details(self, rera_number: str) -> dict[str, Any] | None:
        """
        Get detailed information for a specific RERA project.

        Args:
            rera_number: RERA registration number

        Returns:
            Project detail dict or None
        """
        detail_url = f"{self.BASE_URL}projectDetails?reraNumber={rera_number}"

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
                print(f"[KARNATAKA RERA] Detail fetch failed: {exc}")
                return None

    def _parse_project_details(
        self,
        html: str,
        rera_number: str,
    ) -> dict[str, Any] | None:
        """Parse Karnataka RERA project detail page."""
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()

        return {
            "source": self.SOURCE,
            "rera_number": rera_number,
            "project_name": self._extract_field(text, r"Project Name\s*[:]\s*(.+)"),
            "builder_name": self._extract_field(text, r"Builder\s*[:]\s*(.+)"),
            "city": self._extract_field(text, r"City\s*[:]\s*(.+)"),
            "locality": self._extract_field(text, r"Locality\s*[:]\s*(.+)"),
            "property_type": self._extract_field(text, r"Property Type\s*[:]\s*(.+)"),
            "total_floors": self._extract_number(text, r"Total Floors\s*[:]\s*(\d+)"),
            "total_units": self._extract_number(text, r"Total Units\s*[:]\s*(\d+)"),
            "parking": self._extract_number(text, r"Parking\s*[:]\s*(\d+)"),
            "area_sqft": self._extract_number(text, r"Area\s*[:]\s*(\d+)"),
            "approval_date": self._extract_field(text, r"Approval Date\s*[:]\s*(.+)"),
            "completion_date": self._extract_field(text, r"Completion Date\s*[:]\s*(.+)"),
        }


async def main():
    """Example usage."""
    scraper = KarnatakaReraScraper()

    # Search for projects
    projects = await scraper.search_projects(project_name="Prestige")

    print(f"Found {len(projects)} Karnataka RERA projects")

    for project in projects[:5]:
        print(f"\n  {project.get('project_name')}")
        print(f"  RERA: {project.get('rera_number')}")
        print(f"  Builder: {project.get('builder_name')}")
        print(f"  City: {project.get('city')}")


if __name__ == "__main__":
    asyncio.run(main())
