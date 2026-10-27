"""
Human Handoff Service
Sprint 3.6 - Migration to Python

Manages validated human escalation workflows, decision triggers,
audit logging, telemetry recording, and state lifecycle transitions.
"""

import json
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.models import Tenant, OrderDraft, AuditLog, BIEvent, HandoffRequest
from backend.app.schemas.handoff import (
    HandoffCreateRequest,
    HandoffCloseRequest,
    HandoffResponse,
    HandoffSummary,
)
from backend.app.services.whatsapp_adapter import (
    WhatsAppAdapter,
    InvalidPhoneNumberError,
    MaliciousUrlDestinationError,
)
from backend.app.core.logging import logger


class HandoffServiceError(Exception):
    """Base exception for Handoff Service errors."""
    pass


class TenantNotFoundError(HandoffServiceError):
    """Raised when tenant does not exist."""
    pass


class HandoffNotFoundError(HandoffServiceError):
    """Raised when handoff request does not exist."""
    pass


class CrossTenantAccessError(HandoffServiceError):
    """Raised when accessing a handoff or draft across tenant boundaries."""
    pass


class InvalidStateTransitionError(HandoffServiceError):
    """Raised when attempting an invalid handoff state transition."""
    pass


class MissingOrInvalidPhoneError(HandoffServiceError):
    """Raised when tenant has no valid WhatsApp business phone configured."""
    pass


# Deterministic trigger patterns
EXPLICIT_HANDOFF_KEYWORDS_EN = [
    "human", "agent", "specialist", "person", "speak to", "talk to",
    "whatsapp", "call me", "customer service", "real person", "concierge",
    "representative", "live support"
]

EXPLICIT_HANDOFF_KEYWORDS_AR = [
    "إنسان", "موظف", "بشري", "خدمة عملاء", "واتساب", "أكلم حد", "عايز اكلم حد",
    "تحدث مع", "اتصال", "بشخص", "مسؤول", "مندوب", "دعم مباشر"
]

COMPLAINT_KEYWORDS = [
    "angry", "furious", "terrible", "horrible", "awful", "scam", "fraud",
    "complaint", "sue", "unacceptable", "money back", "refund", "stolen",
    "غضبان", "زعلان", "نصب", "شكوى", "احتيال", "استرجاع", "فلوسي", "سيء جدا"
]


