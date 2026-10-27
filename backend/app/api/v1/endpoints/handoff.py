"""
Human Handoff & WhatsApp Escalation API Endpoints
Sprint 3.6 — Python Migration

Provides secure, versioned, tenant-isolated endpoints for human escalation
lifecycle management and WhatsApp click-to-chat URL preparation.

Sprint 5: Uses centralized authenticated principal resolution from core.auth.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.core.auth import get_authorized_tenant, require_permission
from backend.app.schemas.auth import Permissions
from backend.app.schemas.handoff import (
    HandoffCreateRequest,
    HandoffCloseRequest,
    HandoffResponse,
)
from backend.app.services.handoff_service import (
    HandoffService,
    HandoffServiceError,
    HandoffNotFoundError,
    CrossTenantAccessError,
    InvalidStateTransitionError,
    MissingOrInvalidPhoneError,
    TenantNotFoundError,
)
from backend.app.core.logging import logger

router = APIRouter(prefix="/handoff", tags=["handoff"])



def _map_handoff_error(exc: Exception) -> HTTPException:
    """Maps domain service exceptions to safe, structured HTTP exceptions without stack traces."""
    if isinstance(exc, (HandoffNotFoundError, TenantNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CrossTenantAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, (InvalidStateTransitionError, MissingOrInvalidPhoneError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.error("Unhandled handoff service error: %s", exc, exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred while processing the handoff request.",
    )


# ──────────────────────────────────────────────────────────────
#  Create / Request Handoff
# ──────────────────────────────────────────────────────────────

@router.post(
    "/whatsapp",
    response_model=HandoffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request Human Handoff & Prepare WhatsApp URL",
    description=(
        "Validates escalation reason, fetches the business WhatsApp number from trusted tenant config, "
        "constructs a safe click-to-chat URL, logs the HANDOFF_TRIGGERED audit event, and persists the "
        "handoff record. Does NOT send a WhatsApp message or guarantee human acceptance."
    ),
)
def create_handoff(
    request: HandoffCreateRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.HANDOFF_CREATE)),
) -> HandoffResponse:
    # Security: reject body tenantId that doesn't match the authorized header
    if request.tenant_id and request.tenant_id.strip() != authorized_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tenant authorization mismatch: body tenantId '{request.tenant_id}' "
                f"does not match authorized header '{authorized_tenant_id}'."
            ),
        )

    service = HandoffService(db)
    try:
        return service.create_handoff(
            tenant_id=authorized_tenant_id,
            session_id=request.session_id,
            reason=request.reason,
            notes=request.notes,
            draft_id=request.draft_id,
            escalation_trigger=request.escalation_trigger or "customer_request",
            idempotency_key=request.idempotency_key,
            actor="customer",
        )
    except HandoffServiceError as exc:
        raise _map_handoff_error(exc)


# ──────────────────────────────────────────────────────────────
#  Retrieve Handoff Status
# ──────────────────────────────────────────────────────────────

@router.get(
    "/{handoff_id}",
    response_model=HandoffResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Handoff Status",
    description="Returns the current status of a handoff, enforcing tenant isolation.",
)
def get_handoff(
    handoff_id: str = Path(..., description="Handoff record identifier"),
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.READ)),
) -> HandoffResponse:
    service = HandoffService(db)
    try:
        return service.get_handoff(
            tenant_id=authorized_tenant_id,
            handoff_id=handoff_id,
        )
    except HandoffServiceError as exc:
        raise _map_handoff_error(exc)


# ──────────────────────────────────────────────────────────────
#  Close Handoff
# ──────────────────────────────────────────────────────────────

@router.post(
    "/{handoff_id}/close",
    response_model=HandoffResponse,
    status_code=status.HTTP_200_OK,
    summary="Close Handoff Request",
    description=(
        "Closes an active handoff. Only permitted by authorized callers in the same tenant. "
        "Does NOT claim that a human accepted or resolved the case."
    ),
)
def close_handoff(
    handoff_id: str = Path(..., description="Handoff record identifier"),
    request: HandoffCloseRequest = HandoffCloseRequest(),
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.HANDOFF_MANAGE)),
) -> HandoffResponse:
    service = HandoffService(db)
    try:
        return service.close_handoff(
            tenant_id=authorized_tenant_id,
            handoff_id=handoff_id,
            resolution_notes=request.resolution_notes,
            actor="staff",
        )
    except HandoffServiceError as exc:
        raise _map_handoff_error(exc)
