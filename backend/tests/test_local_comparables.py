"""Local comparables database (app.services.property_db) and the
valuation tool built on it (app.tools.local_comparables) - a second
valuation source alongside live AVnester, populated by scraping public
listing sites (property_data/, scripts/ingest_squareyards.py)."""
import os
from unittest.mock import patch

import pytest

from app.services import property_db
from app.tools.local_comparables import fetch_local_valuation
from property_data.cleaners.property_cleaner import (
    calculate_price_per_sqft, clean_area, clean_bedrooms, clean_price,
    clean_property_type, clean_transaction_type,
)


# ---------------------------------------------------------- property_db

def test_find_comparables_with_no_database_returns_empty():
    assert property_db.find_comparables("Mumbai") == []


def test_save_listings_with_no_database_is_a_safe_no_op():
    assert property_db.save_listings([{"city": "Mumbai"}]) == {"inserted": 0, "duplicates": 0}


# ------------------------------------------------------- local_comparables

def _row(price, area, locality="Andheri West", city="Mumbai", bhk=2, source_url=None):
    return {
        "source": "square_yards", "source_url": source_url, "city": city, "locality": locality,
        "property_type": "Apartment", "transaction_type": "Sale", "bedrooms": bhk, "area_sqft": area,
        "price": price, "price_per_sqft": price / area,
    }


def test_fetch_local_valuation_with_no_database_returns_empty_shape():
    out = fetch_local_valuation("Andheri West", "Mumbai", 2, 1000)
    assert out["estimated_market_value_inr"] == 0
    assert out["comparables"] == []
    assert out["scope"] is None


def test_fetch_local_valuation_uses_median_price_per_sqft():
    rows = [_row(p, 1000) for p in (9_000_000, 9_500_000, 20_000_000)]  # median -> 9.5M / 1000 = 9500/sqft
    with patch("app.tools.local_comparables.find_comparables", return_value=rows):
        out = fetch_local_valuation("Andheri West", "Mumbai", 2, 1000)
    assert out["scope"] == "locality"
    assert out["price_per_sqft_inr"] == 9500
    assert out["estimated_market_value_inr"] == 9500 * 1000
    assert len(out["comparables"]) == 3


def test_fetch_local_valuation_widens_to_city_when_locality_is_thin():
    calls = []

    def fake(city, locality=None, bedrooms=None):
        calls.append(locality)
        if locality:
            return [_row(9_000_000, 1000)]  # only 1 - below the 3-comp minimum
        return [_row(p, 1000) for p in (8_000_000, 9_000_000, 10_000_000)]

    with patch("app.tools.local_comparables.find_comparables", side_effect=fake):
        out = fetch_local_valuation("Andheri West", "Mumbai", 2, 1000)
    assert calls == ["Andheri West", None]
    assert out["scope"] == "city"
    assert len(out["comparables"]) == 3


def test_fetch_local_valuation_drops_listings_without_usable_price_or_area():
    rows = [_row(9_000_000, 1000), {"price": None, "area_sqft": None, "price_per_sqft": None, "city": "Mumbai"}]
    with patch("app.tools.local_comparables.find_comparables", return_value=rows):
        out = fetch_local_valuation("Andheri West", "Mumbai", 2, 1000)
    assert len(out["comparables"]) == 1


# ---------------------------------------------------------- property_cleaner

@pytest.mark.parametrize("raw,expected", [
    ("₹65 Lakh", 6_500_000.0), ("1.2 Cr", 12_000_000.0), ("Rs. 50,00,000", 5_000_000.0), (7_500_000, 7_500_000.0),
])
def test_clean_price(raw, expected):
    assert clean_price(raw) == expected


def test_clean_price_handles_garbage():
    assert clean_price(None) is None
    assert clean_price("not a price") is None


@pytest.mark.parametrize("raw,expected", [("1200 sq ft", 1200.0), ("1,500", 1500.0), (900, 900.0)])
def test_clean_area(raw, expected):
    assert clean_area(raw) == expected


@pytest.mark.parametrize("raw,expected", [("3 BHK", 3), (2, 2), ("studio", None)])
def test_clean_bedrooms(raw, expected):
    assert clean_bedrooms(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2 BHK Flat", "Apartment"), ("Independent House", "Independent House"),
    ("Villa", "Villa"), ("Residential Plot", "Plot"),
])
def test_clean_property_type(raw, expected):
    assert clean_property_type(raw) == expected


