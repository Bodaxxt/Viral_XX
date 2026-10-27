"""
Telemetry Ingestion Service
Sprint 4 — Business Intelligence & Analytics Migration

Provides validated, structured, multi-tenant telemetry ingestion with
foreign key integrity, idempotency protection, sensitive data sanitization,
and strict distinction between client-reported behavioral events and server-verified business outcomes.
"""

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import BIEvent, Tenant, Product
from backend.app.repositories.analytics_repository import AnalyticsRepository
from backend.app.schemas.telemetry import (
    ALLOWED_EVENT_TYPES,
    BIEventType,
    CLIENT_REPORTABLE_EVENT_TYPES,
    SERVER_VERIFIED_EVENT_TYPES,
    TelemetryEventCreate,
    TelemetryEventResponse,
    TelemetryIngestResponse,
)
from backend.app.core.logging import logger


# Sensitive data redaction patterns
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
BEARER_TOKEN_REGEX = re.compile(r"(?:Bearer|bearer|BEARER)\s+[\w\-\.=+/]{8,}", re.IGNORECASE)
API_KEY_REGEX = re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[a-zA-Z0-9]{36})\b")
PASSWORD_REGEX = re.compile(r"(?:password|secret|token)\s*[:=]\s*(?!\[[A-Z_ ]+\])\S+", re.IGNORECASE)

MAX_METADATA_BYTES = 32 * 1024  # 32 KB payload limit


class TelemetryServiceError(Exception):
    """Base exception for telemetry service errors."""
    pass


class TenantNotFoundError(TelemetryServiceError):
    """Raised when the specified tenant workspace does not exist."""
    pass


class InvalidEventType(TelemetryServiceError):
    """Raised when an unsupported or unwhitelisted event type is submitted."""
    pass


class ClientFabricationError(TelemetryServiceError):
    """Raised when an untrusted client attempts to report a server-verified business outcome."""
    pass


class CrossTenantViolationError(TelemetryServiceError):
    """Raised when a draft or session belongs to a different tenant workspace."""
    pass


class PayloadSizeExceededError(TelemetryServiceError):
    """Raised when event metadata exceeds allowed limits."""
    pass


