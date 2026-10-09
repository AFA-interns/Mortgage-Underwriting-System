"""
Test the geocoder and RERA scraper.

Usage:
    python -m property_data.test_geocoder
"""

import asyncio

from property_data.geocoder import geocode_locality, enrich_listings_with_geocoding
from property_data.scrapers.rera_scraper import ReraScraper


async def test_geocoder():
    """Test geocoding with Nominatim."""
    print("=" * 60)
    print("TESTING GEOCODER")
    print("=" * 60)

    # Test 1: Geocode a known locality
    result = await geocode_locality("Whitefield", "Bangalore", "Karnataka")
    if result:
        print(f"\n[PASS] Geocoding Whitefield, Bangalore")
        print(f"  Pincode: {result.get('pincode')}")
        print(f"  Lat/Lon: {result.get('lat')}, {result.get('lon')}")
    else:
        print(f"\n[FAIL] Geocoding Whitefield, Bangalore")

    # Test 2: Geocode another locality
    result2 = await geocode_locality("Indiranagar", "Bangalore", "Karnataka")
    if result2:
        print(f"\n[PASS] Geocoding Indiranagar, Bangalore")
        print(f"  Pincode: {result2.get('pincode')}")
    else:
        print(f"\n[FAIL] Geocoding Indiranagar, Bangalore")

    # Test 3: Enrich listings with geocoding
    test_listings = [
        {
            "locality": "Koramangala",
            "city": "Bangalore",
            "pincode": None,
            "imputed_fields": [],
        },
        {
            "locality": "HSR Layout",
            "city": "Bangalore",
            "pincode": None,
            "imputed_fields": [],
        },
    ]

    print(f"\nEnriching {len(test_listings)} listings with geocoding...")
    enriched = await enrich_listings_with_geocoding(test_listings)

    for listing in enriched:
        pincode = listing.get("pincode")
        if pincode:
            print(f"  [PASS] {listing['locality']} -> pincode {pincode}")
        else:
            print(f"  [FAIL] {listing['locality']} -> no pincode")


async def test_rera_scraper():
    """Test RERA scraper."""
    print("\n" + "=" * 60)
    print("TESTING RERA SCRAPER")
    print("=" * 60)

    scraper = ReraScraper(state="Karnataka")

    # Test search
    projects = await scraper.search_projects(project_name="Prestige")

    if projects:
        print(f"\n[PASS] Found {len(projects)} RERA projects")
        for p in projects[:3]:
            print(f"  - {p.get('project_name')} ({p.get('rera_number')})")
    else:
        print(f"\n[INFO] No RERA projects found (website structure may have changed)")
        print(f"  RERA URL: {scraper.base_url}")


async def main():
    await test_geocoder()
    await test_rera_scraper()


if __name__ == "__main__":
    asyncio.run(main())
