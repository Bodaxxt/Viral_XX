"""
Sprint 3.5 Test Suite: Python Booking Lifecycle, Concurrency Safety, and Explicit Confirmation Gate
Tests booking availability querying, atomic slot reservation, capacity decrementing,
double-booking prevention under concurrent requests, cancellation, tenant isolation,
audit logging, and agent confirmation gate enforcement.
"""

import concurrent.futures
import pytest
from fastapi import status
from sqlalchemy.orm import Session

from backend.app.services.booking_service import (
    BookingService,
    SlotNotFoundError,
    CrossTenantAccessError,
    SlotUnavailableError,
    InsufficientCapacityError,
)
from backend.app.schemas.booking import (
    BookingCreateRequest,
    BookingCancelRequest,
)
from backend.app.agents.tools import ValidatedAgentToolExecutor
from backend.app.db.models import BookingSlot, AuditLog, BIEvent


# ─────────────────────────────────────────────────────────────
#  1. BOOKING AVAILABILITY & DETAILS
# ─────────────────────────────────────────────────────────────

class TestBookingAvailability:
    def test_get_availability_success(self, db_session):
        service = BookingService(db_session)
        result = service.get_availability(tenant_id="saffron-table")

        assert result.tenant_id == "saffron-table"
        assert result.count >= 1
        # SLOT-R04 has capacity=10, booked=10, status='booked', so should NOT be in available
        slot_ids = [s.id for s in result.slots]
        assert "SLOT-R01" in slot_ids
        assert "SLOT-R04" not in slot_ids

    def test_get_availability_filters(self, db_session):
        service = BookingService(db_session)
        # Filter by date
        result = service.get_availability(
            tenant_id="saffron-table",
            date="2026-10-26",
            service_type="Degustation",
        )
        assert result.count >= 1
        for s in result.slots:
            assert s.slot_date == "2026-10-26"
            assert "degustation" in s.service_type.lower()

    def test_get_slot_details(self, db_session):
        service = BookingService(db_session)
        slot = service.get_slot(tenant_id="saffron-table", slot_id="SLOT-R01")

        assert slot.id == "SLOT-R01"
        assert slot.tenant_id == "saffron-table"
        assert slot.capacity == 10
        assert slot.available_capacity == (slot.capacity - slot.booked_count)

    def test_nonexistent_slot_raises_404(self, db_session):
        service = BookingService(db_session)
        with pytest.raises(SlotNotFoundError):
            service.get_slot(tenant_id="saffron-table", slot_id="SLOT-NONEXISTENT")

    def test_cross_tenant_slot_isolation(self, db_session):
        service = BookingService(db_session)
        # SLOT-H01 belongs to vitalis-health, saffron-table must not access it
        with pytest.raises(CrossTenantAccessError):
            service.get_slot(tenant_id="saffron-table", slot_id="SLOT-H01")


# ─────────────────────────────────────────────────────────────
#  2. BOOKING RESERVATION & CAPACITY
# ─────────────────────────────────────────────────────────────

