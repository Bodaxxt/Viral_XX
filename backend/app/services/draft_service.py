"""
Draft Order Service
Encapsulates domain logic for order draft lifecycle, pricing calculations,
stock reservation, explicit confirmation gates, and state-transition safety.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.db.models import OrderDraft, Tenant, Product, Inventory
from backend.app.repositories.draft_repository import DraftRepository
from backend.app.repositories.tenant_repository import TenantRepository
from backend.app.repositories.product_repository import ProductRepository
from backend.app.schemas.draft import (
    DraftItemRequest,
    DraftItemResponse,
    DraftCreateRequest,
    DraftUpdateRequest,
    DraftResponse,
    DraftConfirmResponse,
    DraftCancelResponse,
)
from backend.app.core.logging import logger


class DraftServiceError(Exception):
    """Base error for draft service exceptions."""
    pass


class TenantNotFoundError(DraftServiceError):
    pass


class DraftNotFoundError(DraftServiceError):
    pass


class CrossTenantAccessError(DraftServiceError):
    pass


class InvalidStateTransitionError(DraftServiceError):
    pass


class InsufficientStockError(DraftServiceError):
    def __init__(self, message: str, available_stock: int = 0):
        super().__init__(message)
        self.available_stock = available_stock


class ProductNotFoundError(DraftServiceError):
    pass


class DraftService:
    def __init__(self, db: Session):
        self.db = db
        self.draft_repo = DraftRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.product_repo = ProductRepository(db)

    # ─────────────────────────────────────────────────────────────
    #  Pricing Engine (Trusted Server-Side Calculation)
    # ─────────────────────────────────────────────────────────────

    def calculate_price(
        self,
        tenant_id: str,
        items: List[DraftItemRequest],
        discount_code: Optional[str] = None,
        apply_shipping: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """
        Deterministically recalculates totals using trusted database product records.
        Never relies on client-submitted prices or totals.
        """
        if not items:
            raise DraftServiceError("At least one item is required for price calculation.")

        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        subtotal = 0.0
        validated_items: List[Dict[str, Any]] = []

        for req_item in items:
            if req_item.quantity <= 0:
                continue

            # Fetch product strictly scoped to this tenant
            product_row = (
                self.db.query(Product)
                .filter(Product.tenant_id == tenant_id)
                .filter(
                    (Product.id == req_item.product_id) | (Product.sku == req_item.product_id)
                )
                .first()
            )
            if not product_row:
                raise ProductNotFoundError(
                    f"Product '{req_item.product_id}' does not exist in workspace '{tenant_id}'."
                )

            item_subtotal = float(product_row.base_price) * req_item.quantity
            subtotal += item_subtotal
            validated_items.append({
                "product_id": product_row.id,
                "sku": product_row.sku,
                "name": product_row.name,
                "name_ar": product_row.name_ar,
                "unit_price": float(product_row.base_price),
                "quantity": req_item.quantity,
                "total": item_subtotal,
                "currency": product_row.currency,
            })

        # Tenant-specific pricing rules
        discount_amount = 0.0
        if discount_code and discount_code.strip().upper() == "VIRALX10":
            discount_amount = round(subtotal * 0.10, 2)

        tax_amount = 0.0
        deposit_required = 0.0
        shipping_fee = 0.0

        if tenant.category == "jewelry":
            # 0% sales tax, insured courier free over 20,000 QAR or 250 QAR
            if apply_shipping and subtotal < 20000:
                shipping_fee = 250.0
            tax_amount = 0.0
        elif tenant.category == "restaurant":
            # Cairo Fine Dining: 14% VAT; 500 EGP deposit per guest
            total_guests = sum(it["quantity"] for it in validated_items)
            deposit_required = float(total_guests * 500)
            tax_amount = round(subtotal * 0.14, 2)
        elif tenant.category == "healthcare":
            # Healthcare: 14% Clinical administration VAT
            tax_amount = round(subtotal * 0.14, 2)

        total_amount = max(0.0, subtotal - discount_amount + tax_amount + shipping_fee)

        return {
            "subtotal": subtotal,
            "discount_code": discount_code.strip() if discount_code else None,
            "discount_amount": discount_amount,
            "tax_amount": tax_amount,
            "deposit_required": deposit_required,
            "shipping_fee": shipping_fee,
            "total_amount": total_amount,
            "currency": tenant.currency,
            "items": validated_items,
        }

    # ─────────────────────────────────────────────────────────────
    #  Create Draft
    # ─────────────────────────────────────────────────────────────

    def create_draft(
        self,
        tenant_id: str,
        items: List[DraftItemRequest],
        session_id: Optional[str] = None,
        customer_notes: Optional[str] = "",
        draft_type: Optional[str] = None,
        discount_code: Optional[str] = None,
        apply_shipping: Optional[bool] = False,
        actor: str = "customer",
    ) -> DraftResponse:
        """
        Creates a stateful, non-binding draft order.
        Never confirms or reserves stock immediately.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")

        # Recompute totals and validate items
        pricing = self.calculate_price(
            tenant_id=tenant_id,
            items=items,
            discount_code=discount_code,
            apply_shipping=apply_shipping,
        )

        # Validate inventory availability (without reservation)
        for it in pricing["items"]:
            inv = self.draft_repo.get_inventory(tenant_id, it["product_id"])
            if inv and inv.stock_count < it["quantity"]:
                self.draft_repo.record_bi_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    event_type="OUT_OF_STOCK_DETECTED",
                    category="drafting",
                    outcome="insufficient_stock",
                    metadata={
                        "product_id": it["product_id"],
                        "requested_quantity": it["quantity"],
                        "available_stock": inv.stock_count,
                    },
                )
                raise InsufficientStockError(
                    f"Item '{it['name']}' cannot be drafted. Insufficient stock "
                    f"(Requested: {it['quantity']}, In stock: {inv.stock_count}).",
                    available_stock=inv.stock_count,
                )

        sid = session_id or f"ses-{uuid.uuid4().hex[:12]}"
        self.draft_repo.ensure_session(sid, tenant_id)

        cat_prefix = (tenant.category or "gen")[:3].upper()
        draft_id = f"DRF-{cat_prefix}-{int(time.time()*1000):X}"

        resolved_draft_type = (
            draft_type
            or ("table_booking" if tenant.category == "restaurant" else "product_order")
        )

        draft = OrderDraft(
            id=draft_id,
            session_id=sid,
            tenant_id=tenant_id,
            status="draft",
            draft_type=resolved_draft_type,
            items_json=json.dumps(pricing["items"]),
            subtotal=pricing["subtotal"],
            discount_amount=pricing["discount_amount"],
            tax_amount=pricing["tax_amount"],
            deposit_required=pricing["deposit_required"],
            total_amount=pricing["total_amount"],
            currency=tenant.currency,
            customer_notes=customer_notes or "",
            idempotency_key=f"IDEMP-{draft_id}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)

        # Audit log
        self.draft_repo.log_audit(
            tenant_id=tenant_id,
            session_id=sid,
            action="DRAFT_CREATED",
            actor=actor,
            details={
                "draft_id": draft_id,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
            },
        )
        self.draft_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=sid,
            event_type="DRAFT_CREATED",
            category=draft.draft_type,
            draft_id=draft_id,
            outcome="draft_prepared",
            metadata={
                "total_amount": draft.total_amount,
                "currency": draft.currency,
                "items_count": len(pricing["items"]),
                "deposit_required": draft.deposit_required,
            },
        )

        return self._format_draft_response(draft)

    # ─────────────────────────────────────────────────────────────
    #  Retrieve Draft
    # ─────────────────────────────────────────────────────────────

    def get_draft(self, tenant_id: str, draft_id: str) -> DraftResponse:
        """
        Retrieves a draft ensuring strict multi-tenant boundary isolation.
        """
        draft = self.draft_repo.get_by_id_and_tenant(draft_id, tenant_id)
        if not draft:
            # Check if draft exists under another tenant to detect cross-tenant breach
            other_draft = self.draft_repo.get_by_id_any_tenant(draft_id)
            if other_draft and other_draft.tenant_id != tenant_id:
                raise CrossTenantAccessError(
                    f"Unauthorized: draft '{draft_id}' belongs to another tenant workspace."
                )
            raise DraftNotFoundError(f"Draft '{draft_id}' not found.")

        return self._format_draft_response(draft)

    # ─────────────────────────────────────────────────────────────
    #  Update Draft
    # ─────────────────────────────────────────────────────────────

    def update_draft(
        self,
        tenant_id: str,
        draft_id: str,
        items: List[DraftItemRequest],
        customer_notes: Optional[str] = None,
        discount_code: Optional[str] = None,
        apply_shipping: Optional[bool] = False,
        actor: str = "customer",
    ) -> DraftResponse:
        """
        Modifies items and customer notes on an existing draft.
        Rejects modifications if the draft is already confirmed or cancelled.
        """
        draft = self.draft_repo.get_by_id_and_tenant(draft_id, tenant_id)
        if not draft:
            other_draft = self.draft_repo.get_by_id_any_tenant(draft_id)
            if other_draft and other_draft.tenant_id != tenant_id:
                raise CrossTenantAccessError(
                    f"Unauthorized: draft '{draft_id}' belongs to another tenant workspace."
                )
            raise DraftNotFoundError(f"Draft '{draft_id}' not found.")

        if draft.status != "draft":
            raise InvalidStateTransitionError(
                f"Cannot modify draft in status: '{draft.status}'."
            )

        # Recalculate prices with trusted product data
        pricing = self.calculate_price(
            tenant_id=tenant_id,
            items=items,
            discount_code=discount_code,
            apply_shipping=apply_shipping,
        )

        # Re-check inventory
        for it in pricing["items"]:
            inv = self.draft_repo.get_inventory(tenant_id, it["product_id"])
            if inv and inv.stock_count < it["quantity"]:
                self.draft_repo.record_bi_event(
                    tenant_id=tenant_id,
                    session_id=draft.session_id,
                    event_type="OUT_OF_STOCK_DETECTED",
                    category="draft_update",
                    outcome="insufficient_stock",
                    metadata={
                        "product_id": it["product_id"],
                        "requested_quantity": it["quantity"],
                        "available_stock": inv.stock_count,
                    },
                )
                raise InsufficientStockError(
                    f"Item '{it['name']}' insufficient stock "
                    f"(Requested: {it['quantity']}, Available: {inv.stock_count}).",
                    available_stock=inv.stock_count,
                )

        draft.items_json = json.dumps(pricing["items"])
        draft.subtotal = pricing["subtotal"]
        draft.discount_amount = pricing["discount_amount"]
        draft.tax_amount = pricing["tax_amount"]
        draft.deposit_required = pricing["deposit_required"]
        draft.total_amount = pricing["total_amount"]
        if customer_notes is not None:
            draft.customer_notes = customer_notes
        draft.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(draft)

        self.draft_repo.log_audit(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            action="DRAFT_UPDATED",
            actor=actor,
            details={
                "draft_id": draft_id,
                "total_amount": draft.total_amount,
                "items_count": len(pricing["items"]),
            },
        )
        self.draft_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            event_type="DRAFT_UPDATED",
            category=draft.draft_type,
            draft_id=draft_id,
            outcome="draft_updated",
            metadata={
                "total_amount": draft.total_amount,
                "currency": draft.currency,
                "items_count": len(pricing["items"]),
            },
        )

        return self._format_draft_response(draft)

    # ─────────────────────────────────────────────────────────────
    #  Explicit Confirmation Gate
    # ─────────────────────────────────────────────────────────────

    def confirm_draft(
        self,
        tenant_id: str,
        draft_id: str,
        idempotency_key: Optional[str] = None,
        expected_version: Optional[str] = None,
        actor: str = "customer",
    ) -> DraftConfirmResponse:
        """
        Executes explicit, verified draft confirmation.
        Safeguards:
        - Atomic SQLite transaction.
        - Idempotency check: duplicate confirmations return the confirmed draft without double-reserving stock.
        - Terminal state check: cancelled drafts cannot be confirmed.
        - Real-time stock revalidation before reservation.
        - Decrements stock_count and increments reserved_count atomically.
        - Emits unique external confirmation reference.
        """
        draft = self.draft_repo.get_by_id_and_tenant(draft_id, tenant_id)
        if not draft:
            other_draft = self.draft_repo.get_by_id_any_tenant(draft_id)
            if other_draft and other_draft.tenant_id != tenant_id:
                raise CrossTenantAccessError(
                    f"Unauthorized: draft '{draft_id}' belongs to another tenant workspace."
                )
            raise DraftNotFoundError(f"Draft '{draft_id}' does not exist.")

        # Idempotency check: if already confirmed, return success without double-decrement
        if draft.status == "confirmed":
            formatted = self._format_draft_response(draft)
            return DraftConfirmResponse(
                success=True,
                already_confirmed=True,
                alreadyConfirmed=True,
                external_reference=draft.external_reference or "ALREADY-CONFIRMED",
                draft=formatted,
                message="This order draft was previously confirmed.",
            )

        if draft.status == "cancelled":
            raise InvalidStateTransitionError("Cannot confirm a cancelled draft order.")

        if draft.status != "draft":
            raise InvalidStateTransitionError(f"Cannot confirm draft in status: '{draft.status}'.")

        # Parse stored items
        try:
            items_list = json.loads(draft.items_json)
        except Exception:
            items_list = []

        # Atomic transaction block
        try:
            # 1. Revalidate live stock availability for all items
            for it in items_list:
                inv = self.draft_repo.get_inventory(tenant_id, it["product_id"])
                if inv and inv.stock_count < it["quantity"]:
                    raise InsufficientStockError(
                        f"Item \"{it.get('name', it['product_id'])}\" is out of stock "
                        f"(Available: {inv.stock_count}, Requested: {it['quantity']}). "
                        f"Cannot confirm draft.",
                        available_stock=inv.stock_count,
                    )

            # 2. Decrement inventory atomically
            for it in items_list:
                inv = self.draft_repo.get_inventory(tenant_id, it["product_id"])
                if inv:
                    inv.stock_count = inv.stock_count - it["quantity"]
                    inv.reserved_count = inv.reserved_count + it["quantity"]
                    self.db.add(inv)

            # 3. Generate external confirmation reference
            tenant_prefix = tenant_id[:3].upper()
            external_ref = f"CONF-{tenant_prefix}-{int(time.time()*1000):X}"

            now_utc = datetime.now(timezone.utc)
            draft.status = "confirmed"
            draft.external_reference = external_ref
            draft.confirmed_at = now_utc
            draft.updated_at = now_utc
            if idempotency_key:
                draft.idempotency_key = idempotency_key

            self.db.commit()
            self.db.refresh(draft)

        except Exception:
            self.db.rollback()
            raise

        # Audit log
        self.draft_repo.log_audit(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            action="DRAFT_CONFIRMED",
            actor=actor,
            details={
                "draft_id": draft_id,
                "external_reference": external_ref,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
            },
        )

        # Telemetry
        self.draft_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            event_type="DRAFT_CONFIRMED",
            category=draft.draft_type,
            draft_id=draft_id,
            outcome="success",
            idempotency_key=idempotency_key or f"EVT-CONF-{draft_id}",
            metadata={
                "external_reference": external_ref,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
                "items_count": len(items_list),
            },
        )

        formatted = self._format_draft_response(draft)
        return DraftConfirmResponse(
            success=True,
            already_confirmed=False,
            alreadyConfirmed=False,
            external_reference=external_ref,
            draft=formatted,
            message="Draft confirmed successfully. Inventory reserved and transmitted to merchant fulfillment.",
        )

    # ─────────────────────────────────────────────────────────────
    #  Cancel Draft
    # ─────────────────────────────────────────────────────────────

    def cancel_draft(
        self,
        tenant_id: str,
        draft_id: str,
        reason: Optional[str] = None,
        actor: str = "customer",
    ) -> DraftCancelResponse:
        """
        Cancels an eligible draft. If previously confirmed, restores inventory.
        """
        draft = self.draft_repo.get_by_id_and_tenant(draft_id, tenant_id)
        if not draft:
            other_draft = self.draft_repo.get_by_id_any_tenant(draft_id)
            if other_draft and other_draft.tenant_id != tenant_id:
                raise CrossTenantAccessError(
                    f"Unauthorized: draft '{draft_id}' belongs to another tenant workspace."
                )
            raise DraftNotFoundError("Draft not found")

        # Idempotent if already cancelled
        if draft.status == "cancelled":
            formatted = self._format_draft_response(draft)
            return DraftCancelResponse(
                success=True,
                draft=formatted,
                message="Draft order is already cancelled.",
            )

        try:
            # If draft was confirmed, restore inventory
            if draft.status == "confirmed":
                try:
                    items_list = json.loads(draft.items_json)
                except Exception:
                    items_list = []

                for it in items_list:
                    inv = self.draft_repo.get_inventory(tenant_id, it["product_id"])
                    if inv:
                        inv.stock_count = inv.stock_count + it["quantity"]
                        inv.reserved_count = max(0, inv.reserved_count - it["quantity"])
                        self.db.add(inv)

            draft.status = "cancelled"
            draft.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(draft)

        except Exception:
            self.db.rollback()
            raise

        self.draft_repo.log_audit(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            action="DRAFT_CANCELLED",
            actor=actor,
            details={"draft_id": draft_id, "reason": reason or "User cancellation"},
        )
        self.draft_repo.record_bi_event(
            tenant_id=tenant_id,
            session_id=draft.session_id,
            event_type="DRAFT_CANCELLED",
            category=draft.draft_type,
            draft_id=draft_id,
            outcome="cancelled",
            metadata={
                "previous_status": draft.status,
                "total_amount": draft.total_amount,
            },
        )

        formatted = self._format_draft_response(draft)
        return DraftCancelResponse(
            success=True,
            draft=formatted,
            message="Draft order has been cancelled.",
        )

    # ─────────────────────────────────────────────────────────────
    #  Helper Formatter
    # ─────────────────────────────────────────────────────────────

    def _format_draft_response(self, draft: OrderDraft) -> DraftResponse:
        try:
            raw_items = json.loads(draft.items_json) if draft.items_json else []
        except Exception:
            raw_items = []

        item_responses: List[DraftItemResponse] = []
        for it in raw_items:
            item_responses.append(
                DraftItemResponse(
                    product_id=it.get("product_id", ""),
                    sku=it.get("sku"),
                    name=it.get("name", ""),
                    name_ar=it.get("name_ar"),
                    unit_price=float(it.get("unit_price", 0.0)),
                    quantity=int(it.get("quantity", 1)),
                    total=float(it.get("total", 0.0)),
                    currency=it.get("currency", draft.currency),
                )
            )

        return DraftResponse(
            id=draft.id,
            session_id=draft.session_id,
            tenant_id=draft.tenant_id,
            status=draft.status,
            draft_type=draft.draft_type,
            items=item_responses,
            subtotal=draft.subtotal,
            discount_amount=draft.discount_amount or 0.0,
            tax_amount=draft.tax_amount or 0.0,
            deposit_required=draft.deposit_required or 0.0,
            total_amount=draft.total_amount,
            currency=draft.currency,
            customer_notes=draft.customer_notes or "",
            idempotency_key=draft.idempotency_key,
            external_reference=draft.external_reference,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            confirmed_at=draft.confirmed_at,
        )
