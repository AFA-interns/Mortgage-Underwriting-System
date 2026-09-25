"""Runs the FULL pipeline on the four bundled mock-document scenarios and
prints a readable result for each.

    cd backend
    .\\venv\\Scripts\\python.exe smoke_test_pipeline.py

Uses the same borrower profiles and synthetic credit-bureau data as the UI's
demo scenarios (app/services/applications.py), so the results match what you
see in the browser. Writes nothing to the database.
"""
import os
import sys

os.environ["DATABASE_URL"] = ""  # this script must not touch PostgreSQL

from app.graph.workflow import build_underwriting_graph  # noqa: E402
from app.services.applications import DEMO_SCENARIOS  # noqa: E402
from tests.mock_data.generate_docs import generate_all_mock_scenarios  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # so rupee signs print on Windows

EXPECTED = {
    "clean": "APPROVE",
    "name_mismatch": "SUSPEND",
    "salary_mismatch": "SUSPEND",
    "missing_docs": "SUSPEND",
}


def inr(value) -> str:
    return f"Rs {value:,.0f}" if isinstance(value, (int, float)) and value > 0 else "n/a"


def main() -> int:
    print("Generating mock documents for all 4 scenarios...")
    docs = generate_all_mock_scenarios()
    graph = build_underwriting_graph().compile()
    failures = 0

    for sid, scenario in DEMO_SCENARIOS.items():
        paths = docs[scenario["key"]]
        state = {
            "application_id": f"SMOKE-{sid.upper()}",
            "raw_document_paths": paths,
            "borrower_profile": dict(scenario["profile"]),
            "credit_bureau_data": scenario["bureau"],
            "errors": [],
        }
        result = graph.invoke(state)

        dec = result.get("decision", {})
        credit = result.get("credit_analysis", {})
        prop = result.get("property_analysis", {})
        comp = result.get("compliance_analysis", {})
        doc = result.get("document_analysis", {})

        got = dec.get("decision")
        ok = got == EXPECTED[sid]
        failures += 0 if ok else 1

        print(f"\n=== {scenario['label']}  ({sid}) ===")
        print(f"  Documents      : {len(paths)} PDFs, missing = {doc.get('missing_documents') or 'none'}")
        print(f"  Credit         : CIBIL {credit.get('cibil_score')}  FOIR {credit.get('foir')}  LTV {credit.get('ltv')}")
        print(f"  Property       : {inr(prop.get('estimated_value'))}  (confidence {prop.get('valuation_confidence')})")
        print(f"  Compliance     : critical flags = {comp.get('critical_flags') or 'none'}")
        print(f"  DECISION       : {got}   risk {dec.get('risk_score')}   confidence {dec.get('confidence')}")
        print(f"  Rationale      : {dec.get('rationale')}")
        print(f"  Expected {EXPECTED[sid]}: {'OK' if ok else 'MISMATCH'}")

    print("\n=== SMOKE TEST", "PASSED" if failures == 0 else f"FAILED ({failures} mismatch)", "===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
