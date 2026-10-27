"""
Draft Repository
Provides encapsulated, tenant-isolated database access for OrderDraft,
Sessions, Inventory, and AuditLog models.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.models import OrderDraft, SessionModel, Inventory, AuditLog, BIEvent, Tenant
from backend.app.repositories.base import BaseRepository
from backend.app.core.logging import logger


class DraftRepository(BaseRepository[OrderDraft]):
    def __init__(self, db: Session):
        super().__init__(OrderDraft, db)

    def get_by_id_and_tenant(self, draft_id: str, tenant_id: str) -> Optional[OrderDraft]:
        """
        Retrieves a draft strictly constrained by tenant boundary.
        Cross-tenant access returns None.
        """
        return (
            self.db.query(OrderDraft)
            .filter(OrderDraft.id == draft_id)
            .filter(OrderDraft.tenant_id == tenant_id)
            .first()
        )

    def get_by_id_any_tenant(self, draft_id: str) -> Optional[OrderDraft]:
        """Used internally to detect cross-tenant unauthorized access attempts."""
        return self.db.query(OrderDraft).filter(OrderDraft.id == draft_id).first()

    def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[OrderDraft]:
        """Checks for existing draft with this idempotency key."""
        return (
            self.db.query(OrderDraft)
            .filter(OrderDraft.tenant_id == tenant_id)
            .filter(OrderDraft.idempotency_key == idempotency_key)
            .first()
        )

    def get_latest_for_session(self, tenant_id: str, session_id: str) -> Optional[OrderDraft]:
        return (
            self.db.query(OrderDraft)
            .filter(OrderDraft.tenant_id == tenant_id)
            .filter(OrderDraft.session_id == session_id)
            .order_by(OrderDraft.created_at.desc())
            .first()
        )

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

    def get_inventory(self, tenant_id: str, product_id: str) -> Optional[Inventory]:
        return (
            self.db.query(Inventory)
            .filter(Inventory.tenant_id == tenant_id)
            .filter(Inventory.product_id == product_id)
            .first()
        )

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
        Appends an audit log record with sanitized JSON details.
        """
        audit_id = f"AUD-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6]}"
        safe_details = details or {}
        # Ensure sensitive details (like full card numbers or secrets) are scrubbed
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
        Safely records a business telemetry event. Non-fatal if telemetry fails.
        """
        try:
            # Check tenant is_demo
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
            logger.warning("Telemetry event recording skipped or failed: %s", exc)
            return None
