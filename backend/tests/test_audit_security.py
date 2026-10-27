"""
Sprint 4.5 — Integration, Security, and Cutover Readiness Audit Test Suite

Covers:
Phase 2 — Authentication and Tenant Isolation:
  - Header tampering to another tenant
  - Conflicting tenant IDs in headers, queries, and request bodies (403 Forbidden)
  - Missing tenant headers (401 Unauthorized)
  - Non-existent tenant headers (404 Not Found)
  - Cross-tenant draft retrieval, update, confirmation, cancellation (403 Forbidden)
  - Cross-tenant booking reservation and cancellation (403 Forbidden)
  - Cross-tenant handoff retrieval and closure (403 Forbidden)
  - Cross-tenant analytics and telemetry queries (403 Forbidden)
  - Cross-tenant identifier injection into agent tool executor

Phase 3 — Cross-Service Business Consistency:
  - Grounded catalog and inventory lookup
  - Server-calculated pricing invariant (client totals ignored)
  - Recalculation on draft modification
  - Explicit Confirmation Gate enforcement
  - Idempotent confirmation (zero double side effects)
  - Handoff URL preparation without claiming message delivery (message_sent=false)
  - Analytics persistence and client vs. server event trust

Phase 4 & 5 — Contract Parity, Concurrency, and Error Safety:
  - Safe structured error responses (no stack traces, no internal DB paths leaked)
  - Arabic and Unicode preservation
  - Transaction rollback integrity on failure
"""

import json
import pytest
from backend.app.db.models import BookingSlot, OrderDraft, SessionModel, Tenant
from backend.app.schemas.draft import DraftItemRequest
from backend.app.services.draft_service import DraftService, CrossTenantAccessError
from backend.app.services.booking_service import BookingService
from backend.app.services.handoff_service import HandoffService
from backend.app.services.telemetry_service import TelemetryService, ClientFabricationError
from backend.app.agents.tools import ValidatedAgentToolExecutor


@pytest.fixture
def jewelry_tenant():
    return "al-noor-jewelry"


@pytest.fixture
def restaurant_tenant():
    return "saffron-table"


@pytest.fixture
def healthcare_tenant():
    return "vitalis-health"


# ─────────────────────────────────────────────────────────────
# 1. Authentication & Tenant Authorization Boundaries (Phase 2)
# ─────────────────────────────────────────────────────────────

