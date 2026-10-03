import asyncio
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


CITY_STATE_MAP = {
    "Bangalore": "Karnataka",
    "Bengaluru": "Karnataka",
    "Chennai": "Tamil Nadu",
    "Coimbatore": "Tamil Nadu",
    "Madurai": "Tamil Nadu",
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
}


class SquareYardsScraper:

    SOURCE = "square_yards"

    def __init__(
        self,
        city: str = "Bangalore",
        bhk: int = 2,
    ):
        self.city = city
        self.bhk = bhk

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        }

    # =========================================================
    # SEARCH URL
    # =========================================================

    def build_search_url(self) -> str:

        city_slug = (
            self.city
            .lower()
            .replace(" ", "-")
        )

        return (
            "https://www.squareyards.com/sale/"
            f"{self.bhk}-bhk-for-sale-in-{city_slug}"
        )

    # =========================================================
    # HTTP
    # =========================================================

    async def fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> str:

        response = await client.get(
            url,
            headers=self.headers,
            timeout=30,
            follow_redirects=True,
        )

        response.raise_for_status()

        return response.text

    # =========================================================
    # URL VALIDATION
    # =========================================================

    @staticmethod
    def is_valid_property_url(
        url: str,
    ) -> bool:

        if not url:
            return False

        url_lower = url.lower()

        rejected_parts = [
            "/project/",
            "/projects/",
            "/property-rates",
            "/heatmap",
            "/calculator",
            "/guides",
            "/localities",
            "/property-search",
            "/residential-property",
            "/commercial-property",
        ]

        if any(
            part in url_lower
            for part in rejected_parts
        ):
            return False

        if "-npd-" in url_lower:
            return True

        if "/property-card/" in url_lower:
            return True

        return False

    # =========================================================
    # TEXT CLEANING
    # =========================================================

    @staticmethod
    def clean_text(
        value: str | None,
    ) -> str | None:

        if not value:
            return None

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        value = value.strip()

        return value or None

    # =========================================================
    # PRICE
    # =========================================================

    @staticmethod
    def price_to_inr(
        value: str,
    ) -> float | None:

        if not value:
            return None

        text = (
            value
            .lower()
            .replace(",", "")
            .replace("₹", "")
            .strip()
        )

        # Crore
        match = re.search(
            r"([\d.]+)\s*(?:cr|crore)",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                float(match.group(1))
                * 10_000_000
            )

        # Lakh
        match = re.search(
            r"([\d.]+)\s*(?:lac|lakh|lakhs)",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                float(match.group(1))
                * 100_000
            )

        # Plain amount
        match = re.search(
            r"([\d.]+)",
            text,
        )

        if match:
            return float(
                match.group(1)
            )

        return None

    # =========================================================
    # AREA
    # =========================================================

    @staticmethod
    def area_to_sqft(
        value: str,
    ) -> float | None:

        if not value:
            return None

        match = re.search(
            r"([\d,.]+)",
            value,
        )

        if not match:
            return None

        return float(
            match.group(1)
            .replace(",", "")
        )

    # =========================================================
    # LOCALITY EXTRACTION
    # =========================================================

    def extract_locality(
        self,
        soup: BeautifulSoup,
    ) -> str | None:

        # -----------------------------------------------------
        # 1. Meta description
        #
        # Example:
        #
        # Aparna Wonderwoods Mallasandra, Bangalore -
        # New Launch...
        #
        # -----------------------------------------------------

        meta = soup.find(
            "meta",
            attrs={"name": "description"},
        )

        if meta:

            description = self.clean_text(
                meta.get("content")
            )

            if description:

                match = re.search(
                    r"\b([A-Za-z][A-Za-z .'-]{2,60}),\s*"
                    r"Bangalore\b",
                    description,
                    re.IGNORECASE,
                )

                if match:

                    before_city = (
                        match.group(1)
                        .strip()
                    )

                    # Remove common project-name
                    # prefixes when possible.
                    words = before_city.split()

                    if len(words) > 1:

                        # In many Square Yards pages:
                        #
                        # "Project Name Locality"
                        #
                        # The locality is usually the final
                        # one/two word segment.
                        #
                        # We use known locality words when
                        # present.

                        known_localities = [
                            "Mallasandra",
                            "Varthur",
                            "Kurubarahalli",
                            "Bannerghatta",
                            "Devanahalli",
                            "Bagalur",
                            "Soukya Road",
                            "Sathnur",
                            "Nagasandra",
                            "Uttarahalli",
                            "Electronic City",
                            "Whitefield",
                            "Sarjapur",
                            "Yelahanka",
                            "Thanisandra",
                            "Hoskote",
                            "Bommasandra",
                            "Gunjur",
                            "Kommasandra",
                            "Dommasandra",
                            "Ullal",
                            "Mathikere",
                        ]

                        lower_value = (
                            before_city.lower()
                        )

                        for locality in known_localities:

                            if locality.lower() in lower_value:

                                return locality

                    # If it is a single word,
                    # it is likely the locality.
                    if len(words) == 1:
                        return before_city

        # -----------------------------------------------------
        # 2. Open Graph title
        # -----------------------------------------------------

        og_title = soup.find(
            "meta",
            attrs={
                "property": "og:title"
            },
        )

        if og_title:

            title = self.clean_text(
                og_title.get("content")
            )

            if title:

                match = re.search(
                    r"\b([A-Za-z][A-Za-z .'-]{2,60}),\s*"
                    r"Bangalore\b",
                    title,
                    re.IGNORECASE,
                )

                if match:

                    value = (
                        match.group(1)
                        .strip()
                    )

                    known_localities = [
                        "Mallasandra",
                        "Varthur",
                        "Kurubarahalli",
                        "Bannerghatta",
                        "Devanahalli",
                        "Bagalur",
                        "Soukya Road",
                        "Sathnur",
                        "Nagasandra",
                        "Uttarahalli",
                    ]

                    for locality in known_localities:

                        if (
                            locality.lower()
                            in value.lower()
                        ):
                            return locality

        # -----------------------------------------------------
        # 3. Breadcrumb
        # -----------------------------------------------------

        for element in soup.select(
            "nav a, .breadcrumb a"
        ):

            text = self.clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            match = re.search(
                r"Projects?\s+in\s+(.+)",
                text,
                re.IGNORECASE,
            )

            if match:

                locality = self.clean_text(
                    match.group(1)
                )

                if locality:
                    return locality

        return None

    # =========================================================
    # PRICE-LIST CONFIGURATIONS
    # =========================================================

    def extract_configurations(
        self,
        soup: BeautifulSoup,
    ) -> list[dict[str, Any]]:

        configurations = []

        # -----------------------------------------------------
        # Find Price List heading
        # -----------------------------------------------------

        price_heading = None

        for heading in soup.find_all(
            ["h2", "h3", "h4"]
        ):

            text = self.clean_text(
                heading.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                text
                and "price list"
                in text.lower()
            ):

                price_heading = heading
                break

        if not price_heading:
            return configurations

        # -----------------------------------------------------
        # Collect nearby page text
        # -----------------------------------------------------

        parts = []

        current = price_heading

        for _ in range(80):

            current = current.find_next()

            if not current:
                break

            text = self.clean_text(
                current.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if current.name == "h2":

                lower = text.lower()

                if (
                    "price list" not in lower
                    and "floor plans" not in lower
                ):
                    break

            parts.append(text)

        full_text = self.clean_text(
            " ".join(parts)
        )

        if not full_text:
            return configurations

        # -----------------------------------------------------
        # Pattern 1
        #
        # 2 BHK Apartment
        # 1292 Sq. Ft
        # ₹1.34 Cr
        # -----------------------------------------------------

        pattern_1 = re.compile(
            r"(?P<bhk>\d+)\s*BHK"
            r"\s+(?:Apartment|Flat)"
            r"\s+(?P<area>[\d,.]+)"
            r"\s*Sq\.?\s*Ft"
            r".{0,150}?"
            r"(?P<price>"
            r"₹\s*[\d,.]+"
            r"\s*(?:Cr|Crore|Lac|Lakh|Lakhs)"
            r")",
            re.IGNORECASE,
        )

        for match in pattern_1.finditer(
            full_text
        ):

            self._add_configuration(
                configurations,
                match,
            )

        # -----------------------------------------------------
        # Pattern 2 fallback
        # -----------------------------------------------------

        if not configurations:

            pattern_2 = re.compile(
                r"(?P<bhk>\d+)\s*BHK"
                r"\s+(?P<area>[\d,.]+)"
                r"\s*Sq\.?\s*Ft"
                r".{0,150}?"
                r"(?P<price>"
                r"₹\s*[\d,.]+"
                r"\s*(?:Cr|Crore|Lac|Lakh|Lakhs)"
                r")",
                re.IGNORECASE,
            )

            for match in pattern_2.finditer(
                full_text
            ):

                self._add_configuration(
                    configurations,
                    match,
                )

        # -----------------------------------------------------
        # DEDUPLICATE CONFIGURATIONS
        # -----------------------------------------------------

        unique = {}

        for item in configurations:

            key = (
                item["bedrooms"],
                item["area_sqft"],
                item["price"],
            )

            unique[key] = item

        return list(
            unique.values()
        )

    # =========================================================
    # ADD CONFIGURATION
    # =========================================================

    def _add_configuration(
        self,
        configurations: list[dict[str, Any]],
        match: re.Match,
    ) -> None:

        bhk = int(
            match.group("bhk")
        )

        if bhk != self.bhk:
            return

        area = self.area_to_sqft(
            match.group("area")
        )

        price = self.price_to_inr(
            match.group("price")
        )

        if area is None or price is None:
            return

        if area < 300 or area > 10_000:
            return

        if price < 500_000:
            return

        configurations.append(
            {
                "bedrooms": bhk,
                "property_type": "Apartment",
                "area_sqft": area,
                "price": price,
            }
        )

    # =========================================================
    # PARSE PAGE
    # =========================================================

    def parse_project_page(
        self,
        html: str,
        url: str,
    ) -> list[dict[str, Any]]:

        soup = BeautifulSoup(
            html,
            "lxml",
        )

        locality = self.extract_locality(
            soup
        )

        configurations = (
            self.extract_configurations(
                soup
            )
        )

        listings = []

        for config in configurations:

            price = config["price"]
            area = config["area_sqft"]

            price_per_sqft = (
                price / area
            )

            listings.append(
                {
                    "source": self.SOURCE,
                    "source_url": url,
                    "state": CITY_STATE_MAP.get(
                        self.city
                    ),
                    "city": self.city,
                    "locality": locality,
                    "pincode": None,
                    "property_type": "Apartment",
                    "transaction_type": "Sale",
                    "bedrooms": config[
                        "bedrooms"
                    ],
                    "bathrooms": None,
                    "area_sqft": area,
                    "price": price,
                    "price_per_sqft": (
                        price_per_sqft
                    ),
                    "furnishing": None,
                    "floor": None,
                    "total_floors": None,
                    "property_age": None,
                    "parking": None,
                    "listing_date": None,
                }
            )

        return listings

    # =========================================================
    # SEARCH PAGE → PROPERTY URLs
    # =========================================================

    async def collect_property_urls(
        self,
        client: httpx.AsyncClient,
    ) -> list[str]:

        search_url = (
            self.build_search_url()
        )

        print(
            "\n[SQUARE YARDS SEARCH URL]"
        )
        print(search_url)

        html = await self.fetch(
            client,
            search_url,
        )

        print(
            "\n[SQUARE YARDS SEARCH STATUS] "
            "Search page fetched successfully"
        )

        soup = BeautifulSoup(
            html,
            "lxml",
        )

        urls = set()

        for link in soup.find_all(
            "a",
            href=True,
        ):

            href = link.get(
                "href"
            )

            if not href:
                continue

            if href.startswith("/"):
                href = (
                    "https://www.squareyards.com"
                    + href
                )

            if not href.startswith(
                "https://www.squareyards.com"
            ):
                continue

            href = href.split("?")[0]

            if self.is_valid_property_url(
                href
            ):
                urls.add(href)

        result = sorted(urls)

        print(
            "\n[SQUARE YARDS] "
            f"Property URLs found: {len(result)}"
        )

        return result

    # =========================================================
    # SCRAPE
    # =========================================================

    async def scrape(
        self,
        limit: int = 12,
    ) -> list[dict[str, Any]]:

        all_listings = []

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
        ) as client:

            urls = (
                await self.collect_property_urls(
                    client
                )
            )

            urls = urls[:limit]

            print(
                "\n[SQUARE YARDS] "
                f"Pages to fetch: {len(urls)}"
            )

            for index, url in enumerate(
                urls,
                start=1,
            ):

                print(
                    f"\n[PROPERTY "
                    f"{index}/{len(urls)}]"
                )

                print(url)

                try:

                    html = await self.fetch(
                        client,
                        url,
                    )

                    listings = (
                        self.parse_project_page(
                            html,
                            url,
                        )
                    )

                    if not listings:

                        print(
                            f"  ✗ No matching "
                            f"{self.bhk} BHK "
                            "configuration"
                        )

                        continue

                    print(
                        f"  ✓ Found "
                        f"{len(listings)} "
                        f"unique "
                        f"{self.bhk} BHK "
                        "configuration(s)"
                    )

                    for listing in listings:

                        print(
                            f"     "
                            f"{listing['bedrooms']} BHK | "
                            f"{listing['area_sqft']:,.0f} sqft | "
                            f"₹{listing['price']:,.0f} | "
                            f"{listing['locality']} | "
                            f"₹{listing['price_per_sqft']:,.2f}/sqft"
                        )

                        all_listings.append(
                            listing
                        )

                except Exception as exc:

                    print(
                        f"  ✗ Error: {exc}"
                    )

        # -----------------------------------------------------
        # Final global deduplication
        # -----------------------------------------------------

        unique = {}

        for listing in all_listings:

            key = (
                listing["source_url"],
                listing["bedrooms"],
                listing["area_sqft"],
                listing["price"],
            )

            unique[key] = listing

        final_listings = list(
            unique.values()
        )

        print(
            "\n[SQUARE YARDS] "
            f"Final unique records: "
            f"{len(final_listings)}"
        )

        return final_listings


# =============================================================
# MAIN
# =============================================================

async def main():

    scraper = SquareYardsScraper(
        city="Bangalore",
        bhk=2,
    )

    listings = await scraper.scrape(
        limit=12
    )

    print("\n")
    print("=" * 80)
    print("FINAL SQUARE YARDS RESULTS")
    print("=" * 80)

    print(
        f"\nTotal valid records: "
        f"{len(listings)}"
    )

    for index, listing in enumerate(
        listings,
        start=1,
    ):

        print(
            f"\n{index}. "
            f"{listing['bedrooms']} BHK "
            f"{listing['property_type']}"
        )

        print(
            f"   Locality    : "
            f"{listing['locality']}"
        )

        print(
            f"   Area        : "
            f"{listing['area_sqft']:,.0f} sqft"
        )

        print(
            f"   Price       : "
            f"₹{listing['price']:,.0f}"
        )

        print(
            f"   Price/sqft  : "
            f"₹{listing['price_per_sqft']:,.2f}"
        )

        print(
            f"   URL         : "
            f"{listing['source_url']}"
        )


if __name__ == "__main__":
    asyncio.run(main())