"""
SQLAlchemy ORM Models
Exact mapping of existing SQLite database schema (server/db/schema.sql).
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # 'jewelry', 'restaurant', 'healthcare'
    location = Column(String, nullable=False)
    currency = Column(String, nullable=False)  # 'QAR', 'EGP', 'USD', etc.
    whatsapp_number = Column(String, nullable=False)
    operating_hours = Column(String, nullable=False)
    policy_summary = Column(String, nullable=False)
    integration_mode = Column(String, default="demo")
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    inventory_items = relationship("Inventory", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_base = relationship("KnowledgeBase", back_populates="tenant", cascade="all, delete-orphan")
    booking_slots = relationship("BookingSlot", back_populates="tenant", cascade="all, delete-orphan")
    sessions = relationship("SessionModel", back_populates="tenant", cascade="all, delete-orphan")
    order_drafts = relationship("OrderDraft", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")
    bi_events = relationship("BIEvent", back_populates="tenant", cascade="all, delete-orphan")
    handoff_requests = relationship("HandoffRequest", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String, nullable=False)
    name = Column(String, nullable=False)
    name_ar = Column(String, nullable=True)
    category = Column(String, nullable=False)
    base_price = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    description = Column(String, nullable=False)
    description_ar = Column(String, nullable=True)
    attributes_json = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")


class Inventory(Base):
    __tablename__ = "inventory"

    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_count = Column(Integer, nullable=False, default=0)
    reserved_count = Column(Integer, nullable=False, default=0)
    location = Column(String, nullable=False)
    low_stock_threshold = Column(Integer, default=1)
    last_verified_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    product = relationship("Product", back_populates="inventory")
    tenant = relationship("Tenant", back_populates="inventory_items")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)
    question = Column(String, nullable=False)
    question_ar = Column(String, nullable=True)
    answer = Column(String, nullable=False)
    answer_ar = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="knowledge_base")


class BookingSlot(Base):
    __tablename__ = "booking_slots"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_date = Column(String, nullable=False)  # 'YYYY-MM-DD'
    slot_time = Column(String, nullable=False)  # 'HH:MM'
    service_type = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False, default=1)
    booked_count = Column(Integer, nullable=False, default=0)
    status = Column(String, default="available")

    # Relationships
    tenant = relationship("Tenant", back_populates="booking_slots")


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)
    language = Column(String, default="en")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    order_drafts = relationship("OrderDraft", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    sender = Column(String, nullable=False)  # 'user', 'ai', 'system'
    content = Column(Text, nullable=False)
    tool_calls_json = Column(Text, nullable=True)
    grounding_info = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    session = relationship("SessionModel", back_populates="messages")


class OrderDraft(Base):
    __tablename__ = "order_drafts"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="draft")
    draft_type = Column(String, nullable=False)
    items_json = Column(Text, nullable=False)
    subtotal = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    deposit_required = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    customer_notes = Column(Text, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=True)
    external_reference = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp())
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("SessionModel", back_populates="order_drafts")
    tenant = relationship("Tenant", back_populates="order_drafts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    details_json = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="audit_logs")


class BIEvent(Base):
    __tablename__ = "bi_events"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    sku = Column(String, nullable=True)
    draft_id = Column(String, ForeignKey("order_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    outcome = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    is_demo = Column(Integer, default=1)
    schema_version = Column(String, default="1.0")
    idempotency_key = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="bi_events")


class HandoffRequest(Base):
    __tablename__ = "handoff_requests"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="link_prepared")  # 'requested', 'link_prepared', 'waiting_for_customer', 'closed'
    reason = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    draft_id = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=False)
    whatsapp_url = Column(Text, nullable=False)
    escalation_trigger = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="handoff_requests")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="staff")  # 'admin', 'manager', 'staff', 'customer', 'read_only'
    permissions_json = Column(Text, nullable=True)  # JSON-serialized list of custom permissions or null for role defaults
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    # Relationships
    tenant = relationship("Tenant", back_populates="users")


class RevokedToken(Base):
    """
    Sprint 5.5: Cryptographic token revocation & replay attack defense.
    Stores revoked JWT IDs (jti) from logouts and rotated refresh tokens.
    """
    __tablename__ = "revoked_tokens"

    id = Column(String, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    token_type = Column(String, nullable=False)  # 'access' or 'refresh'
    user_id = Column(String, nullable=True, index=True)
    reason = Column(String, nullable=True)  # 'logout', 'token_rotated', 'security_revocation'
    revoked_at = Column(DateTime, server_default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=True)
