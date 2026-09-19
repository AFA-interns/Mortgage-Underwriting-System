from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class PropertyIntake(BaseModel):
    address: str = Field(..., description="Full address of the property")
    locality: str = Field(..., description="Locality or neighborhood")
    city: str = Field(..., description="City name")
    property_type: str = Field(..., description="E.g., Apartment, Independent House")
    bhk: int = Field(..., description="Number of bedrooms")
    area_sqft: float = Field(..., description="Area in square feet")
    area_type: str = Field("carpet_area", description="carpet_area, built_up_area, super_built_up_area")
    age_years: int = Field(0, description="Age of the property in years")


class Comparable(BaseModel):
    id: int
    locality: str
    city: str
    property_type: str
    bhk: int
    area_sqft: float
    area_type: str
    age_years: int
    price_inr: float
    price_per_sqft: float


class ValuationRange(BaseModel):
    low: float
    high: float


class ValuationResponse(BaseModel):
    estimated_market_value_inr: float
    valuation_range_inr: ValuationRange
    price_per_sqft_inr: float
    measurement_basis: str
    comparable_count: int
    comparables: List[Dict[str, Any]]
    confidence_score: float
    confidence_label: str
    risk_flags: List[str]
    human_review_required: bool
    method: List[str]
    sources: List[str]
    explanation: str
