def estimate_value(
    comparables,
    target_area_sqft: float,
):
    if not comparables:
        return None

    prices_per_sqft = [
        p.price_per_sqft
        for p in comparables
        if p.price_per_sqft is not None
    ]

    if not prices_per_sqft:
        return None

    average_price_per_sqft = (
        sum(prices_per_sqft) / len(prices_per_sqft)
    )

    estimated_value = (
        average_price_per_sqft * target_area_sqft
    )

    return {
        "average_price_per_sqft": round(
            average_price_per_sqft, 2
        ),
        "estimated_value": round(
            estimated_value, 2
        ),
        "comparables_used": len(prices_per_sqft),
    }