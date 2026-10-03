from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class PropertyListingDB(Base):
    __tablename__ = "property_listings"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(100), nullable=False)
    source_url = Column(Text)

    state = Column(String(100))
    city = Column(String(100), nullable=False)
    locality = Column(String(200))
    pincode = Column(String(20))

    property_type = Column(String(100))
    transaction_type = Column(String(50))

    bedrooms = Column(Integer)
    bathrooms = Column(Integer)

    area_sqft = Column(Float)
    price = Column(Float)
    price_per_sqft = Column(Float)

    furnishing = Column(String(100))
    floor = Column(Integer)
    total_floors = Column(Integer)

    property_age = Column(Integer)
    parking = Column(Integer)

    listing_date = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)