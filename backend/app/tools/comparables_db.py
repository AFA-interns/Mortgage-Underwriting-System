import pandas as pd
import os


CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    '..',
    'data',
    'dummy_properties.csv'
)


def normalize_property_type(property_type: str) -> str:
    """
    Convert different property-type names into a common category.
    """

    value = str(property_type).lower().strip()

    if any(
        keyword in value
        for keyword in [
            "apartment",
            "flat",
            "residential flat",
            "residential apartment",
        ]
    ):
        return "apartment"

    if "independent house" in value:
        return "independent house"

    if "villa" in value:
        return "villa"

    return value


def get_comparables(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float
) -> list[dict]:

    if not os.path.exists(CSV_PATH):
        return []

    df = pd.read_csv(CSV_PATH)

    df["locality_clean"] = (
        df["locality"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    df["city_clean"] = (
        df["city"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    df["property_type_clean"] = (
        df["property_type"]
        .apply(normalize_property_type)
    )

    t_locality = locality.lower().strip()
    t_city = city.lower().strip()
    t_prop_type = normalize_property_type(property_type)

    mask = (
        (df["city_clean"] == t_city)
        & (df["locality_clean"] == t_locality)
        & (df["property_type_clean"] == t_prop_type)
    )

    filtered = df[mask]

    if filtered.empty:
        return []

    # Keep properties within ±20% of subject property area.
    min_area = area_sqft * 0.8
    max_area = area_sqft * 1.2

    filtered = filtered[
        (filtered["area_sqft"] >= min_area)
        & (filtered["area_sqft"] <= max_area)
    ]

    filtered = filtered.drop(
        columns=[
            "locality_clean",
            "city_clean",
            "property_type_clean",
        ]
    )

    return filtered.to_dict(orient="records")