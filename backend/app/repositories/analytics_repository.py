"""
Analytics & Telemetry Repository
Sprint 4 — Business Intelligence & Analytics Migration

Provides encapsulated, parameterized, tenant-isolated database access
for BIEvent and SessionModel aggregations, preserving exact Node.js SQL semantics.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app.db.models import BIEvent, SessionModel, OrderDraft, Tenant
from backend.app.repositories.base import BaseRepository
from backend.app.core.logging import logger


class AnalyticsRepository(BaseRepository[BIEvent]):
    """
    Repository for Business Intelligence telemetry event persistence and analytical queries.
    Enforces tenant boundaries at every query level.
    """

    def __init__(self, db: Session):
        super().__init__(BIEvent, db)

    def get_by_id_and_tenant(self, event_id: str, tenant_id: str) -> Optional[BIEvent]:
        """Retrieves a single BI event strictly isolated by tenant ID."""
        return (
            self.db.query(BIEvent)
            .filter(BIEvent.id == event_id)
            .filter(BIEvent.tenant_id == tenant_id)
            .first()
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[BIEvent]:
        """Finds existing event by unique idempotency key across all events."""
        return (
            self.db.query(BIEvent)
            .filter(BIEvent.idempotency_key == idempotency_key)
            .first()
        )

    def get_draft_tenant_id(self, draft_id: str) -> Optional[str]:
        """Returns the tenant_id associated with a draft to detect cross-tenant linking."""
        draft = self.db.query(OrderDraft).filter(OrderDraft.id == draft_id).first()
        return draft.tenant_id if draft else None

    def ensure_session(self, session_id: str, tenant_id: str) -> None:
        """
        Ensures a session row exists to satisfy the foreign key constraint on bi_events.session_id.
        Creates one if it does not already exist.
        """
        existing = (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
        if not existing:
            new_session = SessionModel(
                id=session_id,
                tenant_id=tenant_id,
            )
            self.db.add(new_session)
            self.db.flush()

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Fetches tenant configuration record."""
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_events(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        is_demo: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BIEvent]:
        """
        Queries telemetry events for a tenant with parameterized filters.
        Enforces tenant isolation and safe pagination.
        """
        query = self.db.query(BIEvent).filter(BIEvent.tenant_id == tenant_id)

        if event_type:
            query = query.filter(BIEvent.event_type == event_type)
        if session_id:
            query = query.filter(BIEvent.session_id == session_id)
        if is_demo is not None:
            query = query.filter(BIEvent.is_demo == (1 if is_demo else 0))

        return (
            query.order_by(BIEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_sessions(self, tenant_id: str, days: int = 30) -> int:
        """
        Counts inbound sessions for a tenant within the specified timeframe.
        Uses native SQLite datetime arithmetic for exact parity with Node.js.
        """
        sql = text("""
            SELECT COUNT(*) as count FROM sessions
            WHERE tenant_id = :tenant_id
              AND created_at >= datetime('now', '-' || :days || ' days')
        """)
        result = self.db.execute(sql, {"tenant_id": tenant_id, "days": days}).fetchone()
        return result[0] if result else 0

    def get_event_counts_by_type_outcome(
        self,
        tenant_id: str,
        days: int = 30,
        is_demo: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregates event counts grouped by event_type and outcome.
        Used for funnel and summary calculation.
        """
        demo_filter = ""
        params: Dict[str, Any] = {"tenant_id": tenant_id, "days": days}
        if is_demo is not None:
            demo_filter = " AND is_demo = :is_demo"
            params["is_demo"] = 1 if is_demo else 0

        sql = text(f"""
            SELECT event_type, outcome, COUNT(*) as count
            FROM bi_events
            WHERE tenant_id = :tenant_id
              AND created_at >= datetime('now', '-' || :days || ' days')
              {demo_filter}
            GROUP BY event_type, outcome
        """)

        rows = self.db.execute(sql, params).fetchall()
        return [{"event_type": r[0], "outcome": r[1], "count": r[2]} for r in rows]

    def get_objection_rows(
        self,
        tenant_id: str,
        days: int = 30,
        is_demo: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregates categorized objection rows grouped by event_type, category, outcome.
        """
        demo_filter = ""
        params: Dict[str, Any] = {"tenant_id": tenant_id, "days": days}
        if is_demo is not None:
            demo_filter = " AND is_demo = :is_demo"
            params["is_demo"] = 1 if is_demo else 0

        sql = text(f"""
            SELECT event_type, category, outcome, COUNT(*) as count
            FROM bi_events
            WHERE tenant_id = :tenant_id
              AND event_type IN ('UNFULFILLED_DEMAND', 'OUT_OF_STOCK_DETECTED', 'UNANSWERED_QUESTION', 'DRAFT_CANCELLED')
              AND created_at >= datetime('now', '-' || :days || ' days')
              {demo_filter}
            GROUP BY event_type, category, outcome
            ORDER BY count DESC
        """)

        rows = self.db.execute(sql, params).fetchall()
        return [
            {
                "event_type": r[0],
                "category": r[1],
                "outcome": r[2],
                "count": r[3],
            }
            for r in rows
        ]

    def get_unfulfilled_demand_signals(
        self,
        tenant_id: str,
        days: int = 30,
        is_demo: Optional[bool] = None,
        limit: int = 10,
    ) -> List[BIEvent]:
        """
        Retrieves recent demand signals (UNFULFILLED_DEMAND, OUT_OF_STOCK_DETECTED).
        """
        query = (
            self.db.query(BIEvent)
            .filter(BIEvent.tenant_id == tenant_id)
            .filter(BIEvent.event_type.in_(["UNFULFILLED_DEMAND", "OUT_OF_STOCK_DETECTED"]))
        )

        if is_demo is not None:
            query = query.filter(BIEvent.is_demo == (1 if is_demo else 0))

        # Use SQLite datetime filter
        sql_filter = text("created_at >= datetime('now', '-' || :days || ' days')")
        query = query.filter(sql_filter.params(days=days))

        return (
            query.order_by(BIEvent.created_at.desc())
            .limit(limit)
            .all()
        )
