import sys
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def run_test():
    payload = {
        "address": "100 Feet Road",
        "locality": "Indiranagar",
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
