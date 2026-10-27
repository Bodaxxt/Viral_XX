"""
Order and Booking Draft Schemas
Strict Pydantic v2 schemas for draft lifecycle, line items, and confirmation gates.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DraftItemRequest(BaseModel):
    product_id: str = Field(..., alias="productId", min_length=1, max_length=100, description="Product ID or SKU")
    quantity: int = Field(..., ge=1, le=1000, description="Purchased quantity (must be >= 1)")

    model_config = ConfigDict(populate_by_name=True)


class DraftItemResponse(BaseModel):
    product_id: str = Field(..., alias="productId")
    sku: Optional[str] = None
    name: str
    name_ar: Optional[str] = None
    unit_price: float = Field(..., alias="unitPrice")
    quantity: int
    total: float
    currency: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DraftCreateRequest(BaseModel):
    tenant_id: Optional[str] = Field(default=None, alias="tenantId", max_length=100)
    session_id: Optional[str] = Field(default=None, alias="sessionId", max_length=150)
    items: List[DraftItemRequest] = Field(..., min_length=1, description="List of items to include in draft")
    customer_notes: Optional[str] = Field(default="", alias="customerNotes", max_length=1000)
    draft_type: Optional[str] = Field(
        default=None,
        alias="draftType",
        description="One of: 'product_order', 'table_booking', 'clinical_consultation'"
    )
    discount_code: Optional[str] = Field(default=None, alias="discountCode", max_length=50)
    apply_shipping: Optional[bool] = Field(default=False, alias="applyShipping")

    model_config = ConfigDict(populate_by_name=True)


class DraftUpdateRequest(BaseModel):
    items: List[DraftItemRequest] = Field(..., min_length=1, description="Complete updated item list")
    customer_notes: Optional[str] = Field(default=None, alias="customerNotes", max_length=1000)
    discount_code: Optional[str] = Field(default=None, alias="discountCode", max_length=50)
    apply_shipping: Optional[bool] = Field(default=False, alias="applyShipping")

    model_config = ConfigDict(populate_by_name=True)



class DraftConfirmRequest(BaseModel):
    draft_id: Optional[str] = Field(default=None, alias="draftId", max_length=150)
    idempotency_key: Optional[str] = Field(default=None, alias="idempotencyKey", max_length=150)
    expected_version: Optional[str] = Field(
        default=None,
        description="Optional version or hash of draft for optimistic concurrency check"
    )

    model_config = ConfigDict(populate_by_name=True)


class DraftCancelRequest(BaseModel):
    draft_id: Optional[str] = Field(default=None, alias="draftId", max_length=150)
    reason: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(populate_by_name=True)


class DraftResponse(BaseModel):
    id: str = Field(..., description="Unique draft order ID")
    session_id: str
    tenant_id: str
    status: str = Field(..., description="'draft', 'confirmed', or 'cancelled'")
    draft_type: str
    items: List[DraftItemResponse]
    subtotal: float
    discount_amount: float
    tax_amount: float
    deposit_required: float
    total_amount: float
    currency: str
    customer_notes: Optional[str] = ""
    idempotency_key: Optional[str] = None
    external_reference: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DraftConfirmResponse(BaseModel):
    success: bool
    already_confirmed: bool = False
    alreadyConfirmed: bool = False
    external_reference: str
    draft: DraftResponse
    message: str

    model_config = ConfigDict(populate_by_name=True)


class DraftCancelResponse(BaseModel):
    success: bool
    draft: DraftResponse
    message: str

    model_config = ConfigDict(populate_by_name=True)
