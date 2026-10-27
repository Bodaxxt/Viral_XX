"""
Sprint 4 — Business Intelligence & Analytics Test Suite

Tests:
1. Supported telemetry event types ingestion
2. Invalid event types and malformed payloads
3. Metadata size limits and JSON validation
4. Idempotency protection and deduplication
5. Tenant and session authorization (401, 403, 404)
6. Cross-tenant isolation (draft linking and query barriers)
7. Client fabrication defense (clients cannot report server-verified outcomes)
8. Server-verified outcomes ingestion
9. Sensitive data sanitization in telemetry metadata
10. 5-Stage sales funnel formula and zero-division edge cases
11. Customer objections breakdown and grouping
12. Unfulfilled demand signals extraction and limit clamping
13. Consolidated telemetry summary metrics
14. Repeatable demo seed generation
15. Node.js response shape compatibility
"""

import json
import pytest
from backend.app.schemas.telemetry import (
    ALLOWED_EVENT_TYPES,
    BIEventType,
    CLIENT_REPORTABLE_EVENT_TYPES,
    SERVER_VERIFIED_EVENT_TYPES,
)
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.telemetry_service import (
    ClientFabricationError,
    CrossTenantViolationError,
    InvalidEventType,
    PayloadSizeExceededError,
    TelemetryService,
    TelemetryServiceError,
    TenantNotFoundError,
)
from backend.app.db.models import OrderDraft, SessionModel, BIEvent


@pytest.fixture
def tenant_jewelry():
    return "al-noor-jewelry"


@pytest.fixture
def tenant_restaurant():
    return "saffron-table"


# ─────────────────────────────────────────────────────────────
# 1. Telemetry Ingestion & Validation
# ─────────────────────────────────────────────────────────────

