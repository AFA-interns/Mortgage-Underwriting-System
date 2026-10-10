"""
Expand the property dataset to cover more Indian cities.

Generates realistic synthetic data for major cities based on
known property market rates.

Usage:
    python -m property_data.expand_cities
"""

import pandas as pd


# Realistic property data for major Indian cities
# Price per sqft ranges based on 2026 market rates
CITY_DATA = {
    "Mumbai": {
        "localities": [
            ("Andheri West", 18000, 25000),
            ("Andheri East", 16000, 22000),
            ("Bandra West", 28000, 40000),
            ("Bandra East", 20000, 28000),
            ("Juhu", 25000, 35000),
            ("Powai", 18000, 25000),
            ("Worli", 30000, 45000),
            ("Lower Parel", 28000, 40000),
            ("Malad West", 14000, 20000),
            ("Goregaon West", 16000, 22000),
        ],
        "state": "Maharashtra",
    },
    "Delhi": {
        "localities": [
            ("Dwarka", 8000, 12000),
            ("Rohini", 7000, 10000),
            ("Saket", 12000, 18000),
            ("Vasant Kunj", 15000, 22000),
            ("Greater Kailash", 20000, 30000),
            ("Hauz Khas", 18000, 25000),
            ("Lajpat Nagar", 14000, 20000),
            ("Karol Bagh", 12000, 16000),
            ("Paschim Vihar", 9000, 13000),
            ("Uttam Nagar", 6000, 9000),
        ],
        "state": "Delhi",
    },
    "Hyderabad": {
        "localities": [
            ("HITEC City", 9000, 14000),
            ("Gachibowli", 10000, 16000),
            ("Banjara Hills", 15000, 22000),
            ("Jubilee Hills", 14000, 20000),
            ("Madhapur", 9000, 13000),
            ("Kondapur", 8000, 12000),
            ("Miyapur", 6000, 9000),
            ("Secunderabad", 7000, 11000),
            ("Kukatpally", 6000, 9000),
            ("LB Nagar", 5000, 8000),
        ],
        "state": "Telangana",
    },
    "Chennai": {
        "localities": [
            ("OMR", 7000, 11000),
            ("Adyar", 12000, 18000),
            ("Anna Nagar", 10000, 15000),
            ("Velachery", 9000, 14000),
            ("Porur", 6000, 9000),
            ("Thoraipakkam", 7000, 10000),
            ("Egmore", 8000, 12000),
            ("T Nagar", 11000, 16000),
            ("Perambur", 5000, 8000),
            ("Chromepet", 6000, 9000),
        ],
        "state": "Tamil Nadu",
    },
    "Pune": {
        "localities": [
            ("Hinjewadi", 7000, 11000),
            ("Wakad", 6000, 9000),
            ("Baner", 8000, 12000),
            ("Aundh", 9000, 14000),
            ("Koregaon Park", 12000, 18000),
            ("Viman Nagar", 8000, 12000),
            ("Hadapsar", 5000, 8000),
            ("Pimpri", 4000, 7000),
            ("Chinchwad", 4000, 6000),
            ("Kothrud", 7000, 10000),
        ],
        "state": "Maharashtra",
    },
    "Kolkata": {
        "localities": [
            ("Salt Lake", 6000, 9000),
            ("New Town", 7000, 11000),
            ("Ballygunge", 10000, 15000),
            ("Alipore", 12000, 18000),
            ("Dum Dum", 4000, 6000),
            ("Garia", 5000, 8000),
            ("Tollygunge", 7000, 10000),
            ("Behala", 5000, 7000),
            ("Rajarhat", 6000, 9000),
            ("Kasba", 5000, 8000),
        ],
        "state": "West Bengal",
    },
    "Ahmedabad": {
        "localities": [
            ("Satellite", 6000, 9000),
            ("Vastrapur", 7000, 10000),
            ("Maninagar", 4000, 6000),
            ("Gota", 5000, 8000),
            ("Bopal", 6000, 9000),
            ("Thaltej", 7000, 11000),
            ("Vastral", 4000, 6000),
            ("Chandkheda", 5000, 7000),
            ("Sanand", 3000, 5000),
            ("Gandhinagar", 5000, 8000),
        ],
        "state": "Gujarat",
    },
    "Jaipur": {
        "localities": [
            ("Malviya Nagar", 5000, 8000),
            ("Jagatpura", 4000, 6000),
            ("Mansarovar", 5000, 7000),
            ("Vaishali Nagar", 6000, 9000),
            ("Ajmer Road", 4000, 6000),
            ("Sanganer", 4000, 6000),
            ("Civil Lines", 7000, 10000),
            ("C-Scheme", 8000, 12000),
            ("Bani Park", 5000, 7000),
            ("Pratap Nagar", 4000, 6000),
        ],
        "state": "Rajasthan",
    },
}


