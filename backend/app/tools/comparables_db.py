import pandas as pd
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'dummy_properties.csv')


def get_comparables(locality: str, city: str, property_type: str, bhk: int, area_sqft: float) -> list[dict]:
    if not os.path.exists(CSV_PATH):
        return []

    df = pd.read_csv(CSV_PATH)

    df['locality_clean'] = df['locality'].str.lower().str.strip()
    df['city_clean'] = df['city'].str.lower().str.strip()
    df['property_type_clean'] = df['property_type'].str.lower().str.strip()

    t_locality = locality.lower().strip()
    t_city = city.lower().strip()
    t_prop_type = property_type.lower().strip()

    mask = (
        (df['city_clean'] == t_city) &
        (df['locality_clean'] == t_locality) &
        (df['property_type_clean'] == t_prop_type)
    )
    filtered = df[mask]

    if filtered.empty:
        return []

    min_area = area_sqft * 0.8
    max_area = area_sqft * 1.2
    filtered = filtered[(filtered['area_sqft'] >= min_area) & (filtered['area_sqft'] <= max_area)]

    filtered = filtered.drop(columns=['locality_clean', 'city_clean', 'property_type_clean'])

    return filtered.to_dict(orient='records')