class TestTelemetryIngestion:
    def test_record_client_reportable_event_success(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        result = service.record_event(
            tenant_id=tenant_jewelry,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            category="search",
            outcome="success",
            metadata={"query": "emerald bracelet", "count": 2},
            source="client",
        )
        assert result["success"] is True
        assert result["duplicate"] is False
        event = result["event"]
        assert event["id"].startswith("EVT-")
        assert event["tenantId"] == tenant_jewelry
        assert event["eventType"] == "PRODUCT_SEARCH"
        assert event["metadata"]["query"] == "emerald bracelet"

    def test_all_allowed_event_types_recordable_from_server(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        for evt_type in sorted(ALLOWED_EVENT_TYPES):
            res = service.record_event(
                tenant_id=tenant_jewelry,
                event_type=evt_type,
                source="server",
            )
            assert res["success"] is True
            assert res["event"]["eventType"] == evt_type

    def test_reject_unwhitelisted_event_type(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        with pytest.raises(InvalidEventType) as exc_info:
            service.record_event(
                tenant_id=tenant_jewelry,
                event_type="UNAUTHORIZED_ARBITRARY_EVENT",
            )
        assert "Invalid event_type" in str(exc_info.value)

    def test_reject_missing_or_empty_tenant(self, db_session):
        service = TelemetryService(db_session)
        with pytest.raises(TelemetryServiceError):
            service.record_event(
                tenant_id="",
                event_type=BIEventType.PRODUCT_SEARCH.value,
            )

    def test_reject_nonexistent_tenant(self, db_session):
        service = TelemetryService(db_session)
        with pytest.raises(TenantNotFoundError):
            service.record_event(
                tenant_id="nonexistent-company-999",
                event_type=BIEventType.PRODUCT_SEARCH.value,
            )


# ─────────────────────────────────────────────────────────────
# 2. Client Fabrication Protection
# ─────────────────────────────────────────────────────────────

class TestClientFabricationDefense:
    def test_client_cannot_fabricate_draft_confirmed(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        with pytest.raises(ClientFabricationError) as exc:
            service.record_event(
                tenant_id=tenant_jewelry,
                event_type=BIEventType.DRAFT_CONFIRMED.value,
                source="client",
            )
        assert "Client cannot fabricate server-verified" in str(exc.value)

    def test_client_cannot_fabricate_draft_created(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        with pytest.raises(ClientFabricationError):
            service.record_event(
                tenant_id=tenant_jewelry,
                event_type=BIEventType.DRAFT_CREATED.value,
                source="client",
            )

    def test_client_cannot_fabricate_handoff_requested(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        with pytest.raises(ClientFabricationError):
            service.record_event(
                tenant_id=tenant_jewelry,
                event_type=BIEventType.HUMAN_HANDOFF_REQUESTED.value,
                source="client",
            )

    def test_server_source_can_record_draft_confirmed(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        res = service.record_event(
            tenant_id=tenant_jewelry,
            event_type=BIEventType.DRAFT_CONFIRMED.value,
            source="server",
        )
        assert res["success"] is True
        assert res["event"]["eventType"] == "DRAFT_CONFIRMED"


# ─────────────────────────────────────────────────────────────
# 3. Idempotency & Deduplication
# ─────────────────────────────────────────────────────────────

class TestTelemetryIdempotency:
    def test_duplicate_idempotency_key_returns_existing(self, db_session, tenant_jewelry):
        service = TelemetryService(db_session)
        key = "idemp-telemetry-unique-key-1"

        res1 = service.record_event(
            tenant_id=tenant_jewelry,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            idempotency_key=key,
            metadata={"query": "first search"},
        )
        assert res1["success"] is True
        assert res1["duplicate"] is False
        event_id = res1["event"]["id"]

        # Second submission with same key
        res2 = service.record_event(
            tenant_id=tenant_jewelry,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            idempotency_key=key,
            metadata={"query": "duplicate search attempt"},
        )
        assert res2["success"] is True
        assert res2["duplicate"] is True
        assert res2["event"]["id"] == event_id
        assert res2["event"]["metadata"]["query"] == "first search"


# ─────────────────────────────────────────────────────────────
# 4. Sensitive Data Sanitization
# ─────────────────────────────────────────────────────────────

class TestSensitiveDataSanitization:
    def test_credit_card_redacted_in_metadata(self):
        meta = {"note": "Customer card: 4111 1111 1111 1111"}
        clean = TelemetryService.sanitize_metadata(meta)
        assert "4111" not in clean["note"]
        assert "[CARD REDACTED]" in clean["note"]

    def test_bearer_token_redacted_in_metadata(self):
        meta = {"auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"}
        clean = TelemetryService.sanitize_metadata(meta)
        assert "eyJhbG" not in clean["auth"]
        assert "[TOKEN REDACTED]" in clean["auth"]

    def test_api_key_redacted_in_metadata(self):
        meta = {"provider_key": "sk-123456789012345678901234"}
        clean = TelemetryService.sanitize_metadata(meta)
        assert "sk-1234" not in clean["provider_key"]
        assert "[KEY REDACTED]" in clean["provider_key"]

    def test_forbidden_top_level_keys_stripped(self):
        meta = {
            "password": "supersecretpassword",
            "token": "secrettoken123",
            "authorization": "Bearer secret",
            "safe_metric": 42,
        }
        clean = TelemetryService.sanitize_metadata(meta)
        assert "password" not in clean
        assert "token" not in clean
        assert "authorization" not in clean
        assert clean["safe_metric"] == 42


# ─────────────────────────────────────────────────────────────
# 5. Cross-Tenant Boundaries & Draft Linking
# ─────────────────────────────────────────────────────────────

class TestCrossTenantBoundaries:
    def test_reject_draft_belonging_to_other_tenant(self, db_session, tenant_jewelry, tenant_restaurant):
        # Create a session and draft belonging to restaurant
        session = SessionModel(id="SES-RESTAURANT-001", tenant_id=tenant_restaurant)
        db_session.add(session)
        draft = OrderDraft(
            id="DRF-RESTAURANT-001",
            session_id="SES-RESTAURANT-001",
            tenant_id=tenant_restaurant,
            items_json="[]",
            subtotal=100,
            total_amount=100,
            currency="EGP",
            status="draft",
            draft_type="product_order",
        )
        db_session.add(draft)
        db_session.commit()

        service = TelemetryService(db_session)
        with pytest.raises(CrossTenantViolationError) as exc:
            service.record_event(
                tenant_id=tenant_jewelry,
                event_type=BIEventType.DRAFT_CREATED.value,
                draft_id=draft.id,
                source="server",
            )
        assert "draftId belongs to a different tenant" in str(exc.value)

    def test_events_query_strictly_isolated_by_tenant(self, db_session, tenant_jewelry, tenant_restaurant):
        service = TelemetryService(db_session)
        service.record_event(
            tenant_id=tenant_jewelry,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            metadata={"query": "gold"},
        )
        service.record_event(
            tenant_id=tenant_restaurant,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            metadata={"query": "tasting menu"},
        )

        jewelry_events = service.get_events(tenant_id=tenant_jewelry)
        assert all(e["tenantId"] == tenant_jewelry for e in jewelry_events)
        assert not any("tasting menu" in str(e["metadata"]) for e in jewelry_events)


# ─────────────────────────────────────────────────────────────
# 6. Sales Funnel Formulas & Zero-Division Edge Cases
# ─────────────────────────────────────────────────────────────

class TestSalesFunnelCalculations:
    def test_funnel_empty_dataset_no_division_by_zero(self, db_session, tenant_jewelry):
        analytics = AnalyticsService(db_session)
        funnel = analytics.get_funnel_metrics(tenant_id=tenant_jewelry, days=30)

        assert funnel["tenant_id"] == tenant_jewelry
        assert funnel["timeframe_days"] == 30
        assert funnel["overallConversionRate"] == "0.0%"
        stages = funnel["stages"]
        assert len(stages) == 5
        assert stages[0]["stage"] == "Inbound Customer Inquiries"
        assert stages[0]["count"] == 0
        assert stages[0]["conversionRate"] == "100.0%"
        assert stages[1]["conversionRate"] == "0.0%"

    def test_funnel_populated_metrics_exact_conversion_rates(self, db_session, tenant_jewelry):
        # Seed 10 sessions
        for i in range(10):
            db_session.add(SessionModel(id=f"SES-FNL-{i}", tenant_id=tenant_jewelry))
        db_session.commit()

        telemetry = TelemetryService(db_session)
        # 8 searches (6 successful)
        for i in range(8):
            telemetry.record_event(
                tenant_id=tenant_jewelry,
                session_id=f"SES-FNL-{i}",
                event_type=BIEventType.PRODUCT_SEARCH.value,
                outcome="success" if i < 6 else "no_results",
                source="server",
            )
        # 4 drafts created
        for i in range(4):
            telemetry.record_event(
                tenant_id=tenant_jewelry,
                session_id=f"SES-FNL-{i}",
                event_type=BIEventType.DRAFT_CREATED.value,
                source="server",
            )
        # 2 drafts confirmed
        for i in range(2):
            telemetry.record_event(
                tenant_id=tenant_jewelry,
                session_id=f"SES-FNL-{i}",
                event_type=BIEventType.DRAFT_CONFIRMED.value,
                source="server",
            )

        analytics = AnalyticsService(db_session)
        funnel = analytics.get_funnel_metrics(tenant_id=tenant_jewelry, days=30)
        stages = funnel["stages"]

        # Stage 1: Inbound Customer Inquiries -> 10, 100.0%
        assert stages[0]["count"] == 10
        assert stages[0]["conversionRate"] == "100.0%"

        # Stage 2: Catalog & Inventory Engaged -> 8 searches / 10 sessions = 80.0%
        assert stages[1]["count"] == 8
        assert stages[1]["conversionRate"] == "80.0%"

        # Stage 3: Grounded Product Recommendation -> 6 successful / 8 searches = 75.0%
        assert stages[2]["count"] == 6
        assert stages[2]["conversionRate"] == "75.0%"

        # Stage 4: Order or Booking Drafted -> 4 drafts / 8 searches = 50.0%
        assert stages[3]["count"] == 4
        assert stages[3]["conversionRate"] == "50.0%"

        # Stage 5: Explicit Customer Confirmation -> 2 confirmed / 4 drafts = 50.0%
        assert stages[4]["count"] == 2
        assert stages[4]["conversionRate"] == "50.0%"

        # Overall: 2 confirmed / max(10, 8, 1) = 2 / 10 = 20.0%
        assert funnel["overallConversionRate"] == "20.0%"


# ─────────────────────────────────────────────────────────────
# 7. Customer Objections & Demand Signals
# ─────────────────────────────────────────────────────────────

class TestObjectionsAndDemand:
    def test_objection_breakdown_categories(self, db_session, tenant_jewelry):
        telemetry = TelemetryService(db_session)
        # 2 out of stock
        telemetry.record_event(tenant_id=tenant_jewelry, event_type=BIEventType.OUT_OF_STOCK_DETECTED.value, source="server")
        telemetry.record_event(tenant_id=tenant_jewelry, event_type=BIEventType.OUT_OF_STOCK_DETECTED.value, source="server")
        # 3 unfulfilled demand
        for _ in range(3):
            telemetry.record_event(tenant_id=tenant_jewelry, event_type=BIEventType.UNFULFILLED_DEMAND.value, source="server")
        # 1 unanswered question
        telemetry.record_event(tenant_id=tenant_jewelry, event_type=BIEventType.UNANSWERED_QUESTION.value, source="server")
        # 1 cancelled draft
        telemetry.record_event(tenant_id=tenant_jewelry, event_type=BIEventType.DRAFT_CANCELLED.value, source="server")

        analytics = AnalyticsService(db_session)
        res = analytics.get_objection_breakdown(tenant_id=tenant_jewelry, days=30)

        assert res["tenant_id"] == tenant_jewelry
        assert res["total_objections"] == 7
        assert res["summary"]["out_of_stock"] == 2
        assert res["summary"]["unfulfilled_searches"] == 3
        assert res["summary"]["unanswered_questions"] == 1
        assert res["summary"]["cancelled_drafts"] == 1
        assert len(res["breakdown"]) >= 4

    def test_demand_signals_filtering_and_limit(self, db_session, tenant_jewelry):
        telemetry = TelemetryService(db_session)
        for i in range(15):
            telemetry.record_event(
                tenant_id=tenant_jewelry,
                event_type=BIEventType.UNFULFILLED_DEMAND.value,
                metadata={"item_num": i},
                source="server",
            )

        analytics = AnalyticsService(db_session)
        signals = analytics.get_unfulfilled_demand_signals(tenant_id=tenant_jewelry, limit=5)
        assert len(signals) == 5
        assert all(s["eventType"] == "UNFULFILLED_DEMAND" for s in signals)


# ─────────────────────────────────────────────────────────────
# 8. Repeatable Demo Seed Generator
# ─────────────────────────────────────────────────────────────

class TestDemoSeedGenerator:
    def test_demo_seed_generates_six_canonical_events(self, db_session, tenant_jewelry):
        analytics = AnalyticsService(db_session)
        res = analytics.seed_demo_events(tenant_id=tenant_jewelry)
        assert res["success"] is True
        assert res["eventsCount"] == 6

        telemetry = TelemetryService(db_session)
        events = telemetry.get_events(tenant_id=tenant_jewelry, limit=20)
        assert len(events) >= 6

        event_types = {e["eventType"] for e in events}
        assert "PRODUCT_SEARCH" in event_types
        assert "UNFULFILLED_DEMAND" in event_types
        assert "OUT_OF_STOCK_DETECTED" in event_types
        assert "UNANSWERED_QUESTION" in event_types
        assert "DRAFT_CREATED" in event_types
        assert "HUMAN_HANDOFF_REQUESTED" in event_types


# ─────────────────────────────────────────────────────────────
# 9. HTTP API Endpoints & Contract Tests
# ─────────────────────────────────────────────────────────────

class TestAnalyticsEndpoints:
    def test_missing_tenant_header_returns_401(self, client):
        res = client.get("/api/v1/analytics/summary")
        assert res.status_code == 401

    def test_mismatched_tenant_returns_403(self, client, tenant_jewelry, tenant_restaurant):
        res = client.get(
            f"/api/v1/analytics/summary?tenantId={tenant_restaurant}",
            headers={"X-Tenant-ID": tenant_jewelry},
        )
        assert res.status_code == 403

    def test_nonexistent_tenant_header_returns_404(self, client):
        res = client.get(
            "/api/v1/analytics/summary",
            headers={"X-Tenant-ID": "nonexistent-tenant"},
        )
        assert res.status_code == 404

    def test_get_summary_success_shape(self, client, tenant_jewelry):
        res = client.get(
            "/api/v1/analytics/summary?days=30",
            headers={"X-Tenant-ID": tenant_jewelry},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "summary" in data
        assert data["summary"]["tenant_id"] == tenant_jewelry
        assert "funnel" in data["summary"]
        assert "searches" in data["summary"]["funnel"]

    def test_get_funnel_success_shape(self, client, tenant_jewelry):
        res = client.get(
            "/api/v1/analytics/funnel?days=30",
            headers={"X-Tenant-ID": tenant_jewelry},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["funnel"]["stages"]) == 5
        assert data["funnel"]["stages"][0]["stage"] == "Inbound Customer Inquiries"

    def test_get_objections_success_shape(self, client, tenant_jewelry):
        res = client.get(
            "/api/v1/analytics/objections?days=30",
            headers={"X-Tenant-ID": tenant_jewelry},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "total_objections" in data["objections"]
        assert "out_of_stock" in data["objections"]["summary"]

    def test_get_demand_success_shape(self, client, tenant_jewelry):
        res = client.get(
            "/api/v1/analytics/demand?days=30&limit=5",
            headers={"X-Tenant-ID": tenant_jewelry},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "demandSignals" in data
        assert isinstance(data["demandSignals"], list)

    def test_demo_seed_endpoint_success(self, client, tenant_jewelry):
        res = client.post(
            "/api/v1/analytics/events/demo-seed",
            headers={"X-Tenant-ID": tenant_jewelry, "Content-Type": "application/json"},
            json={"tenantId": tenant_jewelry},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["eventsCount"] == 6

    def test_ingest_event_endpoint_client_fabrication_rejected(self, client, tenant_jewelry):
        res = client.post(
            "/api/v1/analytics/events",
            headers={"X-Tenant-ID": tenant_jewelry, "Content-Type": "application/json"},
            json={
                "tenantId": tenant_jewelry,
                "eventType": "DRAFT_CONFIRMED",
            },
        )
        assert res.status_code == 403
        err_msg = res.json().get("detail") or res.json().get("error", {}).get("message", "")
        assert "Client cannot fabricate server-verified" in err_msg

    def test_ingest_event_endpoint_behavioral_event_accepted(self, client, tenant_jewelry):
        res = client.post(
            "/api/v1/analytics/events",
            headers={"X-Tenant-ID": tenant_jewelry, "Content-Type": "application/json"},
            json={
                "tenantId": tenant_jewelry,
                "eventType": "PRODUCT_SEARCH",
                "category": "search",
                "metadata": {"query": "emerald tennis necklace"},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["event"]["eventType"] == "PRODUCT_SEARCH"