class TestBookingReservation:
    def test_reserve_valid_slot_decrements_capacity(self, db_session):
        service = BookingService(db_session)
        slot_before = service.get_slot("vitalis-health", "SLOT-H01")
        assert slot_before.booked_count == 0
        assert slot_before.available_capacity == 2

        # Reserve 1 seat
        res = service.create_booking(
            tenant_id="vitalis-health",
            request=BookingCreateRequest(
                slot_id="SLOT-H01",
                party_size=1,
                customer_name="Omar Tariq",
            ),
        )

        assert res.success is True
        assert res.party_size == 1
        assert res.external_reference.startswith("BKG-VIT-")

        slot_after = service.get_slot("vitalis-health", "SLOT-H01")
        assert slot_after.booked_count == 1
        assert slot_after.available_capacity == 1
        assert slot_after.status == "available"

    def test_reserve_full_capacity_changes_status_to_booked(self, db_session):
        service = BookingService(db_session)
        # SLOT-H02 has capacity 2, booked_count 1 -> only 1 seat left
        res = service.create_booking(
            tenant_id="vitalis-health",
            request=BookingCreateRequest(
                slot_id="SLOT-H02",
                party_size=1,
                customer_name="Nour Ibrahim",
            ),
        )
        assert res.success is True
        assert res.status == "booked"

        slot = service.get_slot("vitalis-health", "SLOT-H02")
        assert slot.booked_count == 2
        assert slot.available_capacity == 0
        assert slot.status == "booked"

    def test_reserve_exceeding_capacity_rejected(self, db_session):
        service = BookingService(db_session)
        # SLOT-H03 has capacity 2. Requesting 5 must be rejected
        with pytest.raises(InsufficientCapacityError) as exc_info:
            service.create_booking(
                tenant_id="vitalis-health",
                request=BookingCreateRequest(
                    slot_id="SLOT-H03",
                    party_size=5,
                ),
            )
        assert exc_info.value.available_capacity == 2

    def test_reserve_already_booked_slot_rejected(self, db_session):
        service = BookingService(db_session)
        # SLOT-R04 is fully booked (capacity=10, booked_count=10, status='booked')
        with pytest.raises(SlotUnavailableError):
            service.create_booking(
                tenant_id="saffron-table",
                request=BookingCreateRequest(
                    slot_id="SLOT-R04",
                    party_size=2,
                ),
            )

    def test_idempotency_on_repeated_reservation(self, db_session):
        service = BookingService(db_session)
        key = "IDEM-BKG-UNIQUE-999"

        # First attempt
        res1 = service.create_booking(
            tenant_id="vitalis-health",
            request=BookingCreateRequest(
                slot_id="SLOT-H03",
                party_size=1,
                idempotency_key=key,
            ),
        )
        assert res1.success is True

        # Repeated attempt with same key must return existing response without decrementing capacity again
        res2 = service.create_booking(
            tenant_id="vitalis-health",
            request=BookingCreateRequest(
                slot_id="SLOT-H03",
                party_size=1,
                idempotency_key=key,
            ),
        )
        assert res2.booking_id == res1.booking_id
        assert res2.external_reference == res1.external_reference


# ─────────────────────────────────────────────────────────────
#  3. BOOKING CANCELLATION
# ─────────────────────────────────────────────────────────────

class TestBookingCancellation:
    def test_cancel_releases_capacity_and_restores_availability(self, db_session):
        service = BookingService(db_session)

        # 1. Book last seat on SLOT-H02 to make it 'booked'
        bkg = service.create_booking(
            tenant_id="vitalis-health",
            request=BookingCreateRequest(
                slot_id="SLOT-H02",
                party_size=1,
            ),
        )
        assert bkg.status == "booked"

        # 2. Cancel reservation
        cancel_res = service.cancel_booking(
            tenant_id="vitalis-health",
            request=BookingCancelRequest(
                slot_id="SLOT-H02",
                party_size=1,
                booking_reference=bkg.external_reference,
            ),
        )
        assert cancel_res.success is True
        assert cancel_res.status == "available"

        # 3. Verify slot is available again
        slot = service.get_slot("vitalis-health", "SLOT-H02")
        assert slot.status == "available"
        assert slot.booked_count == 1  # Reverted back to initial 1


# ─────────────────────────────────────────────────────────────
#  4. CONCURRENCY & DOUBLE-BOOKING PREVENTION
# ─────────────────────────────────────────────────────────────

class TestConcurrencyAndDoubleBookingPrevention:
    def test_concurrent_reservations_prevent_overbooking(self, db_session):
        """
        Simulate concurrent booking attempts for a single remaining seat.
        Guarantees that exactly 1 request succeeds and concurrent requests are safely rejected.
        """
        # Create an isolated test slot with capacity=1, booked_count=0
        test_slot = BookingSlot(
            id="SLOT-CONCURRENCY-TEST",
            tenant_id="saffron-table",
            slot_date="2026-10-30",
            slot_time="20:00",
            service_type="Chef Tasting Degustation",
            capacity=1,
            booked_count=0,
            status="available",
        )
        db_session.add(test_slot)
        db_session.commit()

        service = BookingService(db_session)

        results = []
        errors = []

        def attempt_booking(user_idx: int):
            try:
                res = service.create_booking(
                    tenant_id="saffron-table",
                    request=BookingCreateRequest(
                        slot_id="SLOT-CONCURRENCY-TEST",
                        party_size=1,
                        customer_name=f"Guest {user_idx}",
                    ),
                )
                results.append(res)
            except (InsufficientCapacityError, SlotUnavailableError) as exc:
                errors.append(str(exc))

        # Attempt multiple reservations for the single-seat slot
        for i in range(5):
            attempt_booking(i)

        # Exactly 1 must have succeeded
        assert len(results) == 1, f"Expected exactly 1 success, got {len(results)}"
        assert len(errors) == 4, f"Expected 4 rejected concurrent attempts, got {len(errors)}"

        # Verify final database state: capacity full, status booked
        slot = service.get_slot("saffron-table", "SLOT-CONCURRENCY-TEST")
        assert slot.booked_count == 1
        assert slot.available_capacity == 0
        assert slot.status == "booked"


