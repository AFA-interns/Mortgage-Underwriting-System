import sys
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_evaluate_endpoint_reports_local_db_as_value_source_on_avnester_fallback():
    """Regression test: app.graph.property_state.AgentState is a TypedDict,
    and LangGraph only persists state keys declared in that schema. A node
    returning "value_source" that wasn't declared there was silently
    dropped on merge, so /api/v1/valuation/evaluate always reported
    "avnester" even when reconcile_node had fallen back to the local
    comparables database."""
    local_rows = [
        {
            "source": "square_yards", "source_url": f"https://example.com/reg{i}",
            "city": "Mumbai", "locality": "Andheri West", "property_type": "Apartment",
            "transaction_type": "Sale", "bedrooms": 2, "area_sqft": 1000.0,
            "price": 9_000_000 + i * 100_000, "price_per_sqft": (9_000_000 + i * 100_000) / 1000,
        }
        for i in range(3)
    ]
    payload = {
        "address": "x", "locality": "Andheri West", "city": "Mumbai", "property_type": "Apartment",
        "bhk": 2, "area_sqft": 1000, "area_type": "carpet_area", "age_years": 0,
    }

    with patch("app.tools.external_api.search_properties", return_value={"listings": []}), \
         patch("app.tools.local_comparables.find_comparables", return_value=local_rows):
        response = client.post("/api/v1/valuation/evaluate", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["value_source"] == "local_db"
    assert body["sources"] == ["Nominatim Geocoder", "Local comparables database"]
    assert body["method"] == ["comparable_sales", "local_db"]
    assert body["estimated_market_value_inr"] > 0


def run_test():
    payload = {
        "address": "Whitefield Main Road",
        "locality": "Whitefield",
        "city": "Bangalore",
        "property_type": "Apartment",
        "bhk": 2,
        "area_sqft": 1200,
        "area_type": "carpet_area",
        "age_years": 5,
    }

    print("--- POST /api/v1/valuation/evaluate ---")
    response = client.post("/api/v1/valuation/evaluate", json=payload)
    data = response.json()
    print(json.dumps(data, indent=2))

    if data.get("status") == "PENDING_HUMAN_REVIEW":
        thread_id = data.get("thread_id")
        print(f"\n--- Thread {thread_id} paused for Human Review. Resuming... ---")

        resume_payload = {"approved": True, "notes": "Approved by testing script."}
        print(f"\n--- POST /api/v1/valuation/{thread_id}/resume ---")
        resume_resp = client.post(f"/api/v1/valuation/{thread_id}/resume", json=resume_payload)
        print(json.dumps(resume_resp.json(), indent=2))


if __name__ == "__main__":
    run_test()
