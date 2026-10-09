"""
Run the enrichment pipeline on existing CSV data.

Usage:
    python -m property_data.run_enrichment
"""

import pandas as pd
from property_data.enricher import enrich_listing


def main():
    # Read existing CSV
    df = pd.read_csv("data/dummy_properties.csv")

    # Convert to list of dicts
    listings = df.to_dict("records")

    # Enrich each listing
    enriched = []
    for listing in listings:
        # Map CSV columns to internal format
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

    # Create output DataFrame
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
                "imputed_fields": ",".join(e.get("imputed_fields", [])),
            }
        )

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv("data/enriched_properties.csv", index=False)

    print("ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"Input rows: {len(df)}")
    print(f"Output rows: {len(out_df)}")
    print()
    print("QUALITY SCORES:")
    print(out_df["data_quality_score"].describe())
    print()
    print("SAMPLE OUTPUT:")
    print(
        out_df[
            [
                "locality",
                "bedrooms",
                "bathrooms",
                "furnishing",
                "parking",
                "data_quality_score",
            ]
        ]
        .head(10)
        .to_string()
    )
    print()
    print("IMPUTED FIELDS PER ROW:")
    for _, row in out_df.iterrows():
        print(
            f"  {row['locality']} {row['bedrooms']}BHK: "
            f"{row['imputed_fields']}"
        )


if __name__ == "__main__":
    main()