@pytest.mark.parametrize("raw,expected", [("For Sale", "Sale"), ("For Rent", "Rent")])
def test_clean_transaction_type(raw, expected):
    assert clean_transaction_type(raw) == expected


def test_calculate_price_per_sqft():
    assert calculate_price_per_sqft(1_000_000, 1000) == 1000.0
    assert calculate_price_per_sqft(1_000_000, 0) is None
    assert calculate_price_per_sqft(None, 1000) is None


# --------------------------------------------- end-to-end valuation fallback

def test_property_valuation_node_falls_back_to_local_db_when_avnester_is_empty():
    """The full pipeline's property agent: AVnester has nothing, the local
    comparables database does - the final estimate must come from the
    local database, not silently stay at zero."""
    from app.graph.nodes.property_valuation import property_valuation_node

    state = {
        "doc_ingestion_output": {"property_profile": {
            "city": "Mumbai", "locality": "Andheri West", "property_type": "Apartment",
            "carpet_area_sqft": 1000,
        }},
        "borrower_profile": {"bhk": 2},
        "errors": [],
    }
    local_rows = [_row(p, 1000) for p in (9_000_000, 9_500_000, 10_000_000)]
    with patch("app.tools.external_api.search_properties", return_value={"listings": []}), \
         patch("app.tools.local_comparables.find_comparables", return_value=local_rows):
        result = property_valuation_node(state)

    analysis = result["property_analysis"]
    assert analysis["estimated_value"] > 0
    assert any(e["source"] == "local_db" for e in analysis["evidence"])
    assert "local median fallback" in " ".join(analysis["flags"]).lower()


def test_property_valuation_node_zero_when_both_sources_empty():
    from app.graph.nodes.property_valuation import property_valuation_node

    state = {
        "doc_ingestion_output": {"property_profile": {
            "city": "Mumbai", "locality": "Nowhere", "property_type": "Apartment", "carpet_area_sqft": 1000,
        }},
        "borrower_profile": {"bhk": 2},
        "errors": [],
    }
    with patch("app.tools.external_api.search_properties", return_value={"listings": []}), \
         patch("app.tools.local_comparables.find_comparables", return_value=[]):
        result = property_valuation_node(state)

    assert result["property_analysis"]["estimated_value"] == 0


def test_avnester_scope_message_surfaced_as_risk_flag():
    """AVnester explains unsupported locations (e.g. "only covers Tamil
    Nadu") - that explanation must reach the UI instead of a bare zero."""
    from app.graph.nodes.property_valuation import property_valuation_node

    state = {
        "doc_ingestion_output": {"property_profile": {
            "city": "Mumbai", "locality": "Andheri West", "property_type": "Apartment", "carpet_area_sqft": 1000,
        }},
        "borrower_profile": {"bhk": 2},
        "errors": [],
    }
    unsupported_response = {
        "listings": [], "supported": False,
        "scopeMessage": "AVnester property listings cover Tamil Nadu only.",
    }
    with patch("app.tools.external_api.search_properties", return_value=unsupported_response), \
         patch("app.tools.local_comparables.find_comparables", return_value=[]):
        result = property_valuation_node(state)

    assert "AVnester property listings cover Tamil Nadu only." in result["property_analysis"]["flags"]


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to run against PostgreSQL")
def test_postgres_save_and_find_round_trip():
    import importlib

    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    importlib.reload(property_db)
    try:
        listings = [_row(9_000_000 + i * 10_000, 1000, source_url=f"https://example.com/t{i}") for i in range(3)]
        first = property_db.save_listings(listings)
        assert first == {"inserted": 3, "duplicates": 0}
        second = property_db.save_listings(listings)
        assert second == {"inserted": 0, "duplicates": 3}
        found = property_db.find_comparables("Mumbai", "Andheri West", 2)
        assert len(found) == 3
    finally:
        from sqlalchemy import create_engine, text

        from app.services.db import normalise_url

        engine = create_engine(normalise_url(os.environ["DATABASE_URL"]))
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM property_listings WHERE source_url LIKE 'https://example.com/t%'"))
        os.environ["DATABASE_URL"] = ""
        importlib.reload(property_db)
