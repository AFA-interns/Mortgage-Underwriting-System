"""
Full enrichment pipeline — combines all data sources.

Pipeline:
1. Read raw scraped data (with NULLs)
2. Enrich with inference (fill bathrooms, furnishing, etc.)
3. Enrich with geocoding (fill pincodes)
4. Compute quality scores
5. Save to PostgreSQL

Usage:
    python -m property_data.pipeline_v2
"""

import asyncio

import pandas as pd

from property_data.enricher import enrich_listing
from property_data.geocoder import enrich_listings_with_geocoding
from property_data.scrapers.quality import get_quality_label


async def run_pipeline(
    input_csv: str = "data/dummy_properties.csv",
    output_csv: str = "data/enriched_properties.csv",
    save_to_db: bool = True,
) -> list[dict]:
    """
    Run the full enrichment pipeline.

    Args:
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        save_to_db: Whether to save results to PostgreSQL

    Returns:
        List of enriched property dicts
    """
    print("=" * 60)
    print("FULL ENRICHMENT PIPELINE")
    print("=" * 60)

    # Step 1: Read input data
    print("\n[Step 1] Reading input data...")
    df = pd.read_csv(input_csv)
    listings = df.to_dict("records")
    print(f"  Read {len(listings)} rows")

    # Step 2: Enrich with inference
    print("\n[Step 2] Enriching with inference...")
    enriched = []
    for listing in listings:
        mapped = {
            "source": "csv_import",
            "source_url": None,
            "city": listing.get("city"),
            "locality": listing.get("locality"),
            "pincode": None,
            "property_type": listing.get("property_type"),
            "transaction_type": "Sale",
            "bedrooms": listing.get("bhk"),
            "bathrooms": None,
            "area_sqft": listing.get("area_sqft"),
            "price": listing.get("price_inr"),
            "price_per_sqft": listing.get("price_per_sqft"),
            "furnishing": None,
            "floor": None,
            "total_floors": None,
            "property_age": listing.get("age_years"),
            "parking": None,
            "listing_date": None,
        }
        result = enrich_listing(mapped)
        enriched.append(result)
    print(f"  Enriched {len(enriched)} rows")

    # Step 3: Enrich with geocoding
    print("\n[Step 3] Enriching with geocoding...")
    enriched = await enrich_listings_with_geocoding(enriched)
    print(f"  Geocoding complete")

    # Step 4: Compute final quality scores
    print("\n[Step 4] Computing quality scores...")
    for listing in enriched:
        quality = get_quality_label(listing.get("data_quality_score", 0))
        listing["quality_label"] = quality
    print(f"  Quality scores computed")

    # Step 5: Save to CSV
    print("\n[Step 5] Saving to CSV...")
    output_rows = []
    for e in enriched:
        output_rows.append(
            {
                "id": e.get("id"),
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
                "quality_label": e.get("quality_label"),
                "imputed_fields": ",".join(e.get("imputed_fields", [])),
            }
        )

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv(output_csv, index=False)
    print(f"  Saved to {output_csv}")

    # Step 6: Save to PostgreSQL
    if save_to_db:
        print("\n[Step 6] Saving to PostgreSQL...")
        from property_data.database.connection import AsyncSessionLocal, init_db
        from property_data.database.models import PropertyListingDB
        from sqlalchemy import select

        await init_db()

        async with AsyncSessionLocal() as session:
            saved = 0
            skipped = 0

            for listing in enriched:
                # Check if already exists
                result = await session.execute(
                    select(PropertyListingDB).where(
                        PropertyListingDB.city == listing.get("city"),
                        PropertyListingDB.locality == listing.get("locality"),
                        PropertyListingDB.bedrooms == listing.get("bedrooms"),
                        PropertyListingDB.area_sqft == listing.get("area_sqft"),
                    )
                )

                if result.scalar_one_or_none():
                    skipped += 1
                    continue

                db_listing = PropertyListingDB(
                    source=listing.get("source", "pipeline"),
                    source_url=None,
                    state="Karnataka",
                    city=listing.get("city"),
                    locality=listing.get("locality"),
                    pincode=str(listing.get("pincode")) if listing.get("pincode") else None,
                    property_type=listing.get("property_type"),
                    transaction_type="Sale",
                    bedrooms=listing.get("bedrooms"),
                    bathrooms=listing.get("bathrooms"),
                    area_sqft=listing.get("area_sqft"),
                    price=listing.get("price"),
                    price_per_sqft=listing.get("price_per_sqft"),
                    furnishing=listing.get("furnishing"),
                    floor=listing.get("floor"),
                    total_floors=listing.get("total_floors"),
                    property_age=listing.get("property_age"),
                    parking=listing.get("parking"),
                    listing_date=None,
                    data_quality_score=listing.get("data_quality_score", 0.0),
                    quality_completeness=0.0,
                    quality_freshness=50.0,
                    source_count=1,
                    imputed_fields=listing.get("imputed_fields", []),
                    sources=["pipeline"],
                )
                session.add(db_listing)
                saved += 1

            await session.commit()
            print(f"  Saved: {saved} | Skipped: {skipped}")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Input rows: {len(listings)}")
    print(f"  Output rows: {len(enriched)}")
    print(f"  Quality range: {out_df['data_quality_score'].min():.1f} — {out_df['data_quality_score'].max():.1f}")
    print(f"  Mean quality: {out_df['data_quality_score'].mean():.1f}")

    return enriched


def main():
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
