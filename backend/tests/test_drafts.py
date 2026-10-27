"""
Sprint 3.5 Test Suite: Python Draft Order Lifecycle and Explicit Confirmation Gates
Tests draft creation, retrieval, updates, pricing recalculation, explicit confirmation,
idempotency, cancellation, inventory stock reservation, tenant isolation, and audit logging.
"""

import json
import pytest
from fastapi import status

from backend.app.services.draft_service import (
    DraftService,
    DraftNotFoundError,
    CrossTenantAccessError,
    InvalidStateTransitionError,
    InsufficientStockError,
    ProductNotFoundError,
)
from backend.app.schemas.draft import DraftItemRequest
from backend.app.db.models import OrderDraft, Inventory, AuditLog


# ─────────────────────────────────────────────────────────────
#  1. DRAFT CREATION AND RETRIEVAL
# ─────────────────────────────────────────────────────────────

class TestDraftCreationAndRetrieval:
    def test_create_draft_success(self, db_session):
        service = DraftService(db_session)
        draft = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-session-1",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
            customer_notes="Please include gift box",
        )

        assert draft.id.startswith("DRF-JEW-")
        assert draft.tenant_id == "al-noor-jewelry"
        assert draft.status == "draft"
        assert draft.total_amount == 42000.0
        assert draft.currency == "QAR"
        assert len(draft.items) == 1
        assert draft.items[0].product_id == "J-101"
        assert draft.customer_notes == "Please include gift box"

    def test_retrieve_draft_success(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-session-2",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        retrieved = service.get_draft(
            tenant_id="al-noor-jewelry",
            draft_id=created.id,
        )
        assert retrieved.id == created.id
        assert retrieved.status == "draft"
        assert retrieved.total_amount == 42000.0

    def test_retrieve_nonexistent_draft_raises_404(self, db_session):
        service = DraftService(db_session)
        with pytest.raises(DraftNotFoundError):
            service.get_draft("al-noor-jewelry", "DRF-NONEXISTENT")


# ─────────────────────────────────────────────────────────────
#  2. DRAFT UPDATES AND PERMITTED STATE TRANSITIONS
# ─────────────────────────────────────────────────────────────

