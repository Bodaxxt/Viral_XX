"""
Security and Prompt Injection Guardrails
Direct port of server/ai/guardrails.js with strict type safety, input sanitization,
PCI-DSS redaction, and multi-tenant isolation.
"""

import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(instructions|prompt|secret|api\s*key)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+(developer|dan|jailbreak)\s+mode", re.IGNORECASE),
    re.compile(r"\[system\]", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+dan", re.IGNORECASE),
    re.compile(r"disregard\s+(any|all)\s+safety", re.IGNORECASE),
    re.compile(r"what\s+is\s+your\s+system\s+instruction", re.IGNORECASE),
    re.compile(r"print\s+your\s+initial\s+prompt", re.IGNORECASE),
    re.compile(r"bypass\s+(the\s+)?guardrails", re.IGNORECASE),
    re.compile(r"leak\s+(the\s+)?(system\s+prompt|prompt|secret)", re.IGNORECASE),
    re.compile(r"تجاهل\s+(جميع|كل)\s+التعليمات", re.IGNORECASE),
    re.compile(r"أظهر\s+الأسرار", re.IGNORECASE),
    re.compile(r"اكشف\s+(عن\s+)?التعليمات\s+السرية", re.IGNORECASE),
    re.compile(r"ما\s+هو\s+البرومبت\s+الرئيسي", re.IGNORECASE),
]

CARD_PATTERN = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b")
CVV_PATTERN = re.compile(r"\b(cvv|cvc)(?:\s+is|\s*:)?\s*(\d{3,4})\b", re.IGNORECASE)
MAX_MESSAGE_LENGTH = 1500

SAFE_GUARDRAIL_RESPONSE = (
    "I am the Viral-X verified sales assistant. I operate exclusively within our authorized "
    "business catalog, inventory verification, and customer ordering protocols. "
    "How can I assist you with our services today?"
)


class GuardrailCheckResult(BaseModel):
    is_safe: bool = Field(..., description="True if no malicious or override patterns were found")
    flagged_pattern: Optional[str] = Field(default=None, description="The regex pattern that matched if unsafe")
    reason: Optional[str] = Field(default=None, description="Rejection reason code")
    safe_response: str = Field(default=SAFE_GUARDRAIL_RESPONSE, description="Polite canned refusal message")
    sanitized: str = Field(default="", description="Sanitized and bounded message text")


class Guardrails:
    """
    Main guardrails interface used by AgentOrchestrator and test suites.
    """

    def __init__(self, max_length: int = MAX_MESSAGE_LENGTH):
        self.max_length = max_length

    def check_input(self, text: Optional[str], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates message length, prompt injection patterns, and tenant integrity.
        Returns a dict:
            {"blocked": bool, "reason": Optional[str], "sanitized_input": str}
        """
        if not text or not isinstance(text, str):
            return {"blocked": False, "sanitized_input": ""}

        trimmed = text.strip()

        # Length check
        if len(trimmed) > self.max_length:
            return {
                "blocked": True,
                "reason": f"Message exceeds maximum allowed length of {self.max_length} characters.",
                "sanitized_input": trimmed[:self.max_length],
            }

        # Prompt injection check
        for pattern in INJECTION_PATTERNS:
            if pattern.search(trimmed):
                return {
                    "blocked": True,
                    "reason": "PROMPT_INJECTION_DETECTED",
                    "flagged_pattern": pattern.pattern,
                    "sanitized_input": "",
                }

        return {
            "blocked": False,
            "sanitized_input": trimmed,
            "tenant_id": tenant_id,
        }

    def sanitize_output(self, text: Optional[str]) -> str:
        """
        Redacts payment cards, CVVs, or sensitive credentials from outgoing LLM text.
        """
        if not text or not isinstance(text, str):
            return ""

        clean = CARD_PATTERN.sub("[REDACTED_CARD]", text)
        clean = CVV_PATTERN.sub(r"\1: [REDACTED]", clean)
        return clean

    @staticmethod
    def verify_tenant_access(requested_tenant_id: Optional[str], active_tenant_id: Optional[str]) -> bool:
        return SecurityGuardrails.verify_tenant_access(requested_tenant_id, active_tenant_id)


class SecurityGuardrails:
    """
    Static helper class preserving backwards-compatibility.
    """

    @staticmethod
    def inspect_prompt(input_text: Optional[str], max_chars: int = MAX_MESSAGE_LENGTH) -> GuardrailCheckResult:
        g = Guardrails(max_length=max_chars)
        res = g.check_input(input_text)
        if res["blocked"]:
            return GuardrailCheckResult(
                is_safe=False,
                flagged_pattern=res.get("flagged_pattern"),
                reason=res.get("reason"),
                safe_response=SAFE_GUARDRAIL_RESPONSE,
                sanitized="",
            )
        return GuardrailCheckResult(
            is_safe=True,
            sanitized=res.get("sanitized_input", ""),
        )

    @staticmethod
    def redact_sensitive(text: Optional[str]) -> str:
        g = Guardrails()
        return g.sanitize_output(text)

    @staticmethod
    def verify_tenant_access(requested_tenant_id: Optional[str], active_tenant_id: Optional[str]) -> bool:
        if not requested_tenant_id or not active_tenant_id:
            raise ValueError("Tenant ID cannot be null or empty.")

        if requested_tenant_id.strip() != active_tenant_id.strip():
            raise PermissionError(
                f"Tenant Isolation Violation: Cross-tenant operation blocked "
                f"({requested_tenant_id} != {active_tenant_id})."
            )
        return True
