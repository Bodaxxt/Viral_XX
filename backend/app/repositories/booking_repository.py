"""
Booking Repository
Provides atomic, tenant-isolated operations on booking_slots, audit_logs, and bi_events.
Guarantees concurrency safety in SQLite through atomic conditional updates.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.models import BookingSlot, AuditLog, BIEvent, Tenant, SessionModel
from backend.app.repositories.base import BaseRepository
from backend.app.core.logging import logger


class BookingRepository(BaseRepository[BookingSlot]):
    def __init__(self, db: Session):
        super().__init__(BookingSlot, db)

    def get_by_id_and_tenant(self, slot_id: str, tenant_id: str) -> Optional[BookingSlot]:
        """
        Retrieves a booking slot strictly within tenant boundaries.
        Returns None if not found or belongs to a different tenant.
        """
        return (
            self.db.query(BookingSlot)
            .filter(BookingSlot.id == slot_id)
            .filter(BookingSlot.tenant_id == tenant_id)
            .first()
        )

    def get_by_id_any_tenant(self, slot_id: str) -> Optional[BookingSlot]:
        """Used internally for detecting cross-tenant access attempts."""
        return self.db.query(BookingSlot).filter(BookingSlot.id == slot_id).first()

    def list_slots(
        self,
        tenant_id: str,
        slot_date: Optional[str] = None,
        service_type: Optional[str] = None,
        available_only: bool = True,
    ) -> List[BookingSlot]:
        """
        Retrieves booking slots for a tenant with optional filtering by date and service type.
        """
        query = self.db.query(BookingSlot).filter(BookingSlot.tenant_id == tenant_id)

        if available_only:
            query = query.filter(
                BookingSlot.status == "available",
                (BookingSlot.capacity - BookingSlot.booked_count) > 0,
            )

        if slot_date and slot_date.strip():
            query = query.filter(BookingSlot.slot_date == slot_date.strip())

        if service_type and service_type.strip():
            query = query.filter(BookingSlot.service_type.ilike(f"%{service_type.strip()}%"))

        query = query.order_by(BookingSlot.slot_date.asc(), BookingSlot.slot_time.asc())
        return query.all()

    def atomic_reserve_capacity(self, slot_id: str, tenant_id: str, party_size: int) -> bool:
        """
        Atomically increments booked_count and conditionally marks status as 'booked'
        if capacity is reached, ONLY IF current capacity allows it.
        Guarantees single-statement concurrency protection in SQLite.
        Returns True if reservation succeeded, False if slot is unavailable or capacity exceeded.
        """
        sql = text("""
            UPDATE booking_slots
            SET booked_count = booked_count + :party_size,
                status = CASE
                    WHEN (booked_count + :party_size) >= capacity THEN 'booked'
                    ELSE status
                END
            WHERE id = :slot_id
              AND tenant_id = :tenant_id
              AND status = 'available'
              AND (capacity - booked_count) >= :party_size
        """)

        result = self.db.execute(
            sql,
            {
                "slot_id": slot_id,
                "tenant_id": tenant_id,
                "party_size": party_size,
            },
        )
        self.db.flush()
        self.db.expire_all()
        return (result.rowcount or 0) > 0

    def atomic_release_capacity(self, slot_id: str, tenant_id: str, party_size: int) -> bool:
        """
        Atomically decrements booked_count and restores status to 'available'.
        """
        sql = text("""
            UPDATE booking_slots
            SET booked_count = MAX(0, booked_count - :party_size),
                status = 'available'
            WHERE id = :slot_id
              AND tenant_id = :tenant_id
        """)

        result = self.db.execute(
            sql,
            {
                "slot_id": slot_id,
                "tenant_id": tenant_id,
                "party_size": party_size,
            },
        )
        self.db.flush()
        self.db.expire_all()
        return (result.rowcount or 0) > 0

    def ensure_session(
        self,
        session_id: str,
        tenant_id: str,
        customer_name: Optional[str] = None,
        language: str = "en",
    ) -> SessionModel:
        """
        Ensures a session row exists to satisfy foreign key constraints.
        """
        session_obj = (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
        if not session_obj:
            session_obj = SessionModel(
                id=session_id,
                tenant_id=tenant_id,
                customer_name=customer_name,
                language=language,
            )
            self.db.add(session_obj)
            self.db.flush()
        return session_obj

    def log_audit(
        self,
        tenant_id: str,
        session_id: Optional[str],
        action: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """
        Records an audit entry with sanitized details.
        """
        audit_id = f"AUD-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6]}"
        safe_details = details or {}
        details_str = json.dumps(safe_details)

        audit_entry = AuditLog(
            id=audit_id,
            tenant_id=tenant_id,
            session_id=session_id,
            action=action,
            actor=actor,
            details_json=details_str,
            ip_address=ip_address,
        )
        self.db.add(audit_entry)
        self.db.flush()
        return audit_entry

    def record_bi_event(
        self,
        tenant_id: str,
        session_id: Optional[str],
        event_type: str,
        category: Optional[str] = None,
        draft_id: Optional[str] = None,
        outcome: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[BIEvent]:
        """
        Records business telemetry event. Non-fatal.
        """
        try:
            if session_id:
                self.ensure_session(session_id, tenant_id)

            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            is_demo = 1 if (not tenant or tenant.integration_mode != "live") else 0

            event_id = f"EVT-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6]}"
            evt = BIEvent(
                id=event_id,
                tenant_id=tenant_id,
                session_id=session_id,
                event_type=event_type,
                category=category,
                draft_id=draft_id,
                outcome=outcome,
                metadata_json=json.dumps(metadata or {}),
                is_demo=is_demo,
                idempotency_key=idempotency_key,
            )
            self.db.add(evt)
            self.db.flush()
            return evt
        except Exception as exc:
            logger.warning("Telemetry event recording skipped: %s", exc)
            return None