class TestDraftUpdatesAndStateTransitions:
    def test_update_draft_items_and_notes(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="saffron-table",
            session_id="test-session-update",
            items=[DraftItemRequest(product_id="R-201", quantity=2)],
        )
        assert created.subtotal == 3700.0

        # Update quantity from 2 to 4
        updated = service.update_draft(
            tenant_id="saffron-table",
            draft_id=created.id,
            items=[DraftItemRequest(product_id="R-201", quantity=4)],
            customer_notes="Window table please",
        )

        assert updated.id == created.id
        assert updated.status == "draft"
        assert updated.subtotal == 7400.0
        assert updated.deposit_required == 2000.0  # 4 * 500 EGP
        assert updated.customer_notes == "Window table please"

    def test_update_confirmed_draft_rejected(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-session-conf-update",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        service.confirm_draft("al-noor-jewelry", created.id)

        # Attempt to modify confirmed draft must fail
        with pytest.raises(InvalidStateTransitionError):
            service.update_draft(
                tenant_id="al-noor-jewelry",
                draft_id=created.id,
                items=[DraftItemRequest(product_id="J-101", quantity=2)],
            )

    def test_update_cancelled_draft_rejected(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-session-cancel-update",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        service.cancel_draft("al-noor-jewelry", created.id)

        with pytest.raises(InvalidStateTransitionError):
            service.update_draft(
                tenant_id="al-noor-jewelry",
                draft_id=created.id,
                items=[DraftItemRequest(product_id="J-101", quantity=2)],
            )


# ─────────────────────────────────────────────────────────────
#  3. SERVER-SIDE PRICING AND RECALCULATION
# ─────────────────────────────────────────────────────────────

class TestPricingEngine:
    def test_promo_discount_code(self, db_session):
        service = DraftService(db_session)
        pricing = service.calculate_price(
            tenant_id="al-noor-jewelry",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
            discount_code="VIRALX10",
        )
        assert pricing["subtotal"] == 42000.0
        assert pricing["discount_amount"] == 4200.0  # 10%
        assert pricing["total_amount"] == 37800.0

    def test_restaurant_vat_and_deposit(self, db_session):
        service = DraftService(db_session)
        pricing = service.calculate_price(
            tenant_id="saffron-table",
            items=[DraftItemRequest(product_id="R-201", quantity=2)],
        )
        subtotal = 3700.0
        tax = round(subtotal * 0.14, 2)  # 518.0
        deposit = 2 * 500.0  # 1000.0
        assert pricing["subtotal"] == subtotal
        assert pricing["tax_amount"] == tax
        assert pricing["deposit_required"] == deposit
        assert pricing["total_amount"] == subtotal + tax

    def test_invalid_product_rejected(self, db_session):
        service = DraftService(db_session)
        with pytest.raises(ProductNotFoundError):
            service.calculate_price(
                tenant_id="al-noor-jewelry",
                items=[DraftItemRequest(product_id="NON-EXISTENT-SKU", quantity=1)],
            )


# ─────────────────────────────────────────────────────────────
#  4. EXPLICIT CONFIRMATION GATE & SAFEGUARDS
# ─────────────────────────────────────────────────────────────

class TestExplicitConfirmationGate:
    def test_draft_creation_does_not_confirm(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-no-auto-confirm",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        assert created.status == "draft"
        assert created.confirmed_at is None
        assert created.external_reference is None

    def test_explicit_confirmation_reserves_inventory(self, db_session):
        service = DraftService(db_session)
        # Check initial inventory for J-101 (stock=2, reserved=0)
        inv_before = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        initial_stock = inv_before.stock_count
        initial_reserved = inv_before.reserved_count

        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-explicit-confirm",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        confirm_res = service.confirm_draft("al-noor-jewelry", created.id)
        assert confirm_res.success is True
        assert confirm_res.already_confirmed is False
        assert confirm_res.external_reference.startswith("CONF-AL-")
        assert confirm_res.draft.status == "confirmed"
        assert confirm_res.draft.confirmed_at is not None

        # Verify inventory was decremented and reserved incremented
        inv_after = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        assert inv_after.stock_count == initial_stock - 1
        assert inv_after.reserved_count == initial_reserved + 1

    def test_revalidation_at_confirmation_detects_out_of_stock(self, db_session):
        service = DraftService(db_session)
        # Create draft for J-101 (quantity=1)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-oos-confirm",
            items=[DraftItemRequest(product_id="J-101", quantity=2)],
        )

        # Simulate inventory dropping before customer confirms
        inv = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        inv.stock_count = 1
        db_session.commit()

        # Confirmation must fail because requested 2 > available 1
        with pytest.raises(InsufficientStockError) as exc_info:
            service.confirm_draft("al-noor-jewelry", created.id)
        assert "out of stock" in str(exc_info.value).lower()

    def test_confirm_cancelled_draft_rejected(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cancel-then-confirm",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        service.cancel_draft("al-noor-jewelry", created.id)

        with pytest.raises(InvalidStateTransitionError):
            service.confirm_draft("al-noor-jewelry", created.id)


# ─────────────────────────────────────────────────────────────
#  5. IDEMPOTENT DUPLICATE REQUESTS
# ─────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_repeated_confirmation_is_idempotent(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-idemp-ses",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        inv_before = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        stock_before = inv_before.stock_count

        # First confirmation
        res1 = service.confirm_draft("al-noor-jewelry", created.id, idempotency_key="KEY-123")
        assert res1.already_confirmed is False
        ext_ref = res1.external_reference

        # Second confirmation (duplicate)
        res2 = service.confirm_draft("al-noor-jewelry", created.id, idempotency_key="KEY-123")
        assert res2.success is True
        assert res2.already_confirmed is True
        assert res2.external_reference == ext_ref

        # Inventory must NOT be decremented twice
        inv_after = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        assert inv_after.stock_count == stock_before - 1


# ─────────────────────────────────────────────────────────────
#  6. CANCELLATION BEHAVIOR & INVENTORY REVERSION
# ─────────────────────────────────────────────────────────────

class TestCancellationBehavior:
    def test_cancel_unconfirmed_draft(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cancel-unconf",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        res = service.cancel_draft("al-noor-jewelry", created.id)
        assert res.success is True
        assert res.draft.status == "cancelled"

    def test_cancel_confirmed_draft_restores_inventory(self, db_session):
        service = DraftService(db_session)
        inv = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        orig_stock = inv.stock_count
        orig_reserved = inv.reserved_count

        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cancel-conf",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        service.confirm_draft("al-noor-jewelry", created.id)

        # Cancel confirmed draft
        cancel_res = service.cancel_draft("al-noor-jewelry", created.id)
        assert cancel_res.draft.status == "cancelled"

        # Inventory restored
        inv_after = db_session.query(Inventory).filter(Inventory.product_id == "J-101").first()
        assert inv_after.stock_count == orig_stock
        assert inv_after.reserved_count == orig_reserved


# ─────────────────────────────────────────────────────────────
#  7. TENANT ISOLATION
# ─────────────────────────────────────────────────────────────

class TestTenantIsolation:
    def test_cannot_retrieve_draft_across_tenants(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cross-ses",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        # Attempt to read al-noor-jewelry draft as saffron-table
        with pytest.raises(CrossTenantAccessError):
            service.get_draft("saffron-table", created.id)

    def test_cannot_confirm_draft_across_tenants(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cross-conf",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        with pytest.raises(CrossTenantAccessError):
            service.confirm_draft("saffron-table", created.id)

    def test_cannot_cancel_draft_across_tenants(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="test-cross-canc",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )

        with pytest.raises(CrossTenantAccessError):
            service.cancel_draft("saffron-table", created.id)


# ─────────────────────────────────────────────────────────────
#  8. AUDIT LOGGING & SENSITIVE DATA REDACTION
# ─────────────────────────────────────────────────────────────

class TestAuditLogging:
    def test_audit_log_created_for_all_transitions(self, db_session):
        service = DraftService(db_session)
        created = service.create_draft(
            tenant_id="al-noor-jewelry",
            session_id="audit-ses",
            items=[DraftItemRequest(product_id="J-101", quantity=1)],
        )
        service.confirm_draft("al-noor-jewelry", created.id)
        service.cancel_draft("al-noor-jewelry", created.id)

        logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.tenant_id == "al-noor-jewelry")
            .filter(AuditLog.session_id == "audit-ses")
            .all()
        )
        actions = [log.action for log in logs]
        assert "DRAFT_CREATED" in actions
        assert "DRAFT_CONFIRMED" in actions
        assert "DRAFT_CANCELLED" in actions


# ─────────────────────────────────────────────────────────────
#  9. FASTAPI ENDPOINT & RESTRICTED BOUNDARY TESTS
# ─────────────────────────────────────────────────────────────

class TestDraftEndpoints:
    def test_endpoint_missing_tenant_header_401(self, client):
        resp = client.post(
            "/api/v1/drafts",
            json={"items": [{"productId": "J-101", "quantity": 1}]},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        body = resp.json()
        error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "X-Tenant-ID" in error_msg

    def test_endpoint_mismatched_tenant_403(self, client):
        resp = client.post(
            "/api/v1/drafts",
            headers={"X-Tenant-ID": "al-noor-jewelry"},
            json={
                "tenantId": "saffron-table",
                "items": [{"productId": "J-101", "quantity": 1}],
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        body = resp.json()
        error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "mismatch" in error_msg.lower()

    def test_endpoint_full_lifecycle(self, client):
        headers = {"X-Tenant-ID": "al-noor-jewelry"}

        # 1. Create draft
        create_resp = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={
                "items": [{"productId": "J-101", "quantity": 1}],
                "customerNotes": "VIP customer",
            },
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        draft_data = create_resp.json()
        draft_id = draft_data["id"]
        assert draft_data["status"] == "draft"

        # 2. Retrieve draft
        get_resp = client.get(f"/api/v1/drafts/{draft_id}", headers=headers)
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["id"] == draft_id

        # 3. Explicit confirmation
        confirm_resp = client.post(
            "/api/v1/drafts/confirm",
            headers=headers,
            json={"draftId": draft_id, "idempotencyKey": "REST-IDEMP-1"},
        )
        assert confirm_resp.status_code == status.HTTP_200_OK
        assert confirm_resp.json()["success"] is True
        assert confirm_resp.json()["alreadyConfirmed"] is False
        assert confirm_resp.json()["draft"]["status"] == "confirmed"

        # 4. Duplicate confirmation returns alreadyConfirmed=True
        dup_resp = client.post(
            "/api/v1/drafts/confirm",
            headers=headers,
            json={"draftId": draft_id, "idempotencyKey": "REST-IDEMP-1"},
        )
        assert dup_resp.status_code == status.HTTP_200_OK
        assert dup_resp.json()["alreadyConfirmed"] is True

        # 5. Cancel confirmed draft
        cancel_resp = client.post(
            "/api/v1/drafts/cancel",
            headers=headers,
            json={"draftId": draft_id, "reason": "Customer changed mind"},
        )
        assert cancel_resp.status_code == status.HTTP_200_OK
        assert cancel_resp.json()["draft"]["status"] == "cancelled"

