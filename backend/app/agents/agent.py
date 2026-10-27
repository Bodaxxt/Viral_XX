"""
Python AI Agent Orchestrator — Sprint 3 Migration
Mirrors the Node.js aiAgent.js orchestration loop exactly.

Key design properties:
- Same provider priority order (Gemini > Anthropic > OpenAI > Local).
- Same max tool rounds (6).
- Same guardrail checks (inject detection, length, PII, tenant boundary).
- Local (no-key) mode with deterministic business intent matching.
- All write-capable tools (create_order_draft, etc.) are blocked via tools.py.
- Does NOT touch the Node.js production /api/chat endpoint.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.agents.guardrails import Guardrails
from backend.app.agents.prompt_templates import build_system_prompt
from backend.app.agents.provider_factory import LocalFallbackProvider, get_provider, detect_provider_name
from backend.app.agents.providers import BaseProvider, ProviderError, ProviderTimeoutError
from backend.app.agents.schemas import AgentRequest, AgentResponse, ToolCallRecord
from backend.app.agents.tools import READONLY_TOOL_DEFINITIONS, ReadOnlyToolExecutor
from backend.app.core.logging import logger


class TenantNotFoundError(ValueError):
    pass


class AgentOrchestrator:
    """
    Primary agent class.  One instance per request (thin; no shared mutable state).
    """

    def __init__(self, db: Session):
        self.db = db
        self.guardrails = Guardrails()
        self.provider: BaseProvider = get_provider()

    # ────────────────────────────────────────────────────
    #  Public entry point
    # ────────────────────────────────────────────────────

    async def handle(self, request: AgentRequest) -> AgentResponse:
        tenant_id = request.tenant_id
        session_id = request.session_id
        user_message = request.message

        # 1. Load tenant
        tenant = self._load_tenant(tenant_id)

        # 2. Guardrails: sanitize input
        check = self.guardrails.check_input(user_message, tenant_id)
        if check["blocked"]:
            return AgentResponse(
                reply="عذراً، لا يمكنني معالجة هذا الطلب. للمساعدة يرجى إعادة صياغة سؤالك.",
                grounding="Blocked by security guardrails",
                provider=detect_provider_name(),
                tool_calls=[],
                blocked=True,
                block_reason=check.get("reason"),
            )

        sanitized_message = check.get("sanitized_input", user_message)

        # 3. Load recent conversation history (last 12 messages)
        history = self._load_history(tenant_id, session_id, limit=12)

        # 4. Build system prompt
        system_prompt = build_system_prompt(tenant)

        # 5. Tool executor
        tool_executor = ReadOnlyToolExecutor(
            db=self.db, tenant_id=tenant_id, session_id=session_id
        )

        # 6. Dispatch to provider (or local)
        if isinstance(self.provider, LocalFallbackProvider):
            reply, raw_tool_calls, grounding = self._orchestrate_local(
                tenant=tenant,
                message=sanitized_message,
                session_id=session_id,
                tool_executor=tool_executor,
            )
        else:
            try:
                reply, raw_tool_calls, grounding = await self.provider.call(
                    system_prompt=system_prompt,
                    history=history,
                    current_message=sanitized_message,
                    tool_definitions=READONLY_TOOL_DEFINITIONS,
                    tool_executor=tool_executor,
                    tenant_id=tenant_id,
                    session_id=session_id,
                )
            except ProviderTimeoutError as exc:
                logger.warning("Provider timeout for tenant %s: %s", tenant_id, exc)
                # Fallback to local on timeout
                reply, raw_tool_calls, grounding = self._orchestrate_local(
                    tenant=tenant,
                    message=sanitized_message,
                    session_id=session_id,
                    tool_executor=tool_executor,
                )
            except ProviderError as exc:
                logger.error("Provider error for tenant %s: %s", tenant_id, exc)
                return AgentResponse(
                    reply="أعتذر، حدث خطأ في خدمة الذكاء الاصطناعي. يرجى المحاولة مجدداً.",
                    grounding=f"Provider error: {self.provider.name}",
                    provider=detect_provider_name(),
                    tool_calls=[],
                    error=str(exc),
                )

        # 7. Sanitize output (PCI / sensitive data redaction)
        safe_reply = self.guardrails.sanitize_output(reply)

        tool_call_records = [
            ToolCallRecord(tool=tc["tool"], args=tc["args"], result=tc["result"])
            for tc in raw_tool_calls
        ]

        return AgentResponse(
            reply=safe_reply,
            grounding=grounding,
            provider=detect_provider_name(),
            tool_calls=tool_call_records,
        )

    # ────────────────────────────────────────────────────
    #  Database helpers
    # ────────────────────────────────────────────────────

    def _load_tenant(self, tenant_id: str) -> Dict[str, Any]:
        row = self.db.execute(
            text("SELECT * FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        ).fetchone()
        if not row:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found.")
        return dict(row._mapping)

    def _load_history(
        self, tenant_id: str, session_id: str, limit: int = 12
    ) -> List[Dict[str, str]]:
        rows = self.db.execute(
            text("""
                SELECT sender, content FROM messages
                WHERE session_id = :session_id AND tenant_id = :tenant_id
                ORDER BY created_at DESC LIMIT :limit
            """),
            {"session_id": session_id, "tenant_id": tenant_id, "limit": limit},
        ).fetchall()
        return [{"sender": r.sender, "content": r.content} for r in reversed(rows)]

    # ────────────────────────────────────────────────────
    #  Local / no-key deterministic orchestrator
    # ────────────────────────────────────────────────────

    _GREETING_PATTERNS = re.compile(
        r"^\s*(hi|hello|hey|salam|مرحب|السلام|أهل|صباح|مساء|كيف حالك|أهلاً)\b",
        re.IGNORECASE,
    )
    _PRODUCT_KEYWORDS = re.compile(
        r"(product|item|catalog|catalogue|show|search|diamond|gold|ring|necklace|"
        r"تشكيل|كتالوج|ماس|خاتم|قلادة|ذهب|restaurant|menu|table|booking|طاولة|"
        r"قائمة|حجز|clinic|consult|screen|examination|عيادة|استشار|فحص)",
        re.IGNORECASE,
    )
    _POLICY_KEYWORDS = re.compile(
        r"(policy|hours|delivery|shipping|authentic|gia|allergy|deposit|refund|"
        r"سياسة|مواعيد|توصيل|شحن|أصالة|حساسية|عربون|استرداد)",
        re.IGNORECASE,
    )
    _PRICING_KEYWORDS = re.compile(
        r"(price|cost|how much|budget|كم|سعر|تكلفة|ميزانية)",
        re.IGNORECASE,
    )

    def _detect_arabic(self, text: str) -> bool:
        return bool(re.search(r"[\u0600-\u06FF]", text))

    def _orchestrate_local(
        self,
        tenant: Dict[str, Any],
        message: str,
        session_id: str,
        tool_executor: ReadOnlyToolExecutor,
    ) -> Tuple[str, List[Dict[str, Any]], str]:
        q = message.strip().lower()
        is_arabic = self._detect_arabic(message)
        name = tenant.get("name", "our store")
        tool_calls: List[Dict[str, Any]] = []

        # A. Greeting
        if self._GREETING_PATTERNS.search(q) and len(q) < 60:
            reply = (
                f"أهلاً وسهلاً بك في **{name}**! 🌟 أنا مساعدك الذكي المعتمد. كيف يمكنني خدمتك اليوم؟ يمكنني مساعدتك في استعراض منتجاتنا، الأسعار، أو الحجوزات."
                if is_arabic
                else f"Welcome to **{name}**! 🌟 I'm your certified AI assistant. How can I help you today? I can browse our catalog, check pricing, or assist with bookings."
            )
            return reply, tool_calls, f"Local Orchestrator: Greeting — {name}"

        # B. Policy / knowledge intent
        if self._POLICY_KEYWORDS.search(q):
            result = tool_executor.execute("search_business_knowledge", {"query": message})
            tool_calls.append({"tool": "search_business_knowledge", "args": {"query": message}, "result": result})
            if result.get("count", 0) > 0:
                item = result["results"][0]
                answer = (item.get("answer_ar") or item.get("answer", "")) if is_arabic else item.get("answer", "")
                reply = (
                    f"**بخصوص استفساركم:**\n\n{answer}\n\nهل تحتاج مساعدة إضافية؟"
                    if is_arabic
                    else f"**Policy Information:**\n\n{answer}\n\nIs there anything else I can help you with?"
                )
                return reply, tool_calls, f"Local Orchestrator: Knowledge — {name}"

        # C. Pricing intent
        if self._PRICING_KEYWORDS.search(q):
            result = tool_executor.execute("search_products", {"query": message})
            tool_calls.append({"tool": "search_products", "args": {"query": message}, "result": result})
            if result.get("count", 0) > 0:
                products = result["products"][:3]
                lines = "\n".join(
                    f"• **{p['name']}** — {p['base_price']:,.0f} {p['currency']}"
                    + (f" ({p.get('name_ar', '')})" if is_arabic and p.get("name_ar") else "")
                    for p in products
                )
                reply = (
                    f"إليك الأسعار المتاحة في **{name}**:\n\n{lines}\n\nيمكنني حساب السعر الإجمالي مع الضرائب والخصومات عند الطلب."
                    if is_arabic
                    else f"Here are available prices at **{name}**:\n\n{lines}\n\nI can calculate a full quote with taxes and discounts upon request."
                )
                return reply, tool_calls, f"Local Orchestrator: Pricing — {name}"

        # D. Product / catalog browsing
        if self._PRODUCT_KEYWORDS.search(q):
            result = tool_executor.execute("search_products", {"query": message})
            tool_calls.append({"tool": "search_products", "args": {"query": message}, "result": result})
            if result.get("count", 0) > 0:
                products = result["products"][:4]
                lines = "\n".join(
                    f"• **{p['name']}** — {p['base_price']:,.0f} {p['currency']} "
                    f"({'متوفر ✅' if p['in_stock'] else 'غير متوفر ❌'} "
                    f"| {'In Stock ✅' if p['in_stock'] else 'Out of Stock ❌'})"
                    for p in products
                )
                reply = (
                    f"إليك ما وجدته في كتالوج **{name}**:\n\n{lines}\n\nهل تودون التفاصيل أو التحقق من المخزون لأي من هذه المنتجات؟"
                    if is_arabic
                    else f"Here's what I found in **{name}**'s catalog:\n\n{lines}\n\nWould you like details or inventory check for any of these?"
                )
                return reply, tool_calls, f"Local Orchestrator: Catalog — {name}"

        # E. Default fallback
        reply = (
            f"أهلاً بك في **{name}**. أنا مساعدك الذكي المعتمد. يمكنني مساعدتك في استعراض المنتجات، التحقق من المخزون، حساب الأسعار، أو البحث عن السياسات. كيف أخدمك؟"
            if is_arabic
            else f"Welcome to **{name}**. I'm your certified AI assistant. I can search our catalog, check live inventory, calculate pricing, or look up our policies. How can I help?"
        )
        return reply, tool_calls, f"Local Orchestrator: Default Welcome — {name}"
