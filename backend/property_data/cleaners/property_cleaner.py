import re
from typing import Any


def clean_price(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()

    text = (
        text
        .replace("₹", "")
        .replace("rs.", "")
        .replace("rs", "")
        .replace(",", "")
        .strip()
    )

    match = re.search(
        r"([\d.]+)\s*"
        r"(crore|cr|lakh|lakhs|lac|l|million)?",
        text,
    )

    if not match:
        return None

    number = float(match.group(1))

    unit = (match.group(2) or "").lower()

    if unit in ("crore", "cr"):
        number *= 10_000_000

    elif unit in ("lakh", "lakhs", "lac", "l"):
        number *= 100_000

    elif unit == "million":
        number *= 1_000_000

    return number

def clean_area(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"[\d.]+", str(value).replace(",", ""))

    return float(match.group()) if match else None


def clean_bedrooms(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    match = re.search(r"\d+", str(value))

    return int(match.group()) if match else None


def clean_property_type(value: Any) -> str | None:
    if not value:
        return None

    text = str(value).lower()

    if "flat" in text or "apartment" in text:
        return "Apartment"

    if "villa" in text:
        return "Villa"

    if "house" in text:
        return "Independent House"

    if "plot" in text or "land" in text:
        return "Plot"

    return str(value).strip().title()


def clean_transaction_type(value: Any) -> str | None:
    if not value:
        return None

    text = str(value).lower()

    if "rent" in text or "lease" in text:
        return "Rent"

    if "sale" in text or "sell" in text:
        return "Sale"

    return str(value).strip().title()


def calculate_price_per_sqft(
    price: float | None,
    area_sqft: float | None,
) -> float | None:

    if price is None or area_sqft is None or area_sqft <= 0:
        return None

    return round(price / area_sqft, 2)


def clean_integer(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    match = re.search(r"\d+", str(value))

    return int(match.group()) if match else None