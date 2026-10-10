"""
Enrich all existing CSV data with geocoded pincodes.

Usage:
    python -m property_data.enrich_with_geocoding
"""

import asyncio

import pandas as pd

from property_data.geocoder import enrich_listings_with_geocoding
from property_data.enricher import enrich_listing


async def main():
    # Read enriched CSV
    df = pd.read_csv("data/enriched_properties.csv")

    print(f"Enriching {len(df)} rows with geocoding...")

    # Convert to list of dicts
    listings = df.to_dict("records")

    # Enrich with geocoding (fills missing pincodes)
    enriched = await enrich_listings_with_geocoding(listings)

    # Re-enrich to update quality scores, but preserve original scores
    final = []
    for i, listing in enumerate(enriched):
        original_score = listings[i].get("data_quality_score", 0)

        # Fix imputed_fields: CSV reads empty strings as NaN (float)
        if "imputed_fields" in listing:
            imputed = listing["imputed_fields"]
            if isinstance(imputed, float) or imputed is None:
                listing["imputed_fields"] = []
            elif isinstance(imputed, str):
                listing["imputed_fields"] = [
                    f.strip() for f in imputed.split(",") if f.strip()
                ]

        result = enrich_listing(listing)
        # Keep the higher of the two scores
        result["data_quality_score"] = max(
            original_score,
            result.get("data_quality_score", 0),
        )
        final.append(result)

    # Create output DataFrame
    output_rows = []
    for e in final:
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
                "imputed_fields": ",".join(e.get("imputed_fields", [])),
            }
        )

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv("data/enriched_properties.csv", index=False)

    print(f"\nEnrichment complete!")
    print(f"  Rows: {len(out_df)}")
    print(f"  Quality scores: {out_df['data_quality_score'].min():.1f} — {out_df['data_quality_score'].max():.1f}")
    print(f"\nSample:")
    print(
        out_df[
            [
                "locality",
                "pincode",
                "bathrooms",
                "furnishing",
                "data_quality_score",
            ]
        ]
        .head(10)
        .to_string()
    )


if __name__ == "__main__":
    asyncio.run(main())
