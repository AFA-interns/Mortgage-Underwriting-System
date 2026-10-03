from typing import Any

from property_data.cleaners.property_cleaner import (
    clean_price,
    clean_area,
    clean_bedrooms,
    clean_property_type,
    clean_transaction_type,
    clean_integer,
    calculate_price_per_sqft,
)


def clean_listing(raw: dict[str, Any]) -> dict[str, Any]:

    cleaned = dict(raw)

    cleaned["price"] = clean_price(raw.get("price"))
    cleaned["area_sqft"] = clean_area(raw.get("area_sqft"))
    cleaned["bedrooms"] = clean_bedrooms(raw.get("bedrooms"))
    cleaned["bathrooms"] = clean_integer(raw.get("bathrooms"))

    cleaned["floor"] = clean_integer(raw.get("floor"))
    cleaned["total_floors"] = clean_integer(raw.get("total_floors"))
    cleaned["property_age"] = clean_integer(raw.get("property_age"))
    cleaned["parking"] = clean_integer(raw.get("parking"))

    cleaned["property_type"] = clean_property_type(
        raw.get("property_type")
    )

    cleaned["transaction_type"] = clean_transaction_type(
        raw.get("transaction_type")
    )

    cleaned["price_per_sqft"] = calculate_price_per_sqft(
        cleaned["price"],
        cleaned["area_sqft"],
    )

    return cleaned