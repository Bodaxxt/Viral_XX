"""
Booking API Endpoints
Provides secure, versioned, tenant-isolated operations for booking slot availability,
reservation with concurrency protection, and cancellation.

Sprint 5: Uses centralized authenticated principal resolution from core.auth.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import AuditLog
from backend.app.core.auth import get_authorized_tenant, get_current_principal, require_permission
from backend.app.schemas.auth import AuthenticatedPrincipal, Permissions
from backend.app.schemas.booking import (
    BookingSlotResponse,
    BookingAvailabilityResponse,
    BookingCreateRequest,
    BookingCancelRequest,
    BookingResponse,
)
from backend.app.services.booking_service import (
    BookingService,
    BookingServiceError,
    TenantNotFoundError,
    SlotNotFoundError,
    CrossTenantAccessError,
    SlotUnavailableError,
    InsufficientCapacityError,
    InvalidStateTransitionError,
)
from backend.app.core.logging import logger

router = APIRouter(prefix="/bookings", tags=["bookings"])



def _map_booking_error(exc: Exception) -> HTTPException:
    """Maps domain service exceptions to safe, structured HTTP exceptions."""
    if isinstance(exc, (SlotNotFoundError, TenantNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CrossTenantAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, (SlotUnavailableError, InsufficientCapacityError, InvalidStateTransitionError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.error("Unhandled booking service error: %s", exc, exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred while processing the booking.",
    )


@router.get(
    "/availability",
    response_model=BookingAvailabilityResponse,
    summary="Query Real-Time Booking Availability",
    description="Returns available booking slots for a tenant based on database state.",
)
def get_availability(
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    tenant_id: Optional[str] = Query(None, description="Optional tenant ID filter"),
    date: Optional[str] = Query(None, description="Date filter in YYYY-MM-DD format"),
    service_type: Optional[str] = Query(None, description="Service or menu type filter"),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.BOOKING_READ)),
) -> BookingAvailabilityResponse:
    if tenant_id and tenant_id.strip() != authorized_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tenant authorization mismatch: query tenant_id '{tenant_id}' "
                f"does not match authorized header '{authorized_tenant_id}'."
            ),
        )
    service = BookingService(db)
    try:
        return service.get_availability(tenant_id=authorized_tenant_id, date=date, service_type=service_type)
    except Exception as exc:
        raise _map_booking_error(exc)


@router.get(
    "/slots/{slot_id}",
    response_model=BookingSlotResponse,
    summary="Retrieve Booking Slot Details",
    description="Fetches verified capacity and status for a specific booking slot.",
)
def get_slot_details(
    slot_id: str,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.BOOKING_READ)),
) -> BookingSlotResponse:
    service = BookingService(db)
    try:
        return service.get_slot(tenant_id=authorized_tenant_id, slot_id=slot_id)
    except Exception as exc:
        raise _map_booking_error(exc)


@router.post(
    "/reserve",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve Booking Slot",
    description="Atomically reserves capacity in a booking slot with concurrency protection.",
)
def reserve_slot(
    request: BookingCreateRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.BOOKING_RESERVE)),
) -> BookingResponse:
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
    if principal.role == "customer":
        if not request.session_id:
            request.session_id = f"cust-{principal.user_id}"
        elif not request.session_id.startswith(f"cust-{principal.user_id}") and request.session_id != principal.user_id:
            request.session_id = f"cust-{principal.user_id}-{request.session_id}"

    service = BookingService(db)
    try:
        return service.create_booking(
            tenant_id=authorized_tenant_id,
            request=request,
            actor="customer",
        )
    except Exception as exc:
        raise _map_booking_error(exc)


@router.post(
    "/cancel",
    response_model=BookingResponse,
    summary="Cancel Booking Reservation",
    description="Cancels a reservation and releases slot capacity back to availability.",
)
def cancel_slot(
    request: BookingCancelRequest,
    authorized_tenant_id: str = Depends(get_authorized_tenant),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.BOOKING_CANCEL)),
) -> BookingResponse:
    if request.tenant_id and request.tenant_id.strip() != authorized_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tenant authorization mismatch: body tenantId '{request.tenant_id}' "
                f"does not match authorized header '{authorized_tenant_id}'."
            ),
        )

    # Customer ownership enforcement: customer cannot cancel another customer's booking
    if principal.role == "customer":
        if not request.session_id and not request.booking_reference:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Customer must provide bookingReference or sessionId to cancel their reservation.",
            )
        if request.session_id:
            is_owner = (
                request.session_id == principal.user_id
                or request.session_id == f"cust-{principal.user_id}"
                or request.session_id.startswith(f"cust-{principal.user_id}-")
            )
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Customer cannot cancel another customer's booking reservation.",
                )
        if request.booking_reference:
            audit_record = (
                db.query(AuditLog)
                .filter(
                    AuditLog.tenant_id == authorized_tenant_id,
                    AuditLog.action == "SLOT_RESERVED",
                    AuditLog.details_json.like(f"%{request.booking_reference}%"),
                )
                .first()
            )
            if audit_record and audit_record.session_id:
                is_owner = (
                    audit_record.session_id == principal.user_id
                    or audit_record.session_id == f"cust-{principal.user_id}"
                    or audit_record.session_id.startswith(f"cust-{principal.user_id}-")
                )
                if not is_owner and audit_record.session_id.startswith("cust-"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: Customer cannot cancel another customer's booking reservation.",
                    )

    service = BookingService(db)
    try:
        return service.cancel_booking(
            tenant_id=authorized_tenant_id,
            request=request,
            actor="customer",
        )
    except Exception as exc:
        raise _map_booking_error(exc)
