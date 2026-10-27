"""
Pydantic v2 schemas for Booking Lifecycle, Slot Availability, and Concurrency Protection.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BookingSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    slot_date: str
    slot_time: str
    service_type: str
    capacity: int
    booked_count: int
    available_capacity: int
    status: str


class BookingAvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count: int
    tenant_id: str
    slots: List[BookingSlotResponse]


class BookingCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    slot_id: str = Field(..., alias="slotId", min_length=1, description="Unique slot identifier (e.g. SLOT-R01)")
    party_size: int = Field(default=1, alias="partySize", ge=1, le=50, description="Number of guests or participants")
    customer_name: Optional[str] = Field(default=None, alias="customerName", max_length=100)
    customer_phone: Optional[str] = Field(default=None, alias="customerPhone", max_length=30)
    session_id: Optional[str] = Field(default=None, alias="sessionId", max_length=100)
    customer_notes: Optional[str] = Field(default=None, alias="customerNotes", max_length=500)
    idempotency_key: Optional[str] = Field(default=None, alias="idempotencyKey", max_length=100)
    tenant_id: Optional[str] = Field(default=None, alias="tenantId", description="Optional body tenant ID")


class BookingCancelRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    slot_id: str = Field(..., alias="slotId", min_length=1)
    party_size: int = Field(default=1, alias="partySize", ge=1, le=50)
    booking_reference: Optional[str] = Field(default=None, alias="bookingReference", max_length=100)
    session_id: Optional[str] = Field(default=None, alias="sessionId", max_length=100)
    reason: Optional[str] = Field(default=None, max_length=300)
    tenant_id: Optional[str] = Field(default=None, alias="tenantId")


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    booking_id: str
    slot_id: str
    tenant_id: str
    slot_date: str
    slot_time: str
    service_type: str
    party_size: int
    status: str
    already_booked: bool = False
    external_reference: Optional[str] = None
    message: str
