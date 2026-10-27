"""
Booking Service
Encapsulates domain logic for appointment/dining booking lifecycle, slot availability,
concurrency safety, double-booking prevention, and tenant boundary enforcement.
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import BookingSlot, Tenant
from backend.app.repositories.booking_repository import BookingRepository
from backend.app.repositories.tenant_repository import TenantRepository
from backend.app.schemas.booking import (
    BookingSlotResponse,
    BookingAvailabilityResponse,
    BookingCreateRequest,
    BookingCancelRequest,
    BookingResponse,
)
from backend.app.core.logging import logger


class BookingServiceError(Exception):
    """Base error for booking service exceptions."""
    pass


class TenantNotFoundError(BookingServiceError):
    pass


class SlotNotFoundError(BookingServiceError):
    pass


class CrossTenantAccessError(BookingServiceError):
    pass


class SlotUnavailableError(BookingServiceError):
    pass


class InsufficientCapacityError(BookingServiceError):
    def __init__(self, message: str, available_capacity: int = 0):
        super().__init__(message)
        self.available_capacity = available_capacity


class InvalidStateTransitionError(BookingServiceError):
    pass


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.tenant_repo = TenantRepository(db)

    # In-memory deduplication set for idempotency in the current runtime
    _processed_idempotency_keys: Dict[str, Dict[str, Any]] = {}

    def get_availability(
        self,
        tenant_id: str,
        date: Optional[str] = None,
        service_type: Optional[str] = None,
    ) -> BookingAvailabilityResponse:
        """
        Retrieves real-time available booking slots for a tenant based on database state.
        Never hallucinates or invents slots.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        slots = self.booking_repo.list_slots(
            tenant_id=tenant_id,
            slot_date=date,
            service_type=service_type,
            available_only=True,
        )

        response_slots = []
        for s in slots:
            available = max(0, s.capacity - s.booked_count)
            response_slots.append(
                BookingSlotResponse(
                    id=s.id,
                    tenant_id=s.tenant_id,
                    slot_date=s.slot_date,
                    slot_time=s.slot_time,
                    service_type=s.service_type,
                    capacity=s.capacity,
                    booked_count=s.booked_count,
                    available_capacity=available,
                    status=s.status,
                )
            )

        return BookingAvailabilityResponse(
            count=len(response_slots),
            tenant_id=tenant_id,
            slots=response_slots,
        )

    def get_slot(self, tenant_id: str, slot_id: str) -> BookingSlotResponse:
        """
        Retrieves a single booking slot strictly scoped to tenant.
        Raises CrossTenantAccessError if the slot belongs to another tenant.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        slot = self.booking_repo.get_by_id_and_tenant(slot_id, tenant_id)
        if not slot:
            other_slot = self.booking_repo.get_by_id_any_tenant(slot_id)
            if other_slot:
                raise CrossTenantAccessError(
                    f"Cross-tenant access violation: Slot '{slot_id}' belongs to tenant "
                    f"'{other_slot.tenant_id}', not '{tenant_id}'."
                )
            raise SlotNotFoundError(f"Booking slot '{slot_id}' not found for tenant '{tenant_id}'.")

        available = max(0, slot.capacity - slot.booked_count)
        return BookingSlotResponse(
            id=slot.id,
            tenant_id=slot.tenant_id,
            slot_date=slot.slot_date,
            slot_time=slot.slot_time,
            service_type=slot.service_type,
            capacity=slot.capacity,
            booked_count=slot.booked_count,
            available_capacity=available,
            status=slot.status,
        )

    def create_booking(
        self,
        tenant_id: str,
        request: BookingCreateRequest,
        actor: str = "customer",
    ) -> BookingResponse:
        """
        Reserves a booking slot with atomic concurrency protection.
        Prevents double-booking even under concurrent parallel requests.
        Never reports success before the database operation succeeds.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        # Idempotency check
        if request.idempotency_key and request.idempotency_key in self._processed_idempotency_keys:
            cached = self._processed_idempotency_keys[request.idempotency_key]
            if cached.get("tenant_id") == tenant_id:
                return BookingResponse(**cached)

        # 1. Enforce slot tenant boundary
        slot_info = self.get_slot(tenant_id, request.slot_id)

        # 2. Check current status
        if slot_info.status != "available":
            raise SlotUnavailableError(
                f"Booking slot '{request.slot_id}' is currently '{slot_info.status}' and cannot accept reservations."
            )

        if slot_info.available_capacity < request.party_size:
            raise InsufficientCapacityError(
                f"Requested party size {request.party_size} exceeds remaining capacity "
                f"({slot_info.available_capacity} seats available).",
                available_capacity=slot_info.available_capacity,
            )

        # 3. Execute atomic reservation query directly in the DB
        reserved = self.booking_repo.atomic_reserve_capacity(
            slot_id=request.slot_id,
            tenant_id=tenant_id,
            party_size=request.party_size,
        )

        if not reserved:
            # Recheck to give accurate reason
            latest_slot = self.booking_repo.get_by_id_and_tenant(request.slot_id, tenant_id)
            if not latest_slot or latest_slot.status != "available":
                raise SlotUnavailableError(
                    f"Booking slot '{request.slot_id}' became unavailable during booking."
                )
            latest_available = max(0, latest_slot.capacity - latest_slot.booked_count)
            raise InsufficientCapacityError(
                f"Booking race condition prevented: Only {latest_available} seats remaining. Cannot book {request.party_size}.",
                available_capacity=latest_available,
            )

        # 4. Generate external reference
        ext_ref = f"BKG-{tenant_id[:3].upper()}-{hex(int(time.time() * 1000))[2:].upper()}"
        booking_id = f"RES-{uuid.uuid4().hex[:8].upper()}"

        # 5. Audit log
        self.booking_repo.log_audit(
            tenant_id=tenant_id,
            session_id=request.session_id,
            action="SLOT_RESERVED",
            actor=actor,
            details={
                "booking_id": booking_id,
                "slot_id": request.slot_id,
                "party_size": request.party_size,
                "customer_name": request.customer_name,
                "external_reference": ext_ref,
            },
        )

        # 6. BI event
        self.booking_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=request.session_id,
            event_type="BOOKING_RESERVED",
            category="booking",
            outcome="success",
            metadata={
                "slot_id": request.slot_id,
                "party_size": request.party_size,
                "external_reference": ext_ref,
            },
            idempotency_key=request.idempotency_key,
        )

        # Reload slot to get updated status
        updated_slot = self.booking_repo.get_by_id_and_tenant(request.slot_id, tenant_id)
        current_status = updated_slot.status if updated_slot else "available"

        response_data = {
            "success": True,
            "booking_id": booking_id,
            "slot_id": request.slot_id,
            "tenant_id": tenant_id,
            "slot_date": slot_info.slot_date,
            "slot_time": slot_info.slot_time,
            "service_type": slot_info.service_type,
            "party_size": request.party_size,
            "status": current_status,
            "already_booked": False,
            "external_reference": ext_ref,
            "message": f"Slot successfully reserved for {request.party_size} guests.",
        }

        if request.idempotency_key:
            self._processed_idempotency_keys[request.idempotency_key] = response_data

        return BookingResponse(**response_data)

    def cancel_booking(
        self,
        tenant_id: str,
        request: BookingCancelRequest,
        actor: str = "customer",
    ) -> BookingResponse:
        """
        Releases reserved slot capacity and restores availability.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        slot_info = self.get_slot(tenant_id, request.slot_id)

        # Atomic release
        self.booking_repo.atomic_release_capacity(
            slot_id=request.slot_id,
            tenant_id=tenant_id,
            party_size=request.party_size,
        )

        # Audit log
        self.booking_repo.log_audit(
            tenant_id=tenant_id,
            session_id=request.session_id,
            action="SLOT_CANCELLED",
            actor=actor,
            details={
                "slot_id": request.slot_id,
                "party_size": request.party_size,
                "reason": request.reason,
                "booking_reference": request.booking_reference,
            },
        )

        # BI event
        self.booking_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=request.session_id,
            event_type="BOOKING_CANCELLED",
            category="booking",
            outcome="cancelled",
            metadata={
                "slot_id": request.slot_id,
                "party_size": request.party_size,
                "reason": request.reason,
            },
        )

        updated_slot = self.booking_repo.get_by_id_and_tenant(request.slot_id, tenant_id)
        current_status = updated_slot.status if updated_slot else "available"

        return BookingResponse(
            success=True,
            booking_id=request.booking_reference or "CANCELLED",
            slot_id=request.slot_id,
            tenant_id=tenant_id,
            slot_date=slot_info.slot_date,
            slot_time=slot_info.slot_time,
            service_type=slot_info.service_type,
            party_size=request.party_size,
            status=current_status,
            already_booked=False,
            external_reference=request.booking_reference,
            message="Booking reservation successfully cancelled and slot released.",
        )
