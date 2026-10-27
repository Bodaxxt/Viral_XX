"""
Pytest Test Fixtures and Disposable Database Setup
Sprint 5: Added User model seeding, JWT token factories, and auth client fixtures.
"""

import os
import json
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import Base, get_db
from backend.app.db.models import Tenant, Product, Inventory, BookingSlot, User
from backend.app.core.auth import hash_password, create_access_token
from backend.app.schemas.auth import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS, Permissions
from backend.app.core.config import settings

# Use an in-memory SQLite database for isolated, fast, non-mutating tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine, "connect")
def configure_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Creates all tables in the disposable in-memory database and populates demo fixtures.
    """
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Seed sample tenants
    t1 = Tenant(
        id="al-noor-jewelry",
        name="Al Noor High Jewelry & Diamonds",
        category="jewelry",
        location="Place Vendôme, Doha, Qatar",
        currency="QAR",
        whatsapp_number="+97444991200",
        operating_hours="Sat-Thu 10AM-10PM",
        policy_summary="International GIA certificates. Returns within 7 days.",
        integration_mode="demo",
    )
    t2 = Tenant(
        id="saffron-table",
        name="The Saffron Table Fine Dining",
        category="restaurant",
        location="Zamalek, Cairo, Egypt",
        currency="EGP",
        whatsapp_number="+201098539907",
        operating_hours="Tue-Sun 6PM-12AM",
        policy_summary="Advance booking required. 500 EGP deposit per guest.",
        integration_mode="demo",
    )
    t3 = Tenant(
        id="vitalis-health",
        name="Vitalis Longevity & Clinical Center",
        category="healthcare",
        location="New Cairo, Egypt",
        currency="EGP",
        whatsapp_number="+201200554488",
        operating_hours="Sat-Thu 9AM-7PM",
        policy_summary="Preventive longevity and clinical wellness guidance.",
        integration_mode="demo",
    )
    db.add_all([t1, t2, t3])
    db.commit()

    # Seed sample products
    p1 = Product(
        id="J-101",
        tenant_id="al-noor-jewelry",
        sku="SKU-EM-101",
        name="Al-Thuraya Diamond & Emerald Collar",
        name_ar="طوق الثريا من الألماس والزمرد",
        category="Necklaces",
        base_price=42000.0,
        currency="QAR",
        description="Handcrafted collar necklace set in 18K white gold with 4.5 carats of emeralds.",
        attributes_json=json.dumps({"metal": "18K White Gold", "carat": 4.5}),
        is_active=1,
    )
    p2 = Product(
        id="J-102",
        tenant_id="al-noor-jewelry",
        sku="SKU-SAP-102",
        name="Noor Pavé Sapphire Bangle",
        name_ar="سوار نور المرصع بياقوت السفير",
        category="Bracelets",
        base_price=14500.0,
        currency="QAR",
        description="Slim hinged oval bangle in 18K white gold with royal blue Ceylon sapphires.",
        attributes_json=json.dumps({"metal": "18K White Gold", "gemstone": "Sapphire"}),
        is_active=1,
    )
    p3 = Product(
        id="R-201",
        tenant_id="saffron-table",
        sku="SKU-DEG-201",
        name="Chef's Grand 7-Course Degustation",
        name_ar="قائمة تذوق الشيف الفاخرة (7 أطباق)",
        category="Degustation",
        base_price=1850.0,
        currency="EGP",
        description="Signature multi-course tasting experience featuring modern Egyptian culinary artistry.",
        attributes_json=json.dumps({"courses": 7, "deposit_required": 500}),
        is_active=1,
    )
    db.add_all([p1, p2, p3])
    db.commit()

    # Seed sample inventory
    inv1 = Inventory(
        product_id="J-101",
        tenant_id="al-noor-jewelry",
        stock_count=2,
        reserved_count=0,
        location="Place Vendôme Salon Vault",
        low_stock_threshold=1,
    )
    inv2 = Inventory(
        product_id="J-102",
        tenant_id="al-noor-jewelry",
        stock_count=1,
        reserved_count=1,  # 0 available
        location="Place Vendôme Salon Vault",
        low_stock_threshold=1,
    )
    inv3 = Inventory(
        product_id="R-201",
        tenant_id="saffron-table",
        stock_count=20,
        reserved_count=4,  # 16 available
        location="Main Dining Room",
        low_stock_threshold=5,
    )
    db.add_all([inv1, inv2, inv3])

    # Seed sample booking slots
    s1 = BookingSlot(id="SLOT-R01", tenant_id="saffron-table", slot_date="2026-10-26", slot_time="19:30", service_type="Chef Tasting Degustation", capacity=10, booked_count=4, status="available")
    s2 = BookingSlot(id="SLOT-R02", tenant_id="saffron-table", slot_date="2026-10-26", slot_time="21:30", service_type="Chef Tasting Degustation", capacity=10, booked_count=2, status="available")
    s3 = BookingSlot(id="SLOT-R03", tenant_id="saffron-table", slot_date="2026-10-27", slot_time="19:30", service_type="Chef Tasting Degustation", capacity=10, booked_count=8, status="available")
    s4 = BookingSlot(id="SLOT-R04", tenant_id="saffron-table", slot_date="2026-10-27", slot_time="21:30", service_type="Chef Tasting Degustation", capacity=10, booked_count=10, status="booked")
    s5 = BookingSlot(id="SLOT-H01", tenant_id="vitalis-health", slot_date="2026-10-26", slot_time="09:30", service_type="Executive Longevity Screening", capacity=2, booked_count=0, status="available")
    s6 = BookingSlot(id="SLOT-H02", tenant_id="vitalis-health", slot_date="2026-10-26", slot_time="11:00", service_type="Executive Longevity Screening", capacity=2, booked_count=1, status="available")
    s7 = BookingSlot(id="SLOT-H03", tenant_id="vitalis-health", slot_date="2026-10-27", slot_time="10:00", service_type="Cardio-Vascular Assessment", capacity=2, booked_count=0, status="available")
    db.add_all([s1, s2, s3, s4, s5, s6, s7])

    # Seed test users for Sprint 5 auth tests
    u_admin = User(
        id="user-admin-1",
        tenant_id="al-noor-jewelry",
        username="admin_user",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        permissions_json=None,  # Uses role defaults
        is_active=1,
    )
    u_staff = User(
        id="user-staff-1",
        tenant_id="al-noor-jewelry",
        username="staff_user",
        hashed_password=hash_password("StaffPass123!"),
        role="staff",
        permissions_json=None,
        is_active=1,
    )
    u_saffron = User(
        id="user-saffron-1",
        tenant_id="saffron-table",
        username="saffron_admin",
        hashed_password=hash_password("SaffronPass123!"),
        role="admin",
        permissions_json=None,
        is_active=1,
    )
    u_readonly = User(
        id="user-readonly-1",
        tenant_id="al-noor-jewelry",
        username="readonly_user",
        hashed_password=hash_password("ReadOnlyPass123!"),
        role="read_only",
        permissions_json=None,
        is_active=1,
    )
    u_cust1 = User(
        id="cust-user-1",
        tenant_id="al-noor-jewelry",
        username="customer_one",
        hashed_password=hash_password("CustPass123!"),
        role="customer",
        permissions_json=None,
        is_active=1,
    )
    u_cust2 = User(
        id="cust-user-2",
        tenant_id="al-noor-jewelry",
        username="customer_two",
        hashed_password=hash_password("CustPass123!"),
        role="customer",
        permissions_json=None,
        is_active=1,
    )
    u_inactive = User(
        id="user-inactive-1",
        tenant_id="al-noor-jewelry",
        username="inactive_user",
        hashed_password=hash_password("InactivePass123!"),
        role="staff",
        permissions_json=None,
        is_active=0,
    )
    db.add_all([u_admin, u_staff, u_saffron, u_readonly, u_cust1, u_cust2, u_inactive])
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """
    Yields an isolated transaction-rolled-back DB session per test.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """
    FastAPI TestClient with overridden get_db dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────
# Sprint 5: Authentication Token Factories & Helpers
# ─────────────────────────────────────────────────────────────

def make_access_token(
    user_id: str = "user-admin-1",
    username: str = "admin_user",
    tenant_id: str = "al-noor-jewelry",
    role: str = "admin",
    permissions=None,
    issuer: str = None,
    audience: str = None,
    secret_key: str = None,
) -> str:
    """Factory for creating test JWT access tokens."""
    perms = permissions if permissions is not None else DEFAULT_ROLE_PERMISSIONS.get(role, [])
    return create_access_token(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        role=role,
        permissions=perms,
        issuer=issuer,
        audience=audience,
        secret_key=secret_key,
    )


def auth_headers(
    user_id: str = "user-admin-1",
    username: str = "admin_user",
    tenant_id: str = "al-noor-jewelry",
    role: str = "admin",
    permissions=None,
    secret_key: str = None,
) -> dict:
    """Returns Authorization header dict for test requests."""
    token = make_access_token(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        role=role,
        permissions=permissions,
        secret_key=secret_key,
    )
    return {"Authorization": f"Bearer {token}"}


def dev_headers(tenant_id: str = "al-noor-jewelry") -> dict:
    """Returns legacy X-Tenant-ID dev-only header for backward compat tests."""
    return {"X-Tenant-ID": tenant_id}


@pytest.fixture
def admin_client(db_session):
    """TestClient authenticated as al-noor-jewelry admin user."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.headers.update(auth_headers(tenant_id="al-noor-jewelry", role="admin"))
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def saffron_client(db_session):
    """TestClient authenticated as saffron-table admin user."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.headers.update(auth_headers(
            user_id="user-saffron-1",
            username="saffron_admin",
            tenant_id="saffron-table",
            role="admin",
        ))
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def readonly_client(db_session):
    """TestClient authenticated as read-only al-noor-jewelry user."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.headers.update(auth_headers(
            user_id="user-readonly-1",
            username="readonly_user",
            tenant_id="al-noor-jewelry",
            role="read_only",
            permissions=DEFAULT_ROLE_PERMISSIONS["read_only"],
        ))
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer1_client(db_session):
    """TestClient authenticated as customer_one (cust-user-1)."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.headers.update(auth_headers(
            user_id="cust-user-1",
            username="customer_one",
            tenant_id="al-noor-jewelry",
            role="customer",
            permissions=DEFAULT_ROLE_PERMISSIONS["customer"],
        ))
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer2_client(db_session):
    """TestClient authenticated as customer_two (cust-user-2)."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.headers.update(auth_headers(
            user_id="cust-user-2",
            username="customer_two",
            tenant_id="al-noor-jewelry",
            role="customer",
            permissions=DEFAULT_ROLE_PERMISSIONS["customer"],
        ))
        yield c
    app.dependency_overrides.clear()

