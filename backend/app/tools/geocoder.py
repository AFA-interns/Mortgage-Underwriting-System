from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


def geocode_address(address: str, locality: str, city: str) -> dict:
    full_query = f"{address}, {locality}, {city}, India"

    geolocator = Nominatim(user_agent="property_valuation_agent_india")

    try:
        location = geolocator.geocode(full_query, timeout=5)
        if location:
            return {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "formatted_address": location.address
            }

        fallback_query = f"{locality}, {city}, India"
        location_fallback = geolocator.geocode(fallback_query, timeout=5)
        if location_fallback:
            return {
                "latitude": location_fallback.latitude,
                "longitude": location_fallback.longitude,
                "formatted_address": location_fallback.address,
                "note": "Geocoded using locality fallback"
            }

        return {"error": "Geocoding failed to find location"}

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        return {"error": f"Geocoding service error: {str(e)}"}
