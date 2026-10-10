from sqlalchemy import select

from property_data.database.models import PropertyListingDB


async def save_listing(session, listing: dict):

    property_obj = PropertyListingDB(**listing)

    session.add(property_obj)

    await session.commit()

    await session.refresh(property_obj)

    return property_obj


async def get_listings(
    session,
    city: str,
    locality: str | None = None,
):

    query = select(PropertyListingDB).where(
        PropertyListingDB.city == city
    )

    if locality:
        query = query.where(
            PropertyListingDB.locality == locality
        )

    result = await session.execute(query)

    return result.scalars().all()


async def listing_exists(
    session,
    source_url: str | None,
):

    if not source_url:
        return False

    query = select(PropertyListingDB).where(
        PropertyListingDB.source_url == source_url
    )

    result = await session.execute(query)

    return result.scalar_one_or_none() is not None


async def find_comparables(
    session,
    city: str,
    locality: str,
    bedrooms: int | None = None,
):

    query = select(PropertyListingDB).where(
        PropertyListingDB.city == city,
        PropertyListingDB.locality == locality,
        PropertyListingDB.transaction_type == "Sale",
    )

    if bedrooms is not None:
        query = query.where(
            PropertyListingDB.bedrooms == bedrooms
        )

    result = await session.execute(query)

    return result.scalars().all()