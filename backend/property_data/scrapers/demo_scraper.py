from typing import Any

from property_data.scrapers.base_scraper import BasePropertyScraper


class DemoPropertyScraper(BasePropertyScraper):

    async def fetch_listings(
        self,
        city: str,
        locality: str | None = None,
    ) -> list[dict[str, Any]]:

        return [
            {
                "source": "demo_source",
                "source_url": "https://example.com/property/1",
                "state": "Karnataka",
                "city": city,
                "locality": locality or "Whitefield",
                "pincode": "560066",
                "property_type": "2 BHK Flat",
                "transaction_type": "Sale",
                "bedrooms": "2 BHK",
                "bathrooms": "2",
                "area_sqft": "1200 sq ft",
                "price": "₹65 Lakh",
                "furnishing": "Semi-Furnished",
                "floor": "5",
                "total_floors": "10",
                "property_age": "5",
                "parking": "1",
            },
            {
                "source": "demo_source",
                "source_url": "https://example.com/property/2",
                "state": "Karnataka",
                "city": city,
                "locality": locality or "Whitefield",
                "pincode": "560066",
                "property_type": "3 BHK Apartment",
                "transaction_type": "Sale",
                "bedrooms": "3 BHK",
                "bathrooms": "2",
                "area_sqft": "1500 sq ft",
                "price": "₹85 Lakh",
                "furnishing": "Furnished",
                "floor": "7",
                "total_floors": "12",
                "property_age": "3",
                "parking": "1",
            },
        ]