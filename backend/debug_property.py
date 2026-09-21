import sys
import os
import json
sys.path.insert(0, r'C:\Users\LAKSHYA VARSHNEY\OneDrive\Documents\My-code\Mortgage-Underwriting-System\backend')

from app.graph.workflow import build_underwriting_graph
from tests.mock_data.generate_docs import generate_all_mock_scenarios

graph = build_underwriting_graph()
app = graph.compile()

# Only test clean_prime
scenarios = generate_all_mock_scenarios()
clean_paths = scenarios["clean_prime"]

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
}

borrower = SCENARIO_PROFILES["clean_prime"]

initial_state = {
    'application_id': 'APP-DEBUG-CLEAN',
    'borrower_id': 'BORR-DEBUG',
    'raw_document_paths': clean_paths,
    'borrower_profile': borrower,
    'document_analysis': {},
    'credit_analysis': {},
    'property_analysis': {},
    'compliance_analysis': {},
    'errors': [],
}

# Run step by step to debug
from app.document_ingestion.agent import document_ingestion_node
from app.graph.nodes.doc_ingestion_to_analysis import doc_ingestion_to_analysis_node
from app.graph.nodes.property_valuation import property_valuation_node

print("=== STEP 1: Document Ingestion ===")
state1 = document_ingestion_node(initial_state)
print("doc_ingestion_output keys:", list(state1.get('doc_ingestion_output', {}).keys()))
prop_profile = state1.get('doc_ingestion_output', {}).get('property_profile')
print("property_profile:", prop_profile)

print("\n=== STEP 2: Transform ===")
state2 = doc_ingestion_to_analysis_node(state1)
print("document_analysis keys:", list(state2.get('document_analysis', {}).keys()))

print("\n=== STEP 3: Property Valuation ===")
state3 = property_valuation_node(state2)
print("property_analysis:", json.dumps(state3.get('property_analysis', {}), indent=2, default=str))
print("errors:", state3.get('errors', []))