"""
Analytics Aggregation Service
Sprint 4 — Business Intelligence & Analytics Migration

Calculates verified conversion funnels, customer objection breakdowns,
inventory demand signals, telemetry summaries, and demo seed data.
"""

import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import Tenant
from backend.app.repositories.analytics_repository import AnalyticsRepository
from backend.app.schemas.telemetry import BIEventType
from backend.app.services.telemetry_service import (
    TelemetryService,
    TelemetryServiceError,
    TenantNotFoundError,
)
from backend.app.core.logging import logger


class AnalyticsService:
    """
    Computes business metrics and analytical aggregations with strict multi-tenant isolation.
    """

    def __init__(
        self,
        db: Session,
        repository: Optional[AnalyticsRepository] = None,
        telemetry_service: Optional[TelemetryService] = None,
    ):
        self.db = db
        self.repository = repository or AnalyticsRepository(db)
        self.telemetry_service = telemetry_service or TelemetryService(db, self.repository)

    def _verify_tenant(self, tenant_id: str) -> Tenant:
        """Verifies that the tenant workspace exists."""
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise TelemetryServiceError("tenantId is required.")
        tenant = self.repository.get_tenant_by_id(tenant_id.strip())
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' does not exist.")
        return tenant

    def get_telemetry_summary(
        self,
        tenant_id: str,
        is_demo: Optional[bool] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Aggregates event telemetry summary for a tenant over the specified timeframe.
        """
        self._verify_tenant(tenant_id)
        days = max(1, min(days, 365))  # Clamp between 1 and 365 days

        rows = self.repository.get_event_counts_by_type_outcome(
            tenant_id=tenant_id,
            days=days,
            is_demo=is_demo,
        )

        total_events = 0
        by_event_type: Dict[str, int] = {}
        funnel_counters = {
            "searches": 0,
            "unfulfilled": 0,
            "out_of_stock": 0,
            "drafts_created": 0,
            "drafts_confirmed": 0,
            "drafts_cancelled": 0,
            "handoffs": 0,
        }

        for r in rows:
            cnt = r["count"]
            evt_type = r["event_type"]
            total_events += cnt
            by_event_type[evt_type] = by_event_type.get(evt_type, 0) + cnt

            if evt_type == BIEventType.PRODUCT_SEARCH.value:
                funnel_counters["searches"] += cnt
            elif evt_type == BIEventType.UNFULFILLED_DEMAND.value:
                funnel_counters["unfulfilled"] += cnt
            elif evt_type == BIEventType.OUT_OF_STOCK_DETECTED.value:
                funnel_counters["out_of_stock"] += cnt
            elif evt_type == BIEventType.DRAFT_CREATED.value:
                funnel_counters["drafts_created"] += cnt
            elif evt_type == BIEventType.DRAFT_CONFIRMED.value:
                funnel_counters["drafts_confirmed"] += cnt
            elif evt_type == BIEventType.DRAFT_CANCELLED.value:
                funnel_counters["drafts_cancelled"] += cnt
            elif evt_type == BIEventType.HUMAN_HANDOFF_REQUESTED.value:
                funnel_counters["handoffs"] += cnt

        return {
            "tenant_id": tenant_id,
            "timeframe_days": days,
            "total_events": total_events,
            "by_event_type": by_event_type,
            "funnel": funnel_counters,
        }

    def get_funnel_metrics(
        self,
        tenant_id: str,
        is_demo: Optional[bool] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculates 5-stage conversion funnel metrics matching Node.js production logic.
        """
        self._verify_tenant(tenant_id)
        days = max(1, min(days, 365))

        # 1. Total inbound sessions
        total_sessions = self.repository.count_sessions(tenant_id, days=days)

        # 2. Event type counts
        rows = self.repository.get_event_counts_by_type_outcome(
            tenant_id=tenant_id,
            days=days,
            is_demo=is_demo,
        )

        searches = 0
        successful_searches = 0
        drafts_created = 0
        drafts_confirmed = 0

        for r in rows:
            evt_type = r["event_type"]
            outcome = r["outcome"]
            cnt = r["count"]

            if evt_type == BIEventType.PRODUCT_SEARCH.value:
                searches += cnt
                if outcome == "success":
                    successful_searches += cnt
            elif evt_type == BIEventType.DRAFT_CREATED.value:
                drafts_created += cnt
            elif evt_type == BIEventType.DRAFT_CONFIRMED.value:
                drafts_confirmed += cnt

        # 5-stage conversion calculation
        base_inquiries = max(total_sessions, searches, 1)

        stages = [
            {
                "stage": "Inbound Customer Inquiries",
                "count": total_sessions,
                "conversionRate": "100.0%",
            },
            {
                "stage": "Catalog & Inventory Engaged",
                "count": searches,
                "conversionRate": (
                    f"{(searches / total_sessions * 100):.1f}%"
                    if total_sessions > 0
                    else "0.0%"
                ),
            },
            {
                "stage": "Grounded Product Recommendation",
                "count": successful_searches,
                "conversionRate": (
                    f"{(successful_searches / searches * 100):.1f}%"
                    if searches > 0
                    else "0.0%"
                ),
            },
            {
                "stage": "Order or Booking Drafted",
                "count": drafts_created,
                "conversionRate": (
                    f"{(drafts_created / searches * 100):.1f}%"
                    if searches > 0
                    else "0.0%"
                ),
            },
            {
                "stage": "Explicit Customer Confirmation",
                "count": drafts_confirmed,
                "conversionRate": (
                    f"{(drafts_confirmed / drafts_created * 100):.1f}%"
                    if drafts_created > 0
                    else "0.0%"
                ),
            },
        ]

        overall_conversion_rate = (
            f"{(drafts_confirmed / base_inquiries * 100):.1f}%"
            if base_inquiries > 0
            else "0.0%"
        )

        return {
            "tenant_id": tenant_id,
            "timeframe_days": days,
            "overallConversionRate": overall_conversion_rate,
            "stages": stages,
        }

    def get_objection_breakdown(
        self,
        tenant_id: str,
        is_demo: Optional[bool] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Retrieves categorized purchase objections and friction points.
        """
        self._verify_tenant(tenant_id)
        days = max(1, min(days, 365))

        rows = self.repository.get_objection_rows(
            tenant_id=tenant_id,
            days=days,
            is_demo=is_demo,
        )

        categories = {
            "out_of_stock": 0,
            "unfulfilled_searches": 0,
            "unanswered_questions": 0,
            "cancelled_drafts": 0,
        }

        for r in rows:
            evt_type = r["event_type"]
            cnt = r["count"]
            if evt_type == BIEventType.OUT_OF_STOCK_DETECTED.value:
                categories["out_of_stock"] += cnt
            elif evt_type == BIEventType.UNFULFILLED_DEMAND.value:
                categories["unfulfilled_searches"] += cnt
            elif evt_type == BIEventType.UNANSWERED_QUESTION.value:
                categories["unanswered_questions"] += cnt
            elif evt_type == BIEventType.DRAFT_CANCELLED.value:
                categories["cancelled_drafts"] += cnt

        total_objections = sum(categories.values())

        return {
            "tenant_id": tenant_id,
            "timeframe_days": days,
            "total_objections": total_objections,
            "summary": categories,
            "breakdown": rows,
        }

    def get_unfulfilled_demand_signals(
        self,
        tenant_id: str,
        is_demo: Optional[bool] = None,
        days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Extracts recent unfulfilled demand signals and out-of-stock events.
        """
        self._verify_tenant(tenant_id)
        days = max(1, min(days, 365))
        limit = max(1, min(limit, 100))

        events = self.repository.get_unfulfilled_demand_signals(
            tenant_id=tenant_id,
            days=days,
            is_demo=is_demo,
            limit=limit,
        )
        return [self.telemetry_service.format_event(e) for e in events]

    def seed_demo_events(self, tenant_id: str = "al-noor-jewelry") -> Dict[str, Any]:
        """
        Generates repeatable demo seed events for testing & dashboard preview.
        Matches exact Node.js seed event set.
        """
        tenant = self._verify_tenant(tenant_id)
        session_id = f"SES-SEED-{int(time.time() * 1000)}"

        # 1. Product Search Event
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.PRODUCT_SEARCH.value,
            category="search",
            outcome="success",
            is_demo=True,
            metadata={"query": "diamond emerald collar", "count": 2},
            source="server",
        )

        # 2. Unfulfilled Demand Event
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.UNFULFILLED_DEMAND.value,
            category="search",
            outcome="no_results",
            is_demo=True,
            metadata={"query": "platinum tennis bracelet under 5000", "price_barrier": 5000},
            source="server",
        )

        # 3. Out of stock Event
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.OUT_OF_STOCK_DETECTED.value,
            category="inventory",
            product_id="J-104",
            sku="SKU-CUF-104",
            outcome="out_of_stock",
            is_demo=True,
            metadata={"location": "Doha Place Vendôme Flagship"},
            source="server",
        )

        # 4. Unanswered Question Event
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.UNANSWERED_QUESTION.value,
            category="policy",
            outcome="unanswered",
            is_demo=True,
            metadata={"query": "international wire swift transfer fees"},
            source="server",
        )

        # 5. Draft Created Event
        seed_draft_id = f"DRF-SEED-{int(time.time()):X}"
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.DRAFT_CREATED.value,
            category="product_order",
            outcome="draft_prepared",
            is_demo=True,
            metadata={"draft_id": seed_draft_id, "total_amount": 42000, "currency": tenant.currency or "QAR"},
            source="server",
        )

        # 6. Human Handoff Event
        self.telemetry_service.record_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BIEventType.HUMAN_HANDOFF_REQUESTED.value,
            category="escalation",
            outcome="escalated",
            is_demo=True,
            metadata={"reason": "VIP custom engraving request", "whatsapp_number": getattr(tenant, "whatsapp_number", None) or "+97444123456"},
            source="server",
        )

        return {
            "success": True,
            "message": "Demo telemetry seed events recorded successfully.",
            "eventsCount": 6,
        }
