"""
Read-Only Business Tools for Python Agent — Sprint 3
Executes verified, server-side business logic against the SQLite database.

Write-capable tools (create_order_draft, update_order_draft, get_order_draft,
request_human_handoff) are intentionally excluded from this sprint per
Sprint 3 scope constraints.
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.logging import logger


# Tool definitions for LLM function-calling (JSON Schema, matches Node.js TOOL_DEFINITIONS)
READONLY_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search products or service packages by keyword, category, or maximum budget within the current business tenant.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (e.g. emerald, diamond, tasting menu, screening)"},
                "category": {"type": "string", "description": "Product or service category"},
                "max_budget": {"type": "number", "description": "Maximum price/budget filter"},
            },
        },
    },
    {
        "name": "get_product_details",
        "description": "Retrieve verified detailed product or service information, including metal specifications, carats, course lists, or fasting guidelines.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID or SKU (e.g. J-101, R-201, H-301)"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check verified live inventory, stock count, and location from the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID or SKU to check"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "calculate_price",
        "description": "Deterministically calculate subtotal, discounts, taxes, deposits, and total amount using explicit business rules. Never calculate prices in prompt text.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to price",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product_id", "quantity"],
                    },
                },
                "discount_code": {"type": "string", "description": "Optional promo or discount code"},
                "apply_shipping": {"type": "boolean", "description": "Whether GCC courier shipping applies (jewelry)"},
            },
            "required": ["items"],
        },
    },
    {
        "name": "search_business_knowledge",
        "description": "Search official business policies, FAQs, delivery terms, opening hours, allergy accommodation, and medical disclaimers.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term regarding policies, hours, delivery, allergies"},
                "category": {"type": "string", "description": "Category: policy, delivery, hours, authenticity, allergies, preparation"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_booking_availability",
        "description": "Query verified available booking and reservation time slots for dining or clinic appointments.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "service_type": {"type": "string", "description": "Service or menu type"},
            },
        },
    },
]

# Tools that are write-protected (never callable in read-only Sprint 3 context)
WRITE_PROTECTED_TOOLS = frozenset({
    "create_order_draft",
    "update_order_draft",
    "get_order_draft",
})

# Known valid tools in Sprint 3
VALID_READONLY_TOOLS = frozenset(t["name"] for t in READONLY_TOOL_DEFINITIONS)

DISCOUNT_CODES = {"VIRALX10": 0.10}
VAT_RATES = {"restaurant": 0.14, "healthcare": 0.14}
SHIPPING_COST = 250.0


class ReadOnlyToolExecutor:
    """
    Executes all read-only business tools with strict tenant isolation.
    Write-capable tools raise ToolAccessDenied errors so the agent cannot
    mutate the database during Sprint 3.
    """

    def __init__(self, db: Session, tenant_id: str, session_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.session_id = session_id

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name in WRITE_PROTECTED_TOOLS:
            return {
                "available": False,
                "message": (
                    f"Tool '{tool_name}' is write-protected and not available in this session. "
                    "Please proceed through the main production service channel to place orders or escalate."
                ),
            }

        if tool_name not in VALID_READONLY_TOOLS:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            if tool_name == "search_products":
                return self._search_products(**{k: args.get(k) for k in ("query", "category", "max_budget")})
            elif tool_name == "get_product_details":
                return self._get_product_details(args.get("product_id", ""))
            elif tool_name == "check_inventory":
                return self._check_inventory(args.get("product_id", ""))
            elif tool_name == "calculate_price":
                return self._calculate_price(
                    args.get("items", []),
                    args.get("discount_code"),
                    args.get("apply_shipping", False),
                )
            elif tool_name == "search_business_knowledge":
                return self._search_knowledge(args.get("query", ""), args.get("category"))
            elif tool_name == "check_booking_availability":
                return self._check_booking_availability(args.get("date"), args.get("service_type"))
        except Exception as exc:
            logger.error(f"Tool execution error [{tool_name}] for tenant {self.tenant_id}: {exc}")
            return {"error": "Tool execution encountered an error. Please try again."}

        return {"error": f"Tool '{tool_name}' could not be dispatched."}

    def _search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        max_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        sql = """
            SELECT p.id, p.sku, p.name, p.name_ar, p.category, p.base_price, p.currency,
                   p.description, p.attributes_json,
                   i.stock_count, i.reserved_count, i.location as inventory_location
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.tenant_id = :tenant_id AND p.is_active = 1
        """
        params: Dict[str, Any] = {"tenant_id": self.tenant_id}

        if category and category.strip():
            sql += " AND p.category LIKE :category"
            params["category"] = f"%{category.strip()}%"

        if max_budget and float(max_budget) > 0:
            sql += " AND p.base_price <= :max_budget"
            params["max_budget"] = float(max_budget)

        sql += " ORDER BY p.base_price ASC"
        rows = self.db.execute(text(sql), params).fetchall()

        results = []
        for row in rows:
            prod = dict(row._mapping)
            if query and query.strip():
                q = query.strip().lower()
                match_text = " ".join(filter(None, [
                    prod.get("name", ""), prod.get("description", ""),
                    prod.get("sku", ""), prod.get("category", ""),
                ]))
                if q not in match_text.lower():
                    continue

            # Parse attributes safely
            attrs = {}
            if prod.get("attributes_json"):
                try:
                    attrs = json.loads(prod["attributes_json"])
                except Exception:
                    pass

            available = max(0, (prod.get("stock_count") or 0) - (prod.get("reserved_count") or 0))
            results.append({
                "id": prod["id"],
                "sku": prod["sku"],
                "name": prod["name"],
                "name_ar": prod.get("name_ar"),
                "category": prod["category"],
                "base_price": prod["base_price"],
                "currency": prod["currency"],
                "description": prod["description"],
                "attributes": attrs,
                "stock_available": available,
                "in_stock": available > 0,
                "location": prod.get("inventory_location"),
            })

        return {
            "count": len(results),
            "tenant_id": self.tenant_id,
            "products": results,
        }

    def _get_product_details(self, product_id: str) -> Dict[str, Any]:
        row = self.db.execute(
            text("""
                SELECT p.*, i.stock_count, i.reserved_count, i.location as inventory_location
                FROM products p
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE p.id = :product_id AND p.tenant_id = :tenant_id AND p.is_active = 1
            """),
            {"product_id": product_id, "tenant_id": self.tenant_id},
        ).fetchone()

        if not row:
            return {"found": False, "error": f"Product '{product_id}' not found in this catalog."}

        prod = dict(row._mapping)
        attrs = {}
        if prod.get("attributes_json"):
            try:
                attrs = json.loads(prod["attributes_json"])
            except Exception:
                pass

        available = max(0, (prod.get("stock_count") or 0) - (prod.get("reserved_count") or 0))
        return {
            "found": True,
            "id": prod["id"],
            "sku": prod["sku"],
            "name": prod["name"],
            "name_ar": prod.get("name_ar"),
            "category": prod["category"],
            "base_price": prod["base_price"],
            "currency": prod["currency"],
            "description": prod["description"],
            "description_ar": prod.get("description_ar"),
            "attributes": attrs,
            "stock_available": available,
            "in_stock": available > 0,
        }

    def _check_inventory(self, product_id: str) -> Dict[str, Any]:
        row = self.db.execute(
            text("""
                SELECT i.stock_count, i.reserved_count, i.location, i.last_verified_at,
                       p.name, p.sku, p.tenant_id
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                WHERE i.product_id = :product_id AND i.tenant_id = :tenant_id
            """),
            {"product_id": product_id, "tenant_id": self.tenant_id},
        ).fetchone()

        if not row:
            return {
                "product_id": product_id,
                "found": False,
                "in_stock": False,
                "message": f"No inventory record found for '{product_id}' in this tenant.",
            }

        inv = dict(row._mapping)
        available = max(0, inv["stock_count"] - inv["reserved_count"])
        return {
            "product_id": product_id,
            "found": True,
            "name": inv.get("name"),
            "sku": inv.get("sku"),
            "stock_count": inv["stock_count"],
            "reserved_count": inv["reserved_count"],
            "available_count": available,
            "in_stock": available > 0,
            "location": inv.get("location"),
            "last_verified_at": str(inv.get("last_verified_at", "")),
        }

    def _calculate_price(
        self,
        items: List[Dict[str, Any]],
        discount_code: Optional[str] = None,
        apply_shipping: bool = False,
    ) -> Dict[str, Any]:
        if not items:
            return {"error": "No items provided for price calculation."}

        subtotal = 0.0
        currency = None
        category = None
        line_items = []

        for item in items:
            pid = item.get("product_id", "")
            qty = max(1, int(item.get("quantity", 1)))
            row = self.db.execute(
                text("SELECT id, name, base_price, currency, tenant_id FROM products WHERE id = :pid AND tenant_id = :tid"),
                {"pid": pid, "tid": self.tenant_id},
            ).fetchone()
            if not row:
                return {"error": f"Product '{pid}' not found for tenant '{self.tenant_id}'."}

            prod = dict(row._mapping)
            if not currency:
                currency = prod["currency"]
            if not category:
                tenant_row = self.db.execute(
                    text("SELECT category FROM tenants WHERE id = :tid"),
                    {"tid": self.tenant_id},
                ).fetchone()
                category = dict(tenant_row._mapping)["category"] if tenant_row else None

            line_total = prod["base_price"] * qty
            subtotal += line_total
            line_items.append({
                "product_id": pid,
                "name": prod["name"],
                "unit_price": prod["base_price"],
                "quantity": qty,
                "line_total": round(line_total, 2),
            })

        # Discount
        discount_amount = 0.0
        if discount_code and discount_code.upper() in DISCOUNT_CODES:
            discount_amount = round(subtotal * DISCOUNT_CODES[discount_code.upper()], 2)

        after_discount = subtotal - discount_amount

        # Restaurant deposit: 500 per guest
        deposit_required = 0.0
        if category == "restaurant":
            total_guests = sum(i.get("quantity", 1) for i in items)
            deposit_required = 500.0 * total_guests

        # Tax
        tax_rate = VAT_RATES.get(category, 0.0)
        tax_amount = round(after_discount * tax_rate, 2)

        # Shipping
        shipping = SHIPPING_COST if apply_shipping else 0.0

        total = round(after_discount + tax_amount + shipping, 2)

        return {
            "items": line_items,
            "subtotal": round(subtotal, 2),
            "discount_code": discount_code,
            "discount_amount": discount_amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "deposit_required": deposit_required,
            "shipping": shipping,
            "total_amount": total,
            "currency": currency,
        }

    def _search_knowledge(self, query: str, category: Optional[str] = None) -> Dict[str, Any]:
        sql = """
            SELECT id, category, question, question_ar, answer, answer_ar, tags
            FROM knowledge_base
            WHERE tenant_id = :tenant_id
        """
        params: Dict[str, Any] = {"tenant_id": self.tenant_id}

        if query and query.strip():
            term = f"%{query.strip()}%"
            sql += " AND (question LIKE :q OR question_ar LIKE :q OR answer LIKE :q OR answer_ar LIKE :q OR tags LIKE :q)"
            params["q"] = term

        if category and category.strip():
            sql += " AND category = :category"
            params["category"] = category.strip()

        sql += " LIMIT 5"
        rows = self.db.execute(text(sql), params).fetchall()

        return {
            "count": len(rows),
            "results": [dict(r._mapping) for r in rows],
        }

    def _check_booking_availability(
        self, date: Optional[str] = None, service_type: Optional[str] = None
    ) -> Dict[str, Any]:
        sql = "SELECT * FROM booking_slots WHERE tenant_id = :tenant_id AND status = 'available'"
        params: Dict[str, Any] = {"tenant_id": self.tenant_id}

        if date:
            sql += " AND slot_date = :date"
            params["date"] = date

        if service_type:
            sql += " AND service_type LIKE :service_type"
            params["service_type"] = f"%{service_type}%"

        sql += " ORDER BY slot_date ASC, slot_time ASC"
        rows = self.db.execute(text(sql), params).fetchall()

        return {
            "count": len(rows),
            "available_slots": [dict(r._mapping) for r in rows],
        }


# ─────────────────────────────────────────────────────────────
#  Sprint 3.5: Draft Writing and Confirmation Tool Definitions
# ─────────────────────────────────────────────────────────────

DRAFT_WRITING_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "create_order_draft",
        "description": "Prepare a non-binding order draft for the customer. Recalculates prices and stock on the server. Does NOT charge payment or confirm the order.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of products and quantities to draft",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product_id", "quantity"],
                    },
                },
                "customer_notes": {"type": "string", "description": "Customer notes or requests"},
                "discount_code": {"type": "string", "description": "Promo or discount code"},
                "apply_shipping": {"type": "boolean", "description": "Apply shipping fee if applicable"},
            },
            "required": ["items"],
        },
    },
    {
        "name": "update_order_draft",
        "description": "Update an existing draft order while still in editable 'draft' status.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID to update"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product_id", "quantity"],
                    },
                },
                "customer_notes": {"type": "string"},
                "discount_code": {"type": "string"},
                "apply_shipping": {"type": "boolean"},
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "get_order_draft",
        "description": "Retrieve full details and items of an order draft.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID to retrieve"},
            },
            "required": ["draft_id"],
        },
    },
]

CONFIRMATION_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "confirm_order_draft",
        "description": "Confirm an order draft after explicit customer authorization. NEVER invoke without customer's explicit consent.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID to confirm"},
                "customer_explicitly_confirmed": {
                    "type": "boolean",
                    "description": "MUST be true only if the customer unambiguously said YES / confirm in the conversation.",
                },
                "idempotency_key": {"type": "string", "description": "Optional idempotency key"},
            },
            "required": ["draft_id", "customer_explicitly_confirmed"],
        },
    },
    {
        "name": "cancel_order_draft",
        "description": "Cancel an active draft order.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID to cancel"},
                "reason": {"type": "string", "description": "Reason for cancellation"},
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "reserve_booking_slot",
        "description": "Reserve a booking or dining slot. Requires explicit customer confirmation before final reservation.",
        "parameters": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string", "description": "Slot identifier (e.g. SLOT-R01)"},
                "party_size": {"type": "integer", "minimum": 1, "description": "Number of guests/attendees"},
                "customer_explicitly_confirmed": {
                    "type": "boolean",
                    "description": "MUST be true only if customer explicitly approved the reservation.",
                },
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
                "notes": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["slot_id", "party_size", "customer_explicitly_confirmed"],
        },
    },
]

# Sprint 3.6: Handoff tool definitions
HANDOFF_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "request_human_handoff",
        "description": (
            "Escalate to a human specialist and prepare a WhatsApp click-to-chat URL. "
            "Use only when the customer explicitly asks for a human, complains, or the query is beyond verified AI capabilities. "
            "Does NOT send a message, does NOT guarantee human acceptance. Never fabricate delivery status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation (e.g. customer request, complaint, uncertainty)",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional context from the current turn",
                },
                "escalation_trigger": {
                    "type": "string",
                    "enum": ["explicit_request", "complaint", "uncertainty", "workflow_approval", "provider_failure"],
                    "description": "Classification of why escalation was triggered",
                },
            },
            "required": ["reason"],
        },
    },
]

ALL_AGENT_TOOL_DEFINITIONS = (
    READONLY_TOOL_DEFINITIONS + DRAFT_WRITING_TOOL_DEFINITIONS + CONFIRMATION_TOOL_DEFINITIONS + HANDOFF_TOOL_DEFINITIONS
)


class ValidatedAgentToolExecutor(ReadOnlyToolExecutor):
    """
    Sprint 3.5/3.6 Validated Tool Executor:
    - Safely executes read-only tools.
    - Safely creates and updates draft orders via DraftService.
    - Strictly enforces Explicit Confirmation Gate: rejects any confirmation or booking
      that does not have verified customer explicit authorization.
    - Prepares WhatsApp handoff URLs via HandoffService (Sprint 3.6).
    """

    def __init__(self, db: Session, tenant_id: str, session_id: str):
        super().__init__(db, tenant_id, session_id)
        from backend.app.services.draft_service import DraftService
        from backend.app.services.booking_service import BookingService
        from backend.app.services.handoff_service import HandoffService
        self.draft_service = DraftService(db)
        self.booking_service = BookingService(db)
        self.handoff_service = HandoffService(db)

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Draft-Writing Tools
        if tool_name == "create_order_draft":
            return self._handle_create_draft(args)
        elif tool_name == "update_order_draft":
            return self._handle_update_draft(args)
        elif tool_name == "get_order_draft":
            return self._handle_get_draft(args)

        # 2. Confirmation & Cancellation Tools (Guarded)
        elif tool_name == "confirm_order_draft":
            return self._handle_confirm_draft(args)
        elif tool_name == "cancel_order_draft":
            return self._handle_cancel_draft(args)
        elif tool_name == "reserve_booking_slot":
            return self._handle_reserve_booking(args)

        # 3. Human Handoff (Sprint 3.6)
        elif tool_name == "request_human_handoff":
            return self._handle_human_handoff(args)

        # 4. Read-Only Tools (Delegated to parent)
        elif tool_name in VALID_READONLY_TOOLS:
            return super().execute(tool_name, args)

        return {"error": f"Unknown tool: {tool_name}"}

    def _handle_create_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.app.schemas.draft import DraftItemRequest
            raw_items = args.get("items", [])
            items = [
                DraftItemRequest(
                    product_id=it.get("product_id"),
                    quantity=max(1, int(it.get("quantity", 1))),
                )
                for it in raw_items
            ]
            draft = self.draft_service.create_draft(
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                items=items,
                customer_notes=args.get("customer_notes"),
                discount_code=args.get("discount_code"),
                apply_shipping=args.get("apply_shipping", False),
            )
            return {
                "success": True,
                "draft_id": draft.id,
                "status": draft.status,
                "subtotal": draft.subtotal,
                "discount_amount": draft.discount_amount,
                "tax_amount": draft.tax_amount,
                "deposit_required": draft.deposit_required,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
                "items_count": len(draft.items),
                "explicit_confirmation_required": True,
                "message": (
                    f"Order draft '{draft.id}' created. Total: {draft.total_amount} {draft.currency}. "
                    "NOTE: This order is NOT confirmed yet. You must present the summary and receive "
                    "the customer's explicit confirmation before proceeding."
                ),
            }
        except Exception as exc:
            logger.error("Error creating draft for tenant %s: %s", self.tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def _handle_update_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.app.schemas.draft import DraftItemRequest
            draft_id = args.get("draft_id", "")
            raw_items = args.get("items")
            items = (
                [
                    DraftItemRequest(
                        product_id=it.get("product_id"),
                        quantity=max(1, int(it.get("quantity", 1))),
                    )
                    for it in raw_items
                ]
                if raw_items is not None
                else None
            )

            updated = self.draft_service.update_draft(
                tenant_id=self.tenant_id,
                draft_id=draft_id,
                items=items,
                customer_notes=args.get("customer_notes"),
                discount_code=args.get("discount_code"),
                apply_shipping=args.get("apply_shipping"),
            )
            return {
                "success": True,
                "draft_id": updated.id,
                "status": updated.status,
                "total_amount": updated.total_amount,
                "currency": updated.currency,
                "customer_notes": updated.customer_notes,
                "message": f"Draft '{draft_id}' updated successfully. Total is now {updated.total_amount} {updated.currency}.",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            draft_id = args.get("draft_id", "")
            draft = self.draft_service.get_draft(self.tenant_id, draft_id)
            return {
                "found": True,
                "draft_id": draft.id,
                "status": draft.status,
                "items": [it.model_dump() for it in draft.items],
                "subtotal": draft.subtotal,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
                "external_reference": draft.external_reference,
            }
        except Exception as exc:
            return {"found": False, "error": str(exc)}

    def _handle_confirm_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # EXPLICIT CONFIRMATION GATE
        customer_confirmed = bool(args.get("customer_explicitly_confirmed", False))
        if not customer_confirmed:
            # AI agent is attempting to confirm without explicit customer consent
            logger.warning(
                "Confirmation gate blocked unauthorized agent confirmation for tenant %s, draft %s",
                self.tenant_id,
                args.get("draft_id"),
            )
            return {
                "success": False,
                "blocked": True,
                "reason": "CONFIRMATION_GATE_BLOCKED",
                "error": (
                    "Explicit customer confirmation is required. The AI agent cannot independently "
                    "authorize an order confirmation. Please present the draft summary and ask the "
                    "customer for explicit confirmation."
                ),
            }

        try:
            result = self.draft_service.confirm_draft(
                tenant_id=self.tenant_id,
                draft_id=args.get("draft_id", ""),
                idempotency_key=args.get("idempotency_key"),
                actor="ai_agent",
            )
            return {
                "success": True,
                "draft_id": result.draft.id,
                "status": result.draft.status,
                "external_reference": result.external_reference,
                "already_confirmed": result.already_confirmed,
                "message": result.message,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_cancel_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.draft_service.cancel_draft(
                tenant_id=self.tenant_id,
                draft_id=args.get("draft_id", ""),
                actor="ai_agent",
            )
            return {
                "success": True,
                "draft_id": result.draft.id,
                "status": result.draft.status,
                "message": result.message,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_reserve_booking(self, args: Dict[str, Any]) -> Dict[str, Any]:
        customer_confirmed = bool(args.get("customer_explicitly_confirmed", False))
        if not customer_confirmed:
            return {
                "success": False,
                "blocked": True,
                "reason": "CONFIRMATION_GATE_BLOCKED",
                "error": (
                    "Explicit customer confirmation is required before booking. "
                    "Please present the slot time and ask the customer to confirm."
                ),
            }

        try:
            from backend.app.schemas.booking import BookingCreateRequest
            req = BookingCreateRequest(
                slot_id=args.get("slot_id", ""),
                party_size=max(1, int(args.get("party_size", 1))),
                customer_name=args.get("customer_name"),
                customer_phone=args.get("customer_phone"),
                session_id=self.session_id,
                customer_notes=args.get("notes"),
                idempotency_key=args.get("idempotency_key"),
            )
            res = self.booking_service.create_booking(
                tenant_id=self.tenant_id,
                request=req,
                actor="ai_agent",
            )
            return res.model_dump()
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_human_handoff(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sprint 3.6: Delegates to HandoffService to prepare a WhatsApp click-to-chat URL.
        The agent MUST NOT claim the message was sent, delivered, or that a human accepted.
        Injection-proof: tenant phone fetched from DB, not from args.
        """
        reason = args.get("reason") or "Customer requested direct specialist communication via WhatsApp"
        notes = args.get("notes")
        escalation_trigger = args.get("escalation_trigger") or "explicit_request"

        # Sanitize: strip any model-injected override attempts for tenant or phone
        if args.get("tenant_id") or args.get("phone") or args.get("whatsapp_number"):
            logger.warning(
                "Handoff tool injection attempt: model tried to override tenant/phone for tenant %s",
                self.tenant_id,
            )
            # Silently discard injected fields; proceed with trusted DB values
        try:
            result = self.handoff_service.create_handoff(
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                reason=reason,
                notes=notes,
                escalation_trigger=escalation_trigger,
                actor="ai_agent",
            )
            return {
                "handoff_prepared": True,
                "whatsapp_url": result.whatsapp_url,
                "whatsapp_number": result.whatsapp_number,
                "summary": result.summary.model_dump(),
                "user_message": result.user_message,
                "status": result.status,
                "disclaimer": result.disclaimer,
                # Never set: delivered, accepted_by_human, message_sent — those require real provider confirmation
            }
        except Exception as exc:
            logger.error(
                "Handoff tool failed for tenant %s session %s: %s",
                self.tenant_id, self.session_id, exc,
            )
            return {
                "handoff_prepared": False,
                "error": (
                    "Unable to prepare WhatsApp escalation at this time. "
                    "Please ask the customer to contact the business directly."
                ),
            }