class HandoffService:
    """
    Core human handoff and escalation management service.
    """

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def evaluate_escalation_intent(
        cls,
        message: str,
        category: str = "",
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Determines whether a user turn requires escalation to a human specialist.
        Returns: (should_escalate, trigger_type, reason_description)
        """
        if not message or not isinstance(message, str):
            return False, None, None

        q = message.lower().strip()

        # 1. Explicit human request
        if any(kw in q for kw in EXPLICIT_HANDOFF_KEYWORDS_EN) or any(kw in message for kw in EXPLICIT_HANDOFF_KEYWORDS_AR):
            return True, "explicit_request", "Customer requested direct specialist communication via WhatsApp"

        # 2. Complaint or severe dissatisfaction
        if any(kw in q for kw in COMPLAINT_KEYWORDS) or any(kw in message for kw in COMPLAINT_KEYWORDS):
            return True, "complaint", "Customer expressed critical dissatisfaction or requested escalation"

        # 3. Medical diagnosis restriction (for healthcare tenants)
        if category == "healthcare":
            medical_triggers = ["diagnose", "prescription", "cure cancer", "تشخيص", "علاج لمرض", "روشتة"]
            if any(kw in q for kw in medical_triggers) or any(kw in message for kw in medical_triggers):
                return True, "uncertainty", "Inquiry requires qualified clinical review beyond AI assistant scope"

        # 4. Bespoke luxury customization or VIP high-budget
        if category == "jewelry":
            bespoke_triggers = ["bespoke design", "custom platinum", "تصميم خاص", "تفصيل طقم"]
            if any(kw in q for kw in bespoke_triggers) or any(kw in message for kw in bespoke_triggers):
                return True, "workflow_approval", "Bespoke high-jewelry customization requires master jeweler consultation"

        return False, None, None

    def create_handoff(
        self,
        tenant_id: str,
        session_id: Optional[str] = None,
        reason: str = "Customer requested live specialist communication",
        notes: Optional[str] = None,
        draft_id: Optional[str] = None,
        escalation_trigger: str = "customer_request",
        idempotency_key: Optional[str] = None,
        actor: str = "customer",
    ) -> HandoffResponse:
        """
        Prepares a validated human handoff and generates a safe WhatsApp click-to-chat URL.
        Enforces tenant isolation, idempotency, and audit logging.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise TenantNotFoundError(f"Tenant workspace '{tenant_id}' not found.")

        # Validate business WhatsApp number from trusted tenant configuration
        raw_phone = tenant.whatsapp_number
        try:
            clean_phone = WhatsAppAdapter.normalize_phone_number(raw_phone)
        except InvalidPhoneNumberError as exc:
            logger.error("Tenant %s has invalid WhatsApp phone '%s': %s", tenant_id, raw_phone, exc)
            raise MissingOrInvalidPhoneError(
                f"Tenant workspace '{tenant_id}' does not have a valid WhatsApp phone configured."
            ) from exc

        # Check idempotency
        if idempotency_key and idempotency_key.strip():
            clean_key = idempotency_key.strip()
            existing = self.db.query(HandoffRequest).filter(
                HandoffRequest.tenant_id == tenant_id,
                HandoffRequest.idempotency_key == clean_key,
            ).first()
            if existing:
                return self._format_response(existing, tenant.name, already_created=True)

        # Resolve associated draft if any
        draft_info = None
        resolved_draft_id = None

        if draft_id and draft_id.strip():
            clean_draft_id = draft_id.strip()
            draft = self.db.query(OrderDraft).filter(OrderDraft.id == clean_draft_id).first()
            if draft:
                if draft.tenant_id != tenant_id:
                    raise CrossTenantAccessError(
                        f"Associated draft '{clean_draft_id}' does not belong to tenant '{tenant_id}'."
                    )
                resolved_draft_id = draft.id
                try:
                    items = json.loads(draft.items_json) if draft.items_json else []
                except Exception:
                    items = []
                draft_info = {
                    "id": draft.id,
                    "items": items,
                    "total_amount": draft.total_amount,
                    "currency": draft.currency,
                    "status": draft.status,
                }
        elif session_id and session_id.strip():
            # Lookup latest draft for session in this tenant
            latest_draft = self.db.query(OrderDraft).filter(
                OrderDraft.tenant_id == tenant_id,
                OrderDraft.session_id == session_id.strip(),
            ).order_by(OrderDraft.created_at.desc()).first()
            if latest_draft:
                resolved_draft_id = latest_draft.id
                try:
                    items = json.loads(latest_draft.items_json) if latest_draft.items_json else []
                except Exception:
                    items = []
                draft_info = {
                    "id": latest_draft.id,
                    "items": items,
                    "total_amount": latest_draft.total_amount,
                    "currency": latest_draft.currency,
                    "status": latest_draft.status,
                }

        # Build message body and click-to-chat URL
        message_body = WhatsAppAdapter.build_message_body(
            tenant_name=tenant.name,
            reason=reason,
            notes=notes,
            draft_info=draft_info,
            session_id=session_id,
        )

        whatsapp_url = WhatsAppAdapter.build_click_to_chat_url(
            phone_number=clean_phone,
            message_body=message_body,
        )

        # Create HandoffRequest record
        handoff_id = f"HND-{uuid.uuid4().hex[:10].upper()}"
        handoff = HandoffRequest(
            id=handoff_id,
            tenant_id=tenant_id,
            session_id=session_id,
            status="link_prepared",
            reason=reason,
            notes=notes,
            draft_id=resolved_draft_id,
            whatsapp_number=tenant.whatsapp_number,
            whatsapp_url=whatsapp_url,
            escalation_trigger=escalation_trigger,
            idempotency_key=idempotency_key.strip() if idempotency_key else None,
        )
        self.db.add(handoff)

        # Log Audit entry
        audit_entry = AuditLog(
            id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
            tenant_id=tenant_id,
            session_id=session_id,
            action="HANDOFF_TRIGGERED",
            actor=actor,
            details_json=json.dumps({
                "handoff_id": handoff_id,
                "reason": reason,
                "draft_id": resolved_draft_id,
                "escalation_trigger": escalation_trigger,
                "whatsapp_number": tenant.whatsapp_number,
                "status": "link_prepared",
            }),
        )
        self.db.add(audit_entry)

        # Log BI Telemetry event (optional — skip if session FK doesn't exist)
        try:
            bi_event = BIEvent(
                id=f"BI-{uuid.uuid4().hex[:12].upper()}",
                tenant_id=tenant_id,
                session_id=None,  # Use None to avoid FK constraint; session linkage via handoff record
                event_type="HUMAN_HANDOFF_REQUESTED",
                category="escalation",
                draft_id=resolved_draft_id,
                outcome="escalated",
                metadata_json=json.dumps({
                    "handoff_id": handoff_id,
                    "reason": reason,
                    "escalation_trigger": escalation_trigger,
                    "has_draft": resolved_draft_id is not None,
                    "session_id": session_id,
                }),
                is_demo=1 if tenant.integration_mode == "demo" else 0,
            )
            self.db.add(bi_event)
        except Exception as bi_exc:
            logger.warning("Skipping BI event for handoff %s: %s", handoff_id, bi_exc)

        try:
            self.db.commit()
            self.db.refresh(handoff)
        except Exception as exc:
            self.db.rollback()
            logger.error("Failed to commit handoff request for tenant %s: %s", tenant_id, exc)
            raise HandoffServiceError(f"Database error while saving handoff: {exc}") from exc

        return self._format_response(handoff, tenant.name, already_created=False)

    def get_handoff(self, tenant_id: str, handoff_id: str) -> HandoffResponse:
        """
        Retrieves handoff details enforcing tenant isolation.
        """
        handoff = self.db.query(HandoffRequest).filter(HandoffRequest.id == handoff_id).first()
        if not handoff:
            raise HandoffNotFoundError(f"Handoff request '{handoff_id}' not found.")

        if handoff.tenant_id != tenant_id:
            raise CrossTenantAccessError(
                f"Unauthorized access: handoff '{handoff_id}' belongs to a different tenant."
            )

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_name = tenant.name if tenant else "Business Team"
        return self._format_response(handoff, tenant_name)

    def close_handoff(
        self,
        tenant_id: str,
        handoff_id: str,
        resolution_notes: Optional[str] = None,
        actor: str = "staff",
    ) -> HandoffResponse:
        """
        Closes an active handoff request.
        """
        handoff = self.db.query(HandoffRequest).filter(HandoffRequest.id == handoff_id).first()
        if not handoff:
            raise HandoffNotFoundError(f"Handoff request '{handoff_id}' not found.")

        if handoff.tenant_id != tenant_id:
            raise CrossTenantAccessError(
                f"Unauthorized access: handoff '{handoff_id}' belongs to a different tenant."
            )

        if handoff.status == "closed":
            raise InvalidStateTransitionError(f"Handoff '{handoff_id}' is already closed.")

        handoff.status = "closed"
        handoff.closed_at = datetime.now(timezone.utc)
        if resolution_notes:
            handoff.notes = f"{handoff.notes or ''} [Resolution: {resolution_notes}]".strip()

        # Audit log entry for closure
        audit = AuditLog(
            id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
            tenant_id=tenant_id,
            session_id=handoff.session_id,
            action="HANDOFF_CLOSED",
            actor=actor,
            details_json=json.dumps({
                "handoff_id": handoff.id,
                "status": "closed",
                "resolution_notes": resolution_notes,
            }),
        )
        self.db.add(audit)

        try:
            self.db.commit()
            self.db.refresh(handoff)
        except Exception as exc:
            self.db.rollback()
            raise HandoffServiceError(f"Database error closing handoff: {exc}") from exc

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_name = tenant.name if tenant else "Business Team"
        return self._format_response(handoff, tenant_name)

    @classmethod
    def _format_response(
        cls,
        handoff: HandoffRequest,
        tenant_name: str,
        already_created: bool = False,
    ) -> HandoffResponse:
        created_str = handoff.created_at.isoformat() if hasattr(handoff.created_at, "isoformat") else str(handoff.created_at)
        updated_str = handoff.updated_at.isoformat() if hasattr(handoff.updated_at, "isoformat") else (str(handoff.updated_at) if handoff.updated_at else None)
        closed_str = handoff.closed_at.isoformat() if hasattr(handoff.closed_at, "isoformat") else (str(handoff.closed_at) if handoff.closed_at else None)

        user_message = (
            f"I have prepared a direct escalation to our specialist team at {tenant_name}. "
            "Click the WhatsApp button to continue your conversation with full context preserved."
        )

        return HandoffResponse(
            id=handoff.id,
            tenant_id=handoff.tenant_id,
            session_id=handoff.session_id,
            status=handoff.status,
            success=True,
            handoff_prepared=True,
            whatsapp_number=handoff.whatsapp_number,
            whatsapp_url=handoff.whatsapp_url,
            summary=HandoffSummary(
                business=tenant_name,
                reason=handoff.reason,
                draft_id=handoff.draft_id,
                notes=handoff.notes or "Direct customer request for human assistance.",
            ),
            user_message=user_message,
            escalation_trigger=handoff.escalation_trigger,
            created_at=created_str,
            updated_at=updated_str,
            closed_at=closed_str,
            already_created=already_created,
            handoffUrl=handoff.whatsapp_url,
            tenantName=tenant_name,
            escalationReason=handoff.reason,
            draftId=handoff.draft_id,
        )
