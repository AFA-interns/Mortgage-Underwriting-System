"""
Housing.com scraper using Playwright.

Scrapes property listings from Housing.com with JavaScript rendering,
auto-scroll, and JSON-LD extraction.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from property_data.scrapers.jsonld_extractor import extract_from_all_sources
from property_data.scrapers.playwright_base import PlaywrightBaseScraper


CITY_STATE_MAP = {
    "Bangalore": "Karnataka",
    "Bengaluru": "Karnataka",
    "Chennai": "Tamil Nadu",
    "Hyderabad": "Telangana",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Delhi": "Delhi",
    "Noida": "Uttar Pradesh",
    "Gurgaon": "Haryana",
    "Gurugram": "Haryana",
    "Kolkata": "West Bengal",
    "Ahmedabad": "Gujarat",
    "Jaipur": "Rajasthan",
    "Lucknow": "Uttar Pradesh",
    "Chandigarh": "Chandigarh",
    "Kochi": "Kerala",
    "Indore": "Madhya Pradesh",
    "Bhopal": "Madhya Pradesh",
    "Nagpur": "Maharashtra",
    "Surat": "Gujarat",
    "Thane": "Maharashtra",
    "Navi Mumbai": "Maharashtra",
    "Mysore": "Karnataka",
    "Mangalore": "Karnataka",
    "Visakhapatnam": "Andhra Pradesh",
    "Vijayawada": "Andhra Pradesh",
    "Coimbatore": "Tamil Nadu",
    "Madurai": "Tamil Nadu",
    "Nashik": "Maharashtra",
    "Goa": "Goa",
    "Vadodara": "Gujarat",
    "Rajkot": "Gujarat",
}


class HousingScraper(PlaywrightBaseScraper):
    """
    Housing.com scraper — Playwright-based with JSON-LD extraction.
    """

    SOURCE = "housing"
    BASE_URL = "https://housing.com"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def build_search_url(
        self,
        city: str,
        bhk: int = 2,
        locality: str | None = None,
    ) -> str:
        """Build Housing.com search URL."""
        city_slug = city.lower().replace(" ", "-")

        if locality:
            locality_slug = locality.lower().replace(" ", "-")
            return (
                f"{self.BASE_URL}/in/buy/"
                f"{bhk}-bhk-{locality_slug}-{city_slug}"
            )

        return f"{self.BASE_URL}/in/buy/{bhk}-bhk-{city_slug}"

    async def fetch_listings(
        self,
        city: str,
        locality: str | None = None,
        bhk: int = 2,
        limit: int = 20,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Fetch listings from Housing.com.

        Args:
            city: City name
            locality: Optional locality filter
            bhk: Number of bedrooms
            limit: Maximum number of listings

        Returns:
            List of normalized property listing dicts
        """
        from playwright.async_api import async_playwright

        all_listings: list[dict[str, Any]] = []

        async with async_playwright() as playwright:
            browser, context = await self._create_context(playwright)
            page = await context.new_page()

            try:
                # Step 1: Collect property URLs from search page
                search_url = self.build_search_url(city, bhk, locality)
                print(f"\n[HOUSING.COM] Search URL: {search_url}")

                html = await self._fetch_page(page, search_url)
                soup = BeautifulSoup(html, "lxml")

                property_urls = self._extract_property_urls(soup)
                print(f"[HOUSING.COM] Found {len(property_urls)} property URLs")

                # Step 2: Visit each property page
                for i, url in enumerate(property_urls[:limit]):
                    print(
                        f"\n[HOUSING.COM] "
                        f"[{i+1}/{min(len(property_urls), limit)}] {url}"
                    )

                    try:
                        detail_html = await self._fetch_page(page, url)
                        listings = self._parse_property_page(
                            detail_html,
                            url,
                            city,
                        )

                        if listings:
                            all_listings.extend(listings)
                            print(f"  Found {len(listings)} configuration(s)")
                        else:
                            print(f"  No matching {bhk} BHK configuration")

                    except Exception as exc:
                        print(f"  Error: {exc}")
                        continue

            finally:
                await context.close()
                await browser.close()

        return self._deduplicate(all_listings)

    def _extract_property_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract property detail page URLs from search results."""
        urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href:
                continue

            if href.startswith("/"):
                href = self.BASE_URL + href

            if not href.startswith(self.BASE_URL):
                continue

            href = href.split("?")[0]

            # Housing.com property URL patterns
            if (
                "/property/" in href
                or "/project/" in href
                or "/in/buy/" in href
            ):
                urls.add(href)

        return sorted(urls)

    def _parse_property_page(
        self,
        html: str,
        url: str,
        city: str,
    ) -> list[dict[str, Any]]:
        """Parse a property detail page and extract all configurations."""
        soup = BeautifulSoup(html, "lxml")

        # Extract structured data
        structured = extract_from_all_sources(html)

        # Extract locality
        locality = self._extract_locality(soup, structured)

        # Extract configurations
        configurations = self._extract_configurations(soup)

        # If no configurations found, try structured data
        if not configurations:
            configurations = self._extract_from_structured(structured)

        listings: list[dict[str, Any]] = []

        for config in configurations:
            area = config.get("area_sqft")
            price = config.get("price")

            if not area or not price:
                continue

            if area < 300 or area > 10000:
                continue

            if price < 500000:
                continue

            price_per_sqft = price / area

            listing = {
                "source": self.SOURCE,
                "source_url": url,
                "state": CITY_STATE_MAP.get(city),
                "city": city,
                "locality": locality,
                "pincode": self._extract_pincode(soup),
                "property_type": config.get("property_type", "Apartment"),
                "transaction_type": "Sale",
                "bedrooms": config.get("bedrooms"),
                "bathrooms": self._extract_bathrooms(soup),
                "area_sqft": area,
                "price": price,
                "price_per_sqft": price_per_sqft,
                "furnishing": self._extract_furnishing(soup),
                "floor": self._extract_floor(soup),
                "total_floors": self._extract_total_floors(soup),
                "property_age": self._extract_property_age(soup),
                "parking": self._extract_parking(soup),
                "listing_date": None,
            }

            listings.append(listing)

        return listings

    def _extract_locality(
        self,
        soup: BeautifulSoup,
        structured: dict[str, Any],
    ) -> str | None:
        """Extract locality from multiple sources."""
        # Try structured data first
        address = structured.get("address", {})
        if isinstance(address, dict):
            locality = address.get("addressLocality")
            if locality:
                return locality

        # Try meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            desc = meta.get("content", "")
            match = re.search(
                r"\bin\s+([A-Z][A-Za-z\s]+?)(?:,|\s*-|\s*$)",
                desc,
            )
            if match:
                return match.group(1).strip()

        # Try breadcrumb
        for element in soup.select("nav a, .breadcrumb a"):
            text = element.get_text(" ", strip=True)
            match = re.search(
                r"(?:Projects?|Properties?)\s+in\s+(.+)",
                text,
                re.IGNORECASE,
            )
            if match:
                return match.group(1).strip()

        # Try page title
        title = soup.find("title")
        if title:
            text = title.get_text()
            match = re.search(
                r"(?:in|at)\s+([A-Z][A-Za-z\s]+?)(?:,|\s*-|\s*\||$)",
                text,
            )
            if match:
                return match.group(1).strip()

        return None

    def _extract_configurations(
        self,
        soup: BeautifulSoup,
    ) -> list[dict[str, Any]]:
        """Extract BHK/area/price configurations from the page."""
        configurations: list[dict[str, Any]] = []

        # Housing.com uses various class patterns for price/area
        # Try to find price and area in the page text
        text = soup.get_text()

        # Pattern: "2 BHK 1200 sq.ft. ₹1.2 Cr"
        pattern = re.compile(
            r"(?P<bhk>\d+)\s*BHK"
            r".*?"
            r"(?P<area>[\d,.]+)\s*(?:sq\.?\s*ft|sqft|sq\.?\s*feet)"
            r".*?"
            r"(?P<price>"
            r"₹\s*[\d,.]+"
            r"\s*(?:Cr|Crore|Lac|Lakh|Lakhs)"
            r")",
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(text):
            bhk = int(match.group("bhk"))
            area = self._parse_area(match.group("area"))
            price = self._parse_price(match.group("price"))

            if area and price:
                configurations.append({
                    "bedrooms": bhk,
                    "property_type": "Apartment",
                    "area_sqft": area,
                    "price": price,
                })

        return configurations

    def _extract_from_structured(
        self,
        structured: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract configurations from JSON-LD/structured data."""
        configurations: list[dict[str, Any]] = []

        # Look for offers in structured data
        offers = structured.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price")
            if price:
                configurations.append({
                    "bedrooms": None,
                    "property_type": "Apartment",
                    "area_sqft": None,
                    "price": float(price),
                })

        return configurations

    def _extract_pincode(self, soup: BeautifulSoup) -> str | None:
        """Extract pincode from page."""
        text = soup.get_text()
        match = re.search(r"\b(\d{6})\b", text)
        return match.group(1) if match else None

    def _extract_bathrooms(self, soup: BeautifulSoup) -> int | None:
        """Extract bathroom count."""
        text = soup.get_text()
        match = re.search(r"(\d+)\s*Bath", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _extract_furnishing(self, soup: BeautifulSoup) -> str | None:
        """Extract furnishing status."""
        text = soup.get_text()
        if re.search(r"\b[Ff]urnished\b", text):
            if re.search(r"\b[Ss]emi[-\s]?[Ff]urnished\b", text):
                return "Semi-Furnished"
            if re.search(r"\b[Uu]nfurnished\b", text):
                return "Unfurnished"
            return "Furnished"
        return None

    def _extract_floor(self, soup: BeautifulSoup) -> int | None:
        """Extract floor number."""
        text = soup.get_text()
        match = re.search(r"Floor\s*[:#]?\s*(\d+)", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _extract_total_floors(self, soup: BeautifulSoup) -> int | None:
        """Extract total floors."""
        text = soup.get_text()
        match = re.search(
            r"(?:Total\s+Floors?|Floors?)\s*[:#]?\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        return int(match.group(1)) if match else None

    def _extract_property_age(self, soup: BeautifulSoup) -> int | None:
        """Extract property age."""
        text = soup.get_text()
        match = re.search(
            r"(?:Age|Property\s+Age)\s*[:#]?\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        return int(match.group(1)) if match else None

    def _extract_parking(self, soup: BeautifulSoup) -> int | None:
        """Extract parking count."""
        text = soup.get_text()
        match = re.search(
            r"(\d+)\s*(?:Car\s+)?Parking",
            text,
            re.IGNORECASE,
        )
        return int(match.group(1)) if match else None

    def _parse_area(self, value: str) -> float | None:
        """Parse area string to sqft."""
        if not value:
            return None
        match = re.search(r"([\d,.]+)", value)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))

    def _parse_price(self, value: str) -> float | None:
        """Parse price string to INR."""
        if not value:
            return None

        text = value.lower().replace(",", "").replace("₹", "").strip()

        # Crore
        match = re.search(r"([\d.]+)\s*(?:cr|crore)", text, re.IGNORECASE)
        if match:
            return float(match.group(1)) * 10_000_000

        # Lakh
        match = re.search(r"([\d.]+)\s*(?:lac|lakh|lakhs)", text, re.IGNORECASE)
        if match:
            return float(match.group(1)) * 100_000

        # Plain
        match = re.search(r"([\d.]+)", text)
        if match:
            return float(match.group(1))

        return None

    def _deduplicate(
        self,
        listings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove duplicate listings."""
        seen: set[tuple] = set()
        unique: list[dict[str, Any]] = []

        for listing in listings:
            key = (
                listing.get("source_url"),
                listing.get("bedrooms"),
                listing.get("area_sqft"),
                listing.get("price"),
            )
            if key not in seen:
                seen.add(key)
                unique.append(listing)

        return unique
