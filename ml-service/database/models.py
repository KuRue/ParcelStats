from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.connection import Base
from services.timeutil import utcnow


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    google_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    avatar_url = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Carrier(Base):
    __tablename__ = "carriers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    country = Column(String)
    api_available = Column(Boolean, default=False)
    scrape_available = Column(Boolean, default=False)
    base_url = Column(String)
    tracking_url_template = Column(String)
    created_at = Column(DateTime, default=utcnow)


class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(String, primary_key=True)
    tracking_number = Column(String, nullable=False)
    carrier_id = Column(String, ForeignKey("carriers.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="pending")
    service_type = Column(String)
    weight_kg = Column(Numeric(8, 3))
    origin_lat = Column(Numeric(9, 6))
    origin_lng = Column(Numeric(9, 6))
    origin_name = Column(String)
    dest_lat = Column(Numeric(9, 6))
    dest_lng = Column(Numeric(9, 6))
    dest_name = Column(String)
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    estimated_delivery = Column(DateTime)
    source = Column(String, default="user")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    carrier = relationship("Carrier")
    events = relationship("ShipmentEvent", back_populates="shipment", order_by="desc(ShipmentEvent.event_time)")
    predictions_list = relationship("Prediction", back_populates="shipment")


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"
    id = Column(String, primary_key=True)
    shipment_id = Column(String, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False)
    location_lat = Column(Numeric(9, 6))
    location_lng = Column(Numeric(9, 6))
    location_name = Column(String)
    description = Column(String)
    raw_data = Column(JSON)
    event_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    shipment = relationship("Shipment", back_populates="events")


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(String, primary_key=True)
    shipment_id = Column(String, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    predicted_delivery = Column(DateTime, nullable=False)
    confidence_low = Column(DateTime)
    confidence_high = Column(DateTime)
    confidence_pct = Column(Numeric(5, 2))
    model_version = Column(String, nullable=False)
    features = Column(JSON)
    created_at = Column(DateTime, default=utcnow)
    shipment = relationship("Shipment", back_populates="predictions_list")


class CarrierRoute(Base):
    __tablename__ = "carrier_routes"
    id = Column(String, primary_key=True)
    carrier_id = Column(String, ForeignKey("carriers.id"), nullable=False)
    origin_region = Column(String, nullable=False)
    dest_region = Column(String, nullable=False)
    service_type = Column(String)
    avg_days = Column(Numeric(6, 2))
    median_days = Column(Numeric(6, 2))
    p10_days = Column(Numeric(6, 2))
    p90_days = Column(Numeric(6, 2))
    sample_count = Column(Integer, default=0)
    route_hops = Column(JSON)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"
    id = Column(String, primary_key=True)
    shipment_id = Column(String, ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True)
    carrier_id = Column(String, ForeignKey("carriers.id"), nullable=False)
    tracking_number = Column(String, nullable=False)
    status = Column(String, default="pending")
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    next_attempt_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True)
    model_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    metrics = Column(JSON)
    trained_at = Column(DateTime, default=utcnow)
    is_active = Column(Boolean, default=False)
