import time
import random

def fetch_api_valuation(locality: str, city: str, property_type: str, bhk: int, area_sqft: float) -> dict:
    """
    Simulates fetching a valuation from an external API (like Zapkey or Propstack).
    In a real scenario, this would make an HTTP request.
    """
    # Simulate network delay
    time.sleep(1.5)
    
    # Base rates per locality (mock logic)
    base_rates = {
        "indiranagar": 12800,
        "koramangala": 12500,
        "whitefield": 9200,
        "jayanagar": 19000,
        "bandra west": 42000,
        "andheri east": 21000
    }
    
    key = locality.lower().strip()
    rate = base_rates.get(key, 5000) # Default to 5000 if unknown
    
    # Add some randomness to simulate real-world API variance (+/- 3%)
    rate_variance = rate * random.uniform(0.97, 1.03)
    
    estimated_value = rate_variance * area_sqft
    
    return {
        "api_name": "Mock Zapkey AVM",
        "estimated_market_value_inr": estimated_value,
        "price_per_sqft_inr": rate_variance,
        "valuation_range_inr": {
            "low": estimated_value * 0.90,
            "high": estimated_value * 1.10
        },
        "api_confidence_score": 0.85 if key in base_rates else 0.40,
        "measurement_basis": "carpet_area" if property_type.lower() == "apartment" else "built_up_area"
    }