class TelemetryService:
    """
    Manages telemetry event ingestion, sanitization, validation, and retrieval.
    Guarantees strict tenant boundaries and auditability.
    """

    def __init__(self, db: Session, repository: Optional[AnalyticsRepository] = None):
        self.db = db
        self.repository = repository or AnalyticsRepository(db)

    @classmethod
    def sanitize_metadata(cls, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Recursively redacts credit cards, bearer tokens, API keys, and credential assignments.
        Strips dangerous top-level authorization keys.
        """
        if not metadata or not isinstance(metadata, dict):
            return {}

        clean: Dict[str, Any] = {}
        for key, val in metadata.items():
            # Omit dangerous top-level auth/secret fields
            if key.lower() in ("password", "token", "api_key", "secret", "authorization"):
                continue

            if isinstance(val, str):
                redacted = CREDIT_CARD_REGEX.sub("[CARD REDACTED]", val)
                redacted = BEARER_TOKEN_REGEX.sub("[TOKEN REDACTED]", redacted)
                redacted = API_KEY_REGEX.sub("[KEY REDACTED]", redacted)
                redacted = PASSWORD_REGEX.sub("[CREDENTIAL REDACTED]", redacted)
                clean[key] = redacted[:500]
            elif isinstance(val, (int, float, bool)) or val is None:
                clean[key] = val
            elif isinstance(val, list):
                clean[key] = val[:10]
            elif isinstance(val, dict):
                clean[key] = cls.sanitize_metadata(val)

        return clean

    def record_event(
        self,
        tenant_id: str,
        event_type: str,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
        draft_id: Optional[str] = None,
        outcome: Optional[str] = "success",
        metadata: Optional[Dict[str, Any]] = None,
        is_demo: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
        schema_version: str = "1.0",
        source: str = "server",  # "server" or "client"
    ) -> Dict[str, Any]:
        """
        Records a validated, sanitized BI telemetry event.
        Returns a dict matching TelemetryIngestResponse.
        """
        # 1. Validate tenant existence
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise TelemetryServiceError("Telemetry Error: tenantId is required and must be a string.")

        clean_tenant_id = tenant_id.strip()
        tenant = self.repository.get_tenant_by_id(clean_tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Telemetry Error: Tenant '{clean_tenant_id}' does not exist.")

        # 2. Validate event type against strict whitelist
        if not event_type or event_type not in ALLOWED_EVENT_TYPES:
            raise InvalidEventType(
                f"Telemetry Error: Invalid event_type '{event_type}'. "
                f"Must be one of: {', '.join(sorted(ALLOWED_EVENT_TYPES))}"
            )

        # 3. Prevent client fabrication of server-verified business outcomes
        if source == "client" and event_type in SERVER_VERIFIED_EVENT_TYPES:
            raise ClientFabricationError(
                f"Client cannot fabricate server-verified business outcome: '{event_type}'. "
                "This event type can only be emitted by verified backend services."
            )

        # 4. Check payload size
        metadata = metadata or {}
        try:
            serialized_check = json.dumps(metadata)
            if len(serialized_check.encode("utf-8")) > MAX_METADATA_BYTES:
                raise PayloadSizeExceededError(
                    f"Metadata payload size ({len(serialized_check.encode('utf-8'))} bytes) "
                    f"exceeds maximum limit of {MAX_METADATA_BYTES} bytes."
                )
        except (TypeError, ValueError) as e:
            raise TelemetryServiceError(f"Metadata could not be JSON-serialized: {str(e)}")

        # 5. Idempotency check
        if idempotency_key:
            existing = self.repository.get_by_idempotency_key(idempotency_key)
            if existing:
                return {
                    "success": True,
                    "duplicate": True,
                    "event": self.format_event(existing),
                }

        # 6. Foreign key & relationship validation
        if session_id:
            self.repository.ensure_session(session_id, clean_tenant_id)

        if product_id:
            prod = self.db.query(Product).filter(Product.id == product_id).first()
            if not prod:
                product_id = None

        if draft_id:
            owner_tenant = self.repository.get_draft_tenant_id(draft_id)
            if owner_tenant and owner_tenant != clean_tenant_id:
                raise CrossTenantViolationError("Telemetry Error: draftId belongs to a different tenant.")

        # 7. Demo vs Production determination
        if is_demo is not None:
            demo_flag = 1 if is_demo else 0
        else:
            demo_flag = 1 if tenant.integration_mode == "demo" else 0

        # 8. Sanitize metadata
        sanitized_metadata = self.sanitize_metadata(metadata)

        # 9. Insert event
        event_id = f"EVT-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
        bi_event = BIEvent(
            id=event_id,
            tenant_id=clean_tenant_id,
            session_id=session_id,
            event_type=event_type,
            category=category,
            product_id=product_id,
            sku=sku,
            draft_id=draft_id,
            outcome=outcome or "success",
            metadata_json=json.dumps(sanitized_metadata, ensure_ascii=False),
            is_demo=demo_flag,
            schema_version=schema_version,
            idempotency_key=idempotency_key,
        )

        self.db.add(bi_event)
        self.db.commit()
        self.db.refresh(bi_event)

        return {
            "success": True,
            "duplicate": False,
            "event": self.format_event(bi_event),
        }

    def get_events(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        is_demo: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Queries telemetry events with tenant isolation and filters."""
        if not tenant_id:
            raise TelemetryServiceError("tenantId is required for event queries.")

        events = self.repository.get_events(
            tenant_id=tenant_id,
            event_type=event_type,
            session_id=session_id,
            is_demo=is_demo,
            limit=limit,
            offset=offset,
        )
        return [self.format_event(e) for e in events]

    @staticmethod
    def format_event(row: BIEvent) -> Dict[str, Any]:
        """Formats a BIEvent database row into standard API response shape."""
        if not row:
            return {}

        metadata: Dict[str, Any] = {}
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except Exception:
                metadata = {}

        created_at_str = (
            row.created_at.isoformat()
            if hasattr(row.created_at, "isoformat")
            else str(row.created_at) if row.created_at else None
        )

        return {
            "id": row.id,
            "tenantId": row.tenant_id,
            "sessionId": row.session_id,
            "eventType": row.event_type,
            "category": row.category,
            "productId": row.product_id,
            "sku": row.sku,
            "draftId": row.draft_id,
            "outcome": row.outcome,
            "metadata": metadata,
            "isDemo": bool(row.is_demo),
            "schemaVersion": row.schema_version or "1.0",
            "idempotencyKey": row.idempotency_key,
            "createdAt": created_at_str,
        }
