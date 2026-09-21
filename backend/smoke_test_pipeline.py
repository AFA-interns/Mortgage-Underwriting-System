import json

from app.graph.workflow import build_underwriting_graph
from tests.mock_data.generate_docs import generate_all_mock_scenarios


# Build and compile the underwriting graph
graph = build_underwriting_graph()
app = graph.compile()


# Borrower profiles matching the mock document generator
SCENARIO_PROFILES = {
    "clean_prime": {
        "name": "Aarav Sharma",
        "age": 32,
        "monthly_income": 120000,
        "employment_type": "Salaried",
        "employer": "Tata Consultancy Services",
        "loan_amount": 5000000,
        "loan_tenure_months": 240,
        "property_value": 7500000,
        "existing_debt": 0,
    },
    "name_discrepancy": {
        "name": "Priya Patel",
        "age": 29,
        "monthly_income": 85000,
        "employment_type": "Salaried",
        "employer": "Apex Retail",
        "loan_amount": 4000000,
        "loan_tenure_months": 240,
        "property_value": 6000000,
        "existing_debt": 5000,
    },
    "salary_discrepancy": {
        "name": "Vikram Malhotra",
        "age": 35,
        "monthly_income": 80000,
        "employment_type": "Salaried",
        "employer": "Infosys",
        "loan_amount": 5000000,
        "loan_tenure_months": 240,
        "property_value": 7500000,
        "existing_debt": 20000,
    },
    "missing_docs": {
        "name": "Rahul Verma",
        "age": 28,
        "monthly_income": 80000,
        "employment_type": "Salaried",
        "employer": "Wipro Limited",
        "loan_amount": 4500000,
        "loan_tenure_months": 240,
        "property_value": 6500000,
        "existing_debt": 10000,
    },
}


print("Generating mock documents for all 4 scenarios...")

scenarios = generate_all_mock_scenarios()

for scenario_name, pdf_paths in scenarios.items():

    print("\n=== {} ===".format(scenario_name))
    print("  PDFs: {} files".format(len(pdf_paths)))

    borrower = SCENARIO_PROFILES.get(scenario_name, {})

    initial_state = {
        "application_id": "APP-SMOKE-{}".format(
            scenario_name.upper()
        ),
        "borrower_id": "BORR-{}".format(
            scenario_name.upper()
        ),
        "raw_document_paths": pdf_paths,
        "borrower_profile": borrower,
        "document_analysis": {},
        "credit_analysis": {},
        "property_analysis": {},
        "compliance_analysis": {},
        "errors": [],
    }

    try:

        result = app.invoke(initial_state)

        decision = result.get("decision", {})

        print(
            "  Decision: {}".format(
                decision.get("decision", "N/A")
            )
        )

        print(
            "  Risk Score: {}".format(
                decision.get("risk_score", "N/A")
            )
        )

        print(
            "  Confidence: {}".format(
                decision.get("confidence", "N/A")
            )
        )

        print(
            "  Human Review: {}".format(
                result.get("human_review_required", "N/A")
            )
        )

        print(
            "  Errors: {}".format(
                len(result.get("errors", []))
            )
        )

        for err in result.get("errors", []):

            msg = str(
                err.get("message", "")
            )[:80]

            print(
                "    - {}: {}".format(
                    err.get("stage", ""),
                    msg,
                )
            )

        # Property valuation output
        property_analysis = result.get(
            "property_analysis",
            {}
        )

        print(
            "  Property Estimated Value: {}".format(
                property_analysis.get(
                    "estimated_value",
                    "N/A",
                )
            )
        )

        print(
            "  Property Price/Sqft: {}".format(
                property_analysis.get(
                    "price_per_sqft",
                    "N/A",
                )
            )
        )

        print(
            "  Property Flags: {}".format(
                property_analysis.get(
                    "flags",
                    [],
                )
            )
        )

        print(
            "  Property Keys: {}".format(
                list(property_analysis.keys())
            )
        )

        print(
            "  Credit Keys: {}".format(
                list(
                    result.get(
                        "credit_analysis",
                        {}
                    ).keys()
                )
            )
        )

        print(
            "  Compliance Keys: {}".format(
                list(
                    result.get(
                        "compliance_analysis",
                        {}
                    ).keys()
                )
            )
        )

    except Exception as e:

        print(
            "  ERROR: {}".format(e)
        )


print("\n=== SMOKE TEST COMPLETED ===")