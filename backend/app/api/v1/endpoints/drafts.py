"""
Draft Orders API Endpoints
Provides secure, versioned, tenant-isolated operations for draft order creation,
retrieval, update, explicit confirmation, and cancellation.

Sprint 5: Uses centralized authenticated principal resolution from core.auth.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import OrderDraft
from backend.app.core.auth import (
    get_authorized_tenant,
    get_current_principal,
    require_permission,
)
from backend.app.schemas.auth import AuthenticatedPrincipal, Permissions
from backend.app.schemas.draft import (
    DraftCreateRequest,
    DraftUpdateRequest,
    DraftConfirmRequest,
    DraftCancelRequest,
    DraftResponse,
    DraftConfirmResponse,
    DraftCancelResponse,
)
from backend.app.services.draft_service import (
    DraftService,
    DraftServiceError,
    DraftNotFoundError,
    CrossTenantAccessError,
    InvalidStateTransitionError,
    InsufficientStockError,
    TenantNotFoundError,
    ProductNotFoundError,
)
from backend.app.core.logging import logger

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _verify_customer_ownership(draft_id: str, tenant_id: str, principal: AuthenticatedPrincipal, db: Session) -> None:
    """Enforces that a customer principal cannot access or mutate another customer's draft order."""
    if principal.role == "customer":
        draft_row = db.query(OrderDraft).filter(OrderDraft.id == draft_id, OrderDraft.tenant_id == tenant_id).first()
        if draft_row and draft_row.session_id:
            # Check ownership
            is_owner = (
                draft_row.session_id == principal.user_id
                or draft_row.session_id == f"cust-{principal.user_id}"
                or draft_row.session_id.startswith(f"cust-{principal.user_id}-")
            )
            if not is_owner and draft_row.session_id.startswith("cust-"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Customer cannot access or modify another customer's draft order.",
                )


def _map_service_error(exc: Exception) -> HTTPException:
    """Maps domain service exceptions to safe, structured HTTP exceptions."""
    if isinstance(exc, (DraftNotFoundError, TenantNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CrossTenantAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, (InvalidStateTransitionError, InsufficientStockError, ProductNotFoundError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.error("Unhandled draft service error: %s", exc, exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred while processing the draft order.",
    )


# ─────────────────────────────────────────────────────────────
#  Create Draft
# ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Order",
    description="Creates a new non-binding draft order. Does not charge or reserve stock.",
)
def create_draft(
    request: DraftCreateRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_CREATE)),
) -> DraftResponse:
    # Security: Verify that if a tenantId is in the body, it matches the authorized header
    if request.tenant_id and request.tenant_id.strip() != authorized_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tenant authorization mismatch: body tenantId '{request.tenant_id}' "
                f"does not match authorized header '{authorized_tenant_id}'."
            ),
        )

    # Scoped session_id for customer ownership
    session_id = request.session_id
    if principal.role == "customer":
        if not session_id:
            session_id = f"cust-{principal.user_id}"
        elif not session_id.startswith(f"cust-{principal.user_id}") and session_id != principal.user_id:
            session_id = f"cust-{principal.user_id}-{session_id}"

    service = DraftService(db)
    try:
        return service.create_draft(
            tenant_id=authorized_tenant_id,
            items=request.items,
            session_id=session_id,
            customer_notes=request.customer_notes,
            draft_type=request.draft_type,
            discount_code=request.discount_code,
            apply_shipping=request.apply_shipping,
        )
    except Exception as exc:
        raise _map_service_error(exc)


# ─────────────────────────────────────────────────────────────
#  Retrieve Draft
# ─────────────────────────────────────────────────────────────

@router.get(
    "/{draft_id}",
    response_model=DraftResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Draft Order",
    description="Retrieves a verified draft order within the authorized tenant boundary.",
)
def get_draft(
    draft_id: str,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.READ)),
) -> DraftResponse:
    _verify_customer_ownership(draft_id=draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    service = DraftService(db)
    try:
        return service.get_draft(tenant_id=authorized_tenant_id, draft_id=draft_id)
    except Exception as exc:
        raise _map_service_error(exc)


# ─────────────────────────────────────────────────────────────
#  Update Draft
# ─────────────────────────────────────────────────────────────

@router.put(
    "/{draft_id}",
    response_model=DraftResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Draft Order",
    description="Modifies items or notes on an existing draft order. Only permitted in 'draft' status.",
)
def update_draft(
    draft_id: str,
    request: DraftUpdateRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_UPDATE)),
) -> DraftResponse:
    _verify_customer_ownership(draft_id=draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    service = DraftService(db)
    try:
        return service.update_draft(
            tenant_id=authorized_tenant_id,
            draft_id=draft_id,
            items=request.items,
            customer_notes=request.customer_notes,
            discount_code=request.discount_code,
            apply_shipping=request.apply_shipping,
        )
    except Exception as exc:
        raise _map_service_error(exc)


# ─────────────────────────────────────────────────────────────
#  Explicit Confirmation Gate
# ─────────────────────────────────────────────────────────────

@router.post(
    "/confirm",
    response_model=DraftConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Draft Order (Node.js Compatible)",
    description="Explicitly confirms a draft order, revalidates stock, and reserves inventory.",
)
def confirm_draft_compat(
    request: DraftConfirmRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_CONFIRM)),
) -> DraftConfirmResponse:
    if not request.draft_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="draftId is required in confirmation payload.",
        )

    _verify_customer_ownership(draft_id=request.draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    service = DraftService(db)
    try:
        return service.confirm_draft(
            tenant_id=authorized_tenant_id,
            draft_id=request.draft_id,
            idempotency_key=request.idempotency_key,
            expected_version=request.expected_version,
        )
    except Exception as exc:
        raise _map_service_error(exc)


@router.post(
    "/{draft_id}/confirm",
    response_model=DraftConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Draft Order (RESTful)",
    description="Explicitly confirms a draft order by draft_id in the URL path.",
)
def confirm_draft_restful(
    draft_id: str,
    request: Optional[DraftConfirmRequest] = None,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_CONFIRM)),
) -> DraftConfirmResponse:
    _verify_customer_ownership(draft_id=draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    idemp_key = request.idempotency_key if request else None
    exp_version = request.expected_version if request else None
    service = DraftService(db)
    try:
        return service.confirm_draft(
            tenant_id=authorized_tenant_id,
            draft_id=draft_id,
            idempotency_key=idemp_key,
            expected_version=exp_version,
        )
    except Exception as exc:
        raise _map_service_error(exc)


# ─────────────────────────────────────────────────────────────
#  Cancel Draft
# ─────────────────────────────────────────────────────────────

@router.post(
    "/cancel",
    response_model=DraftCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Draft Order (Node.js Compatible)",
    description="Cancels a draft order. Reverts reserved inventory if previously confirmed.",
)
def cancel_draft_compat(
    request: DraftCancelRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_CANCEL)),
) -> DraftCancelResponse:
    if not request.draft_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="draftId is required in cancellation payload.",
        )

    _verify_customer_ownership(draft_id=request.draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    service = DraftService(db)
    try:
        return service.cancel_draft(
            tenant_id=authorized_tenant_id,
            draft_id=request.draft_id,
            reason=request.reason,
        )
    except Exception as exc:
        raise _map_service_error(exc)


@router.post(
    "/{draft_id}/cancel",
    response_model=DraftCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Draft Order (RESTful)",
    description="Cancels a draft order by draft_id in the URL path.",
)
def cancel_draft_restful(
    draft_id: str,
    request: Optional[DraftCancelRequest] = None,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.DRAFT_CANCEL)),
) -> DraftCancelResponse:
    _verify_customer_ownership(draft_id=draft_id, tenant_id=authorized_tenant_id, principal=principal, db=db)
    reason = request.reason if request else None
    service = DraftService(db)
    try:
        return service.cancel_draft(
            tenant_id=authorized_tenant_id,
            draft_id=draft_id,
            reason=reason,
        )
    except Exception as exc:
        raise _map_service_error(exc)