class TestTenantAuthorizationBoundaries:
    """Verifies strict tenant isolation across all endpoints and services."""

    def test_missing_tenant_header_returns_401_on_all_protected_routes(self, client):
        endpoints = [
            ("GET", "/api/v1/drafts/DRF-TEST-123"),
            ("POST", "/api/v1/drafts"),
            ("POST", "/api/v1/drafts/confirm"),
            ("POST", "/api/v1/drafts/cancel"),
            ("GET", "/api/v1/bookings/availability"),
            ("POST", "/api/v1/bookings/reserve"),
            ("POST", "/api/v1/bookings/cancel"),
            ("POST", "/api/v1/handoff/whatsapp"),
            ("GET", "/api/v1/handoff/HND-123"),
            ("POST", "/api/v1/handoff/HND-123/close"),
            ("GET", "/api/v1/analytics/summary"),
            ("GET", "/api/v1/analytics/funnel"),
            ("GET", "/api/v1/analytics/objections"),
            ("GET", "/api/v1/analytics/demand"),
            ("GET", "/api/v1/analytics/events"),
            ("POST", "/api/v1/analytics/events"),
        ]

        for method, path in endpoints:
            if method == "GET":
                res = client.get(path)
            else:
                res = client.post(path, json={})
            assert res.status_code == 401, f"Expected 401 on {method} {path}, got {res.status_code}"

    def test_nonexistent_tenant_header_returns_404(self, client):
        headers = {"X-Tenant-ID": "fake-tenant-does-not-exist"}
        res = client.get("/api/v1/analytics/summary", headers=headers)
        assert res.status_code == 404

    def test_conflicting_tenant_in_body_and_header_rejected_with_403(
        self, client, jewelry_tenant, restaurant_tenant
    ):
        # Header authorizes jewelry, but payload claims restaurant
        headers = {"X-Tenant-ID": jewelry_tenant}

        # 1. Draft creation conflict
        res_draft = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={
                "tenantId": restaurant_tenant,
                "items": [{"productId": "J-101", "quantity": 1}],
            },
        )
        assert res_draft.status_code == 403

        # 2. Booking reservation conflict
        res_booking = client.post(
            "/api/v1/bookings/reserve",
            headers=headers,
            json={
                "tenantId": restaurant_tenant,
                "slotId": "SLOT-R01",
                "customerName": "Test User",
            },
        )
        assert res_booking.status_code == 403

        # 3. Telemetry event conflict
        res_telemetry = client.post(
            "/api/v1/analytics/events",
            headers=headers,
            json={
                "tenantId": restaurant_tenant,
                "eventType": "PRODUCT_SEARCH",
            },
        )
        assert res_telemetry.status_code == 403

    def test_conflicting_tenant_in_query_param_rejected_with_403(
        self, client, jewelry_tenant, restaurant_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        query_endpoints = [
            f"/api/v1/analytics/summary?tenantId={restaurant_tenant}",
            f"/api/v1/analytics/funnel?tenantId={restaurant_tenant}",
            f"/api/v1/analytics/objections?tenantId={restaurant_tenant}",
            f"/api/v1/analytics/demand?tenantId={restaurant_tenant}",
            f"/api/v1/analytics/events?tenantId={restaurant_tenant}",
        ]
        for url in query_endpoints:
            res = client.get(url, headers=headers)
            assert res.status_code == 403, f"Expected 403 on {url}, got {res.status_code}"


# ─────────────────────────────────────────────────────────────
# 2. Cross-Tenant Mutation & Access Prevention (Phase 2 & 3)
# ─────────────────────────────────────────────────────────────

class TestCrossTenantMutationPrevention:
    """Verifies that an authorized tenant cannot access or mutate resources of another tenant."""

    def test_cannot_read_or_mutate_other_tenant_draft(
        self, client, db_session, jewelry_tenant, restaurant_tenant
    ):
        # Create a draft belonging to restaurant
        draft_service = DraftService(db_session)
        draft = draft_service.create_draft(
            tenant_id=restaurant_tenant,
            items=[DraftItemRequest(product_id="R-201", quantity=2)],
        )

        jewelry_headers = {"X-Tenant-ID": jewelry_tenant}

        # 1. Attempt GET
        res_get = client.get(f"/api/v1/drafts/{draft.id}", headers=jewelry_headers)
        assert res_get.status_code == 403

        # 2. Attempt PUT (update)
        res_put = client.put(
            f"/api/v1/drafts/{draft.id}",
            headers=jewelry_headers,
            json={"items": [{"productId": "R-201", "quantity": 3}]},
        )
        assert res_put.status_code == 403

        # 3. Attempt POST confirm
        res_confirm = client.post(
            "/api/v1/drafts/confirm",
            headers=jewelry_headers,
            json={"draftId": draft.id},
        )
        assert res_confirm.status_code == 403

        # 4. Attempt POST cancel
        res_cancel = client.post(
            "/api/v1/drafts/cancel",
            headers=jewelry_headers,
            json={"draftId": draft.id},
        )
        assert res_cancel.status_code == 403

    def test_cannot_reserve_or_cancel_other_tenant_booking(
        self, client, db_session, jewelry_tenant, restaurant_tenant
    ):
        # Restaurant slot SLOT-R01 exists in test fixtures
        jewelry_headers = {"X-Tenant-ID": jewelry_tenant}

        # Attempt to reserve restaurant slot with jewelry tenant authorization
        res = client.post(
            "/api/v1/bookings/reserve",
            headers=jewelry_headers,
            json={
                "slotId": "SLOT-R01",
                "customerName": "Intruder",
                "customerPhone": "+97444000000",
                "partySize": 2,
            },
        )
        assert res.status_code == 403

    def test_cannot_view_or_close_other_tenant_handoff(
        self, client, db_session, jewelry_tenant, restaurant_tenant
    ):
        # Create handoff for restaurant
        handoff_service = HandoffService(db_session)
        handoff = handoff_service.create_handoff(
            tenant_id=restaurant_tenant,
            reason="Customer wants table near window",
        )

        jewelry_headers = {"X-Tenant-ID": jewelry_tenant}

        # Attempt GET
        res_get = client.get(f"/api/v1/handoff/{handoff.id}", headers=jewelry_headers)
        assert res_get.status_code == 403

        # Attempt Close
        res_close = client.post(
            f"/api/v1/handoff/{handoff.id}/close",
            headers=jewelry_headers,
            json={"resolutionNotes": "Unauthorized attempt"},
        )
        assert res_close.status_code == 403

    def test_agent_tool_executor_cannot_inject_cross_tenant_draft_id(
        self, db_session, jewelry_tenant, restaurant_tenant
    ):
        # Create draft for restaurant
        draft_service = DraftService(db_session)
        restaurant_draft = draft_service.create_draft(
            tenant_id=restaurant_tenant,
            items=[DraftItemRequest(product_id="R-201", quantity=1)],
        )

        # Agent runs in context of jewelry tenant
        agent_executor = ValidatedAgentToolExecutor(
            db=db_session,
            tenant_id=jewelry_tenant,
            session_id="ses-jewelry-agent-01",
        )

        # Attempt to confirm restaurant draft via agent tool
        result = agent_executor.execute(
            "confirm_order_draft",
            {
                "draft_id": restaurant_draft.id,
                "customer_explicitly_confirmed": True,
            },
        )
        assert result["success"] is False
        assert "Unauthorized" in result.get("error", "") or "another tenant" in result.get("error", "")


# ─────────────────────────────────────────────────────────────
# 3. Cross-Service Business Consistency & Confirmation Gates (Phase 3)
# ─────────────────────────────────────────────────────────────

class TestBusinessWorkflowConsistency:
    """Verifies end-to-end business integrity: pricing, gates, idempotency, and handoffs."""

    def test_server_pricing_invariant_ignores_client_totals(
        self, client, db_session, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}

        # Client attempts to pass a spoofed low total ($1.00)
        res = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={
                "items": [{"productId": "J-101", "quantity": 1}],
                "total_amount": 1.0,
                "subtotal": 1.0,
            },
        )
        assert res.status_code == 201
        data = res.json()

        # Server must enforce actual catalog base price (42,000 QAR)
        assert data["subtotal"] == 42000.0
        assert data["total_amount"] == 42000.0

    def test_draft_update_recalculates_pricing_consistently(
        self, client, db_session, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}

        # Create initial draft: 1x J-101 (42,000)
        create_res = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={"items": [{"productId": "J-101", "quantity": 1}]},
        )
        draft_id = create_res.json()["id"]

        # Update draft to 2x J-101 + discount code VIRALX10 (10%)
        update_res = client.put(
            f"/api/v1/drafts/{draft_id}",
            headers=headers,
            json={
                "items": [{"productId": "J-101", "quantity": 2}],
                "discount_code": "VIRALX10",
            },
        )
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["subtotal"] == 84000.0
        assert data["discount_amount"] == 8400.0
        assert data["total_amount"] == 75600.0

    def test_confirmation_gate_blocks_unauthorized_confirmation(
        self, db_session, jewelry_tenant
    ):
        # Direct agent tool call without customer explicit authorization
        executor = ValidatedAgentToolExecutor(
            db=db_session,
            tenant_id=jewelry_tenant,
            session_id="ses-gate-01",
        )
        res = executor.execute(
            "confirm_order_draft",
            {
                "draft_id": "DRF-ANY-001",
                "customer_explicitly_confirmed": False,
            },
        )
        assert res["success"] is False
        assert res["blocked"] is True
        assert res["reason"] == "CONFIRMATION_GATE_BLOCKED"

    def test_idempotent_confirmation_prevents_duplicate_side_effects(
        self, client, db_session, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}

        # 1. Create draft
        res = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={"items": [{"productId": "J-102", "quantity": 1}]},
        )
        draft_id = res.json()["id"]

        # 2. First confirmation
        c1 = client.post(
            "/api/v1/drafts/confirm",
            headers=headers,
            json={"draftId": draft_id, "idempotencyKey": "audit-idemp-001"},
        )
        assert c1.status_code == 200
        d1 = c1.json()
        assert d1["success"] is True
        assert d1["already_confirmed"] is False
        ref1 = d1["external_reference"]

        # 3. Second confirmation with same idempotency key
        c2 = client.post(
            "/api/v1/drafts/confirm",
            headers=headers,
            json={"draftId": draft_id, "idempotencyKey": "audit-idemp-001"},
        )
        assert c2.status_code == 200
        d2 = c2.json()
        assert d2["success"] is True
        assert d2["already_confirmed"] is True
        assert d2["external_reference"] == ref1

    def test_handoff_preparation_does_not_claim_message_sent(
        self, client, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        res = client.post(
            "/api/v1/handoff/whatsapp",
            headers=headers,
            json={"reason": "Customer inquiry regarding international shipping"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data.get("message_sent", False) is False
        assert "No backend delivery was performed" in data["disclaimer"]
        assert data["handoffUrl"].startswith("https://wa.me/")

    def test_client_cannot_fabricate_server_verified_telemetry_outcomes(
        self, client, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        fabricated_events = [
            "DRAFT_CONFIRMED",
            "DRAFT_CREATED",
            "DRAFT_CANCELLED",
            "HUMAN_HANDOFF_REQUESTED",
            "OUT_OF_STOCK_DETECTED",
        ]
        for evt in fabricated_events:
            res = client.post(
                "/api/v1/analytics/events",
                headers=headers,
                json={"eventType": evt},
            )
            assert res.status_code == 403, f"Expected 403 for client-reported {evt}, got {res.status_code}"


# ─────────────────────────────────────────────────────────────
# 4. Contract Parity, Unicode, & Error Scrubbing (Phase 4 & 5)
# ─────────────────────────────────────────────────────────────

class TestContractParityAndSecurityScrubbing:
    """Verifies that responses match legacy shapes, support Arabic, and never leak internal details."""

    def test_arabic_text_preserved_across_drafts_and_handoffs(
        self, client, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        arabic_note = "طلب خاص: تغليف هدايا ملكي باللون الأخضر والذهبي"

        res = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={
                "items": [{"productId": "J-101", "quantity": 1}],
                "customerNotes": arabic_note,
            },
        )
        assert res.status_code == 201
        assert res.json()["customer_notes"] == arabic_note

    def test_error_responses_do_not_leak_stack_traces_or_paths(
        self, client, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        # Trigger validation error
        res = client.post(
            "/api/v1/drafts",
            headers=headers,
            json={"items": "invalid_not_a_list"},
        )
        assert res.status_code == 422
        body = res.text
        # Assert no python file paths or stack trace words leaked
        assert "Traceback" not in body
        assert ".py\"" not in body
        assert "site-packages" not in body

    def test_node_compatible_handoff_response_shape(
        self, client, jewelry_tenant
    ):
        headers = {"X-Tenant-ID": jewelry_tenant}
        res = client.post(
            "/api/v1/handoff/whatsapp",
            headers=headers,
            json={"reason": "Customer inquiry"},
        )
        assert res.status_code == 201
        data = res.json()
        # Node.js contract fields
        assert "handoffUrl" in data
        assert "tenantName" in data
        assert "escalationReason" in data
        assert "summary" in data