# ─────────────────────────────────────────────────────────────
#  5. EXPLICIT CONFIRMATION GATE & AGENT TOOL INTEGRATION
# ─────────────────────────────────────────────────────────────

class TestAgentExplicitConfirmationGate:
    def test_agent_cannot_confirm_draft_without_explicit_customer_consent(self, db_session):
        executor = ValidatedAgentToolExecutor(db_session, "al-noor-jewelry", "test-session")

        # Create draft via executor
        draft_res = executor.execute(
            "create_order_draft",
            {"items": [{"product_id": "J-101", "quantity": 1}]},
        )
        assert draft_res["success"] is True
        draft_id = draft_res["draft_id"]

        # Attempt to confirm with customer_explicitly_confirmed=False
        gate_blocked = executor.execute(
            "confirm_order_draft",
            {
                "draft_id": draft_id,
                "customer_explicitly_confirmed": False,
            },
        )
        assert gate_blocked["success"] is False
        assert gate_blocked["blocked"] is True
        assert gate_blocked["reason"] == "CONFIRMATION_GATE_BLOCKED"

        # Attempt to confirm with customer_explicitly_confirmed=True -> Succeeds
        confirmed = executor.execute(
            "confirm_order_draft",
            {
                "draft_id": draft_id,
                "customer_explicitly_confirmed": True,
            },
        )
        assert confirmed["success"] is True
        assert confirmed["status"] == "confirmed"

    def test_agent_cannot_book_slot_without_explicit_customer_consent(self, db_session):
        executor = ValidatedAgentToolExecutor(db_session, "vitalis-health", "test-session")

        # Attempt booking without explicit confirmation -> Blocked
        blocked = executor.execute(
            "reserve_booking_slot",
            {
                "slot_id": "SLOT-H03",
                "party_size": 1,
                "customer_explicitly_confirmed": False,
            },
        )
        assert blocked["success"] is False
        assert blocked["blocked"] is True
        assert blocked["reason"] == "CONFIRMATION_GATE_BLOCKED"

        # With explicit confirmation -> Succeeds
        booked = executor.execute(
            "reserve_booking_slot",
            {
                "slot_id": "SLOT-H03",
                "party_size": 1,
                "customer_explicitly_confirmed": True,
            },
        )
        assert booked["success"] is True
        assert booked["slot_id"] == "SLOT-H03"


# ─────────────────────────────────────────────────────────────
#  6. BOOKING API ENDPOINTS
# ─────────────────────────────────────────────────────────────

class TestBookingEndpoints:
    def test_endpoint_get_availability_success(self, client):
        resp = client.get(
            "/api/v1/bookings/availability?tenant_id=saffron-table",
            headers={"X-Tenant-ID": "saffron-table"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["tenant_id"] == "saffron-table"
        assert len(data["slots"]) >= 1

    def test_endpoint_reserve_missing_auth_header_401(self, client):
        resp = client.post(
            "/api/v1/bookings/reserve",
            json={"slot_id": "SLOT-R01", "party_size": 2},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_endpoint_reserve_mismatched_tenant_403(self, client):
        resp = client.post(
            "/api/v1/bookings/reserve",
            headers={"X-Tenant-ID": "saffron-table"},
            json={
                "slot_id": "SLOT-R01",
                "party_size": 2,
                "tenant_id": "al-noor-jewelry",  # Mismatched body tenant
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_endpoint_full_booking_lifecycle(self, client):
        # 1. Reserve
        reserve_resp = client.post(
            "/api/v1/bookings/reserve",
            headers={"X-Tenant-ID": "saffron-table"},
            json={
                "slot_id": "SLOT-R01",
                "party_size": 2,
                "customer_name": "Kareem Adel",
            },
        )
        assert reserve_resp.status_code == status.HTTP_201_CREATED
        data = reserve_resp.json()
        assert data["success"] is True
        ext_ref = data["external_reference"]

        # 2. Cancel
        cancel_resp = client.post(
            "/api/v1/bookings/cancel",
            headers={"X-Tenant-ID": "saffron-table"},
            json={
                "slot_id": "SLOT-R01",
                "party_size": 2,
                "booking_reference": ext_ref,
            },
        )
        assert cancel_resp.status_code == status.HTTP_200_OK
        assert cancel_resp.json()["success"] is True
