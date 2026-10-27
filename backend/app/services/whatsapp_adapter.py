"""
WhatsApp Click-to-Chat Adapter
Sprint 3.6 - Migration to Python

Safely builds, validates, and encodes WhatsApp click-to-chat escalation URLs
with strict destination host whitelisting, E.164 phone normalization,
and PCI-DSS/secret redaction.
"""

import re
import urllib.parse
from typing import Optional, Dict, Any, List

from backend.app.core.logging import logger

# Strictly allowed destination hosts for WhatsApp click-to-chat
ALLOWED_WHATSAPP_SCHEMES = frozenset({"https"})
ALLOWED_WHATSAPP_HOSTS = frozenset({"wa.me", "api.whatsapp.com"})

# Regex patterns for sensitive data redaction
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
BEARER_TOKEN_REGEX = re.compile(r"(?:Bearer|bearer|BEARER)\s+[\w\-\.=+/]{8,}", re.IGNORECASE)
API_KEY_REGEX = re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[a-zA-Z0-9]{36})\b")
PASSWORD_REGEX = re.compile(r"(?:password|secret|token)\s*[:=]\s*(?!\[[A-Z_ ]+\])\S+", re.IGNORECASE)


class WhatsAppAdapterError(Exception):
    """Base exception for WhatsApp adapter errors."""
    pass


class InvalidPhoneNumberError(WhatsAppAdapterError):
    """Raised when destination phone number is missing, malformed, or invalid."""
    pass


class MaliciousUrlDestinationError(WhatsAppAdapterError):
    """Raised when an unauthorized destination host or scheme is detected."""
    pass


class WhatsAppAdapter:
    """
    Constructs safe WhatsApp click-to-chat URLs with guaranteed phone normalization,
    allowlisted domain enforcement, Arabic/English UTF-8 encoding, and secret redaction.
    """

    @staticmethod
    def normalize_phone_number(raw_phone: Optional[str]) -> str:
        """
        Validates and normalizes phone number to digits only (E.164 without leading plus).
        Rejects empty numbers, strings with fewer than 8 or more than 15 digits,
        or numbers consisting solely of zeros.
        """
        if not raw_phone or not isinstance(raw_phone, str) or not raw_phone.strip():
            raise InvalidPhoneNumberError("Business WhatsApp phone number is missing or empty.")

        clean_phone = re.sub(r"[^0-9]", "", raw_phone)

        if len(clean_phone) < 8 or len(clean_phone) > 15:
            raise InvalidPhoneNumberError(
                f"Phone number '{clean_phone}' has invalid length ({len(clean_phone)} digits). "
                "Must be between 8 and 15 digits."
            )

        if set(clean_phone) == {"0"}:
            raise InvalidPhoneNumberError("Phone number cannot consist solely of zeros.")

        return clean_phone

    @classmethod
    def sanitize_message_content(cls, text: str) -> str:
        """
        Redacts credit cards, bearer tokens, API keys, and secret values from message content.
        Preserves business context, draft IDs, Arabic text, and customer notes.
        """
        if not text:
            return ""

        redacted = CREDIT_CARD_REGEX.sub("[CARD REDACTED]", text)
        redacted = BEARER_TOKEN_REGEX.sub("[TOKEN REDACTED]", redacted)
        redacted = API_KEY_REGEX.sub("[KEY REDACTED]", redacted)
        redacted = PASSWORD_REGEX.sub("[CREDENTIAL REDACTED]", redacted)
        return redacted

    @classmethod
    def build_message_body(
        cls,
        tenant_name: str,
        reason: str,
        notes: Optional[str] = None,
        draft_info: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Constructs structured escalation message body matching Node.js production format.
        """
        safe_tenant = cls.sanitize_message_content(tenant_name)
        safe_reason = cls.sanitize_message_content(reason)
        safe_notes = cls.sanitize_message_content(notes) if notes else None

        body = f"Hello {safe_tenant} Team,\n\nCustomer Inquiry Escalation:\nReason: {safe_reason}\n"
        if safe_notes:
            body += f"Notes: {safe_notes}\n"

        if draft_info:
            draft_id = draft_info.get("id") or draft_info.get("draft_id") or ""
            items = draft_info.get("items") or []
            if isinstance(items, list):
                items_summary = ", ".join(
                    f"{it.get('quantity', 1)}x {it.get('name') or it.get('product_id', 'Item')}"
                    for it in items
                )
            else:
                items_summary = str(items)

            total = draft_info.get("total_amount", 0)
            currency = draft_info.get("currency", "")
            status = draft_info.get("status", "draft")

            body += (
                f"\nAssociated Draft: {draft_id}\n"
                f"Items: {items_summary}\n"
                f"Total: {total:,.2f} {currency}\n"
                f"Status: {status}\n"
            )

        if session_id:
            body += f"\nSession Token: {session_id}\n"

        body += "Escalated via Viral-X Safe Sales Agent."
        return body

    @classmethod
    def build_click_to_chat_url(
        cls,
        phone_number: str,
        message_body: str,
    ) -> str:
        """
        Builds the safe https://wa.me click-to-chat URL.
        Guarantees allowlisted scheme and host. Correctly percent-encodes Arabic/English text.
        """
        clean_phone = cls.normalize_phone_number(phone_number)
        sanitized_body = cls.sanitize_message_content(message_body)
        encoded_text = urllib.parse.quote(sanitized_body, safe="")

        url = f"https://wa.me/{clean_phone}?text={encoded_text}"
        cls.validate_url_security(url)
        return url

    @classmethod
    def validate_url_security(cls, url: str) -> bool:
        """
        Ensures the generated URL is strictly HTTPS and targets an allowlisted WhatsApp domain.
        Prevents arbitrary redirect URLs, open redirects, or javascript/data schemes.
        """
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ALLOWED_WHATSAPP_SCHEMES:
            raise MaliciousUrlDestinationError(
                f"Unauthorized URL scheme '{parsed.scheme}'. Only 'https' is permitted."
            )

        if parsed.netloc.lower() not in ALLOWED_WHATSAPP_HOSTS:
            raise MaliciousUrlDestinationError(
                f"Unauthorized destination host '{parsed.netloc}'. Must be wa.me or api.whatsapp.com."
            )

        return True