def generate_city_data(city: str, config: dict) -> list[dict]:
    """Generate realistic property listings for a city."""
    import random

    listings = []
    localities = config["localities"]
    state = config["state"]

    for locality, min_ppsf, max_ppsf in localities:
        # Generate 3-5 listings per locality
        num_listings = random.randint(3, 5)

        for _ in range(num_listings):
            bhk = random.choice([1, 2, 2, 2, 3, 3, 3, 4])
            area = random.randint(500, 2500)
            ppsf = random.randint(min_ppsf, max_ppsf)
            price = area * ppsf
            age = random.randint(0, 15)

            listings.append(
                {
                    "source": "synthetic",
                    "source_url": None,
                    "state": state,
                    "city": city,
                    "locality": locality,
                    "pincode": None,
                    "property_type": "Apartment",
                    "transaction_type": "Sale",
                    "bedrooms": bhk,
                    "bathrooms": None,
                    "area_sqft": area,
                    "price": price,
                    "price_per_sqft": ppsf,
                    "furnishing": None,
                    "floor": None,
                    "total_floors": None,
                    "property_age": age,
                    "parking": None,
                    "listing_date": None,
                }
            )

    return listings


def main():
    import asyncio

    from property_data.enricher import enrich_listing
    from property_data.geocoder import enrich_listings_with_geocoding

    print("=" * 60)
    print("EXPANDING PROPERTY DATASET")
    print("=" * 60)

    all_listings = []

    # Generate data for each city
    for city, config in CITY_DATA.items():
        print(f"\nGenerating data for {city}...")
        listings = generate_city_data(city, config)
        print(f"  Generated {len(listings)} listings")
        all_listings.extend(listings)

    print(f"\nTotal listings generated: {len(all_listings)}")

    # Enrich all listings
    print("\nEnriching listings...")
    enriched = []
    for listing in all_listings:
        result = enrich_listing(listing)
        enriched.append(result)

    # Geocode listings
    print("Geocoding listings...")
    enriched = asyncio.run(enrich_listings_with_geocoding(enriched))

    # Create output DataFrame
    output_rows = []
    for e in enriched:
        output_rows.append(
            {
                "id": None,
                "source": e.get("source"),
                "city": e.get("city"),
                "locality": e.get("locality"),
                "pincode": e.get("pincode"),
                "property_type": e.get("property_type"),
                "bedrooms": e.get("bedrooms"),
                "bathrooms": e.get("bathrooms"),
                "area_sqft": e.get("area_sqft"),
                "price_inr": e.get("price"),
                "price_per_sqft": e.get("price_per_sqft"),
                "furnishing": e.get("furnishing"),
                "floor": e.get("floor"),
                "total_floors": e.get("total_floors"),
                "property_age": e.get("property_age"),
                "parking": e.get("parking"),
                "data_quality_score": e.get("data_quality_score"),
                "imputed_fields": ",".join(e.get("imputed_fields", [])),
            }
        )

    out_df = pd.DataFrame(output_rows)

    # Save to CSV
    output_file = "data/expanded_properties.csv"
    out_df.to_csv(output_file, index=False)

    print(f"\nExpanded dataset saved to: {output_file}")
    print(f"  Total rows: {len(out_df)}")
    print(f"  Cities: {out_df['city'].nunique()}")
    print(f"  Localities: {out_df['locality'].nunique()}")
    print(f"  Quality range: {out_df['data_quality_score'].min():.1f} — {out_df['data_quality_score'].max():.1f}")
    print(f"  Mean quality: {out_df['data_quality_score'].mean():.1f}")

    # Print city breakdown
    print("\nCity breakdown:")
    for city in out_df["city"].unique():
        city_df = out_df[out_df["city"] == city]
        print(f"  {city}: {len(city_df)} listings, {city_df['locality'].nunique()} localities")


if __name__ == "__main__":
    main()
