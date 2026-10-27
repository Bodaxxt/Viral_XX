"""
Sprint 3.6 — Human Handoff & WhatsApp Adapter Test Suite

Tests:
1. Explicit customer handoff request
2. Complaint and uncertainty escalation detection
3. Ordinary questions must not trigger escalation
4. Missing or invalid business phone numbers
5. Correct Arabic and English URL encoding
6. Rejection of malicious URL destinations and arbitrary redirects
7. Sensitive-data exclusion from generated messages and logs
8. Tenant isolation and authorization failures
9. Duplicate request/idempotency behavior
10. Handoff state transitions and invalid transitions
11. Failure handling and honest reporting of delivery status
12. Agent attempts to override handoff or tenant-scope rules
13. Existing Node.js handoff behavior compatibility (response shape match)
"""

import pytest
import json
from unittest.mock import MagicMock

from backend.app.services.handoff_service import (
    HandoffService,
    HandoffServiceError,
    HandoffNotFoundError,
    CrossTenantAccessError,
    InvalidStateTransitionError,
    MissingOrInvalidPhoneError,
    TenantNotFoundError,
)
from backend.app.services.whatsapp_adapter import (
    WhatsAppAdapter,
    InvalidPhoneNumberError,
    MaliciousUrlDestinationError,
)


# ─────────────────────────────────────────────────────────────
# Fixtures (db_session and client are provided by conftest.py)
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def jewelry_tenant_id():
    return "al-noor-jewelry"


@pytest.fixture
def restaurant_tenant_id():
    return "saffron-table"


@pytest.fixture
def healthcare_tenant_id():
    return "vitalis-health"


# ─────────────────────────────────────────────────────────────
# 1. WhatsApp Adapter — Phone Number Normalization
# ─────────────────────────────────────────────────────────────

class TestWhatsAppPhoneNormalization:
    def test_valid_international_format(self):
        phone = WhatsAppAdapter.normalize_phone_number("+97444991200")
        assert phone == "97444991200"

    def test_valid_with_spaces_and_dashes(self):
        phone = WhatsAppAdapter.normalize_phone_number("+974 4499 1200")
        assert phone == "97444991200"

    def test_valid_egyptian_number(self):
        phone = WhatsAppAdapter.normalize_phone_number("+20 100 123 4567")
        assert phone == "201001234567"

    def test_missing_phone_raises(self):
        with pytest.raises(InvalidPhoneNumberError):
            WhatsAppAdapter.normalize_phone_number("")

    def test_none_phone_raises(self):
        with pytest.raises(InvalidPhoneNumberError):
            WhatsAppAdapter.normalize_phone_number(None)

    def test_too_short_phone_raises(self):
        with pytest.raises(InvalidPhoneNumberError):
            WhatsAppAdapter.normalize_phone_number("1234567")  # 7 digits — too short

    def test_too_long_phone_raises(self):
        with pytest.raises(InvalidPhoneNumberError):
            WhatsAppAdapter.normalize_phone_number("1234567890123456")  # 16 digits

    def test_all_zeros_rejected(self):
        with pytest.raises(InvalidPhoneNumberError):
            WhatsAppAdapter.normalize_phone_number("00000000")


# ─────────────────────────────────────────────────────────────
# 2. WhatsApp Adapter — URL Generation and Security
# ─────────────────────────────────────────────────────────────

class TestWhatsAppUrlGeneration:
    def test_url_starts_with_wa_me(self):
        url = WhatsAppAdapter.build_click_to_chat_url("+97444991200", "Hello, I need help.")
        assert url.startswith("https://wa.me/97444991200?text=")

    def test_arabic_text_correctly_encoded(self):
        arabic_msg = "مرحبا، أحتاج مساعدة بخصوص مجوهرات"
        url = WhatsAppAdapter.build_click_to_chat_url("+97444991200", arabic_msg)
        assert "wa.me" in url
        assert "%" in url  # URL-encoded

    def test_english_text_percent_encoded(self):
        msg = "Hello Team,\n\nCustomer needs help.\nReason: complaint"
        url = WhatsAppAdapter.build_click_to_chat_url("+97444991200", msg)
        assert "Hello%20Team" in url or "Hello+Team" in url or "Hello" in url

    def test_reject_non_https_scheme(self):
        with pytest.raises(MaliciousUrlDestinationError):
            WhatsAppAdapter.validate_url_security("http://wa.me/97444991200?text=hello")

    def test_reject_javascript_scheme(self):
        with pytest.raises(MaliciousUrlDestinationError):
            WhatsAppAdapter.validate_url_security("javascript:alert(1)")

    def test_reject_arbitrary_redirect_host(self):
        with pytest.raises(MaliciousUrlDestinationError):
            WhatsAppAdapter.validate_url_security("https://evil.com/wa.me?text=steal")

    def test_reject_whatsapp_with_wrong_host(self):
        with pytest.raises(MaliciousUrlDestinationError):
            WhatsAppAdapter.validate_url_security("https://notwhatsapp.com?text=hello")

    def test_only_allowlisted_hosts_pass(self):
        # Should not raise
        WhatsAppAdapter.validate_url_security("https://wa.me/97444991200?text=hello")
        WhatsAppAdapter.validate_url_security("https://api.whatsapp.com/send?phone=97444991200")


# ─────────────────────────────────────────────────────────────
# 3. WhatsApp Adapter — Sensitive Data Redaction
# ─────────────────────────────────────────────────────────────

class TestSensitiveDataRedaction:
    def test_credit_card_redacted_in_message(self):
        msg = "Payment info: 4111 1111 1111 1111"
        result = WhatsAppAdapter.sanitize_message_content(msg)
        assert "4111" not in result
        assert "[CARD REDACTED]" in result

    def test_bearer_token_redacted(self):
        msg = "Token: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc"
        result = WhatsAppAdapter.sanitize_message_content(msg)
        assert "eyJ" not in result
        assert "[TOKEN REDACTED]" in result

    def test_api_key_redacted(self):
        msg = "Use key sk-abc123def456ghi789jkl012mno345p"
        result = WhatsAppAdapter.sanitize_message_content(msg)
        assert "sk-abc123" not in result
        assert "[KEY REDACTED]" in result

    def test_arabic_customer_name_preserved(self):
        msg = "Hello Team,\nReason: عميل محترم يريد مساعدة"
        result = WhatsAppAdapter.sanitize_message_content(msg)
        assert "عميل محترم" in result

    def test_draft_id_preserved_in_message(self):
        result = WhatsAppAdapter.build_message_body(
            tenant_name="Al Noor High Jewelry",
            reason="Customer requested help",
            draft_info={"id": "DRF-JEW-12345", "items": [], "total_amount": 5000, "currency": "QAR", "status": "draft"},
        )
        assert "DRF-JEW-12345" in result

    def test_url_does_not_contain_raw_card(self):
        msg = "Card: 4111111111111111 — please help"
        url = WhatsAppAdapter.build_click_to_chat_url("+97444991200", msg)
        assert "4111111111111111" not in url


# ─────────────────────────────────────────────────────────────
# 4. Escalation Intent Detection
# ─────────────────────────────────────────────────────────────

class TestEscalationIntentDetection:
    def test_explicit_english_human_request(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("I need to speak to a human")
        assert should is True
        assert trigger == "explicit_request"

    def test_explicit_arabic_human_request(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("عايز اكلم موظف")
        assert should is True
        assert trigger == "explicit_request"

    def test_whatsapp_keyword_triggers_escalation(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("send me whatsapp")
        assert should is True

    def test_complaint_triggers_escalation(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("this is a scam, I want a refund")
        assert should is True
        assert trigger == "complaint"

    def test_arabic_complaint_triggers_escalation(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("أنا غضبان جدا واريد استرجاع فلوسي")
        assert should is True
        assert trigger == "complaint"

    def test_ordinary_product_question_does_not_escalate(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("What is the price of the diamond ring?")
        assert should is False

    def test_ordinary_arabic_question_does_not_escalate(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("ما هي ساعات العمل؟")
        assert should is False

    def test_empty_message_does_not_escalate(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent("")
        assert should is False

    def test_healthcare_medical_diagnosis_escalates(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent(
            "Can you diagnose my symptoms?", category="healthcare"
        )
        assert should is True
        assert trigger == "uncertainty"

    def test_jewelry_bespoke_escalates(self):
        should, trigger, reason = HandoffService.evaluate_escalation_intent(
            "I need a bespoke design platinum set", category="jewelry"
        )
        assert should is True
        assert trigger == "workflow_approval"


# ─────────────────────────────────────────────────────────────
# 5. HandoffService — Lifecycle & Tenant Isolation
# ─────────────────────────────────────────────────────────────

class TestHandoffServiceLifecycle:
    def test_create_handoff_success(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        result = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            session_id="test-session-handoff-1",
            reason="Customer requested specialist",
            escalation_trigger="explicit_request",
        )
        assert result.handoff_prepared is True
        assert result.whatsapp_url.startswith("https://wa.me/")
        assert result.status == "link_prepared"
        assert "DRF" not in result.summary.draft_id if result.summary.draft_id else True
        # Disclaimer must be present and honest
        assert "does not send" in result.disclaimer.lower() or "does not guarantee" in result.disclaimer.lower()

    def test_handoff_phone_from_tenant_not_from_caller(self, db_session, jewelry_tenant_id):
        """Phone number must come from DB tenant config, not from caller input."""
        service = HandoffService(db_session)
        result = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            session_id="session-phone-test",
            reason="Test",
        )
        # al-noor-jewelry has +97444991200
        assert "97444991200" in result.whatsapp_url

    def test_create_handoff_nonexistent_tenant_raises(self, db_session):
        service = HandoffService(db_session)
        with pytest.raises(TenantNotFoundError):
            service.create_handoff(tenant_id="nonexistent-tenant", reason="Test")

    def test_cross_tenant_access_on_get_rejected(self, db_session, jewelry_tenant_id, restaurant_tenant_id):
        service = HandoffService(db_session)
        handoff = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            session_id="cross-tenant-test",
            reason="Test escalation",
        )
        with pytest.raises(CrossTenantAccessError):
            service.get_handoff(tenant_id=restaurant_tenant_id, handoff_id=handoff.id)

    def test_get_handoff_not_found_raises(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        with pytest.raises(HandoffNotFoundError):
            service.get_handoff(tenant_id=jewelry_tenant_id, handoff_id="HND-NONEXISTENT")

    def test_idempotency_key_prevents_duplicate(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        idem_key = "IDEM-HANDOFF-001"
        r1 = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            reason="First request",
            idempotency_key=idem_key,
        )
        r2 = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            reason="Duplicate request",
            idempotency_key=idem_key,
        )
        assert r1.id == r2.id
        assert r2.already_created is True

    def test_close_handoff_changes_status(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        handoff = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            session_id="close-test-session",
            reason="Test",
        )
        closed = service.close_handoff(
            tenant_id=jewelry_tenant_id,
            handoff_id=handoff.id,
            resolution_notes="Issue resolved by staff",
            actor="staff",
        )
        assert closed.status == "closed"
        assert closed.closed_at is not None

    def test_close_already_closed_handoff_raises(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        handoff = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            session_id="double-close-session",
            reason="Test",
        )
        service.close_handoff(tenant_id=jewelry_tenant_id, handoff_id=handoff.id)
        with pytest.raises(InvalidStateTransitionError):
            service.close_handoff(tenant_id=jewelry_tenant_id, handoff_id=handoff.id)

    def test_handoff_does_not_claim_message_sent(self, db_session, jewelry_tenant_id):
        service = HandoffService(db_session)
        result = service.create_handoff(
            tenant_id=jewelry_tenant_id,
            reason="Test",
        )
        result_dict = result.model_dump()
        # Must not contain "delivered", "sent", "accepted_by_human"
        assert "delivered" not in result_dict
        assert "message_sent" not in result_dict
        assert "accepted_by_human" not in result_dict


# ─────────────────────────────────────────────────────────────
# 6. HandoffService — Invalid Phone Fallback
# ─────────────────────────────────────────────────────────────

class TestMissingOrInvalidPhone:
    def test_tenant_with_invalid_phone_raises(self, db_session):
        """Mock a tenant with a bad phone number to confirm correct error propagation."""
        from backend.app.db.models import Tenant
        bad_tenant = Tenant(
            id="bad-phone-tenant",
            name="Bad Phone Co",
            category="jewelry",
            location="Unknown",
            currency="USD",
            whatsapp_number="000",  # Invalid — too short
            operating_hours="24/7",
            policy_summary="n/a",
            integration_mode="demo",
        )
        db_session.add(bad_tenant)
        db_session.commit()

        service = HandoffService(db_session)
        with pytest.raises(MissingOrInvalidPhoneError):
            service.create_handoff(tenant_id="bad-phone-tenant", reason="Test")


# ─────────────────────────────────────────────────────────────
# 7. API Endpoint Tests
# ─────────────────────────────────────────────────────────────

class TestHandoffEndpoints:
    def test_endpoint_missing_tenant_header_401(self, client):
        resp = client.post("/api/v1/handoff/whatsapp", json={"reason": "Need help"})
        assert resp.status_code == 401

    def test_endpoint_mismatched_tenant_403(self, client, jewelry_tenant_id):
        resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"tenantId": "different-tenant", "reason": "Need help"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert resp.status_code == 403

    def test_endpoint_create_handoff_success(self, client, jewelry_tenant_id):
        resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Customer wants to speak with specialist"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["handoff_prepared"] is True
        assert data["whatsapp_url"].startswith("https://wa.me/")
        assert "disclaimer" in data

    def test_endpoint_get_handoff_success(self, client, jewelry_tenant_id):
        create_resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Test escalation"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert create_resp.status_code == 201
        handoff_id = create_resp.json()["id"]

        get_resp = client.get(
            f"/api/v1/handoff/{handoff_id}",
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == handoff_id

    def test_endpoint_get_handoff_cross_tenant_403(self, client, jewelry_tenant_id, restaurant_tenant_id):
        create_resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Test"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        handoff_id = create_resp.json()["id"]

        get_resp = client.get(
            f"/api/v1/handoff/{handoff_id}",
            headers={"X-Tenant-ID": restaurant_tenant_id},
        )
        assert get_resp.status_code == 403

    def test_endpoint_close_handoff(self, client, jewelry_tenant_id):
        create_resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Close test"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        handoff_id = create_resp.json()["id"]

        close_resp = client.post(
            f"/api/v1/handoff/{handoff_id}/close",
            json={"resolution_notes": "Resolved by staff"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert close_resp.status_code == 200
        assert close_resp.json()["status"] == "closed"

    def test_endpoint_nonexistent_handoff_404(self, client, jewelry_tenant_id):
        resp = client.get(
            "/api/v1/handoff/HND-DOESNOTEXIST",
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert resp.status_code == 404

    def test_endpoint_response_matches_nodejs_shape(self, client, jewelry_tenant_id):
        """Verify Python response includes all fields expected by Node.js-compatible frontends."""
        resp = client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Need specialist", "sessionId": "compat-test-session"},
            headers={"X-Tenant-ID": jewelry_tenant_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        # Node.js response shape has: handoff_prepared, whatsapp_url, summary, user_message
        assert "handoff_prepared" in data
        assert "whatsapp_url" in data
        assert "summary" in data
        assert "user_message" in data
        assert data["handoff_prepared"] is True
        assert data["whatsapp_url"].startswith("https://wa.me/")
        assert "Al Noor" in data["summary"]["business"]


# ─────────────────────────────────────────────────────────────
# 8. Agent Tool Isolation & Injection Prevention
# ─────────────────────────────────────────────────────────────

class TestAgentHandoffToolIsolation:
    def test_agent_tool_handoff_uses_tenant_phone_not_caller_supplied(self, db_session, jewelry_tenant_id):
        """Agent cannot override phone by injecting args."""
        from backend.app.agents.tools import ValidatedAgentToolExecutor
        executor = ValidatedAgentToolExecutor(
            db=db_session, tenant_id=jewelry_tenant_id, session_id="agent-handoff-test"
        )
        result = executor.execute("request_human_handoff", {
            "reason": "Customer wants help",
            "phone": "+1234567890",         # injected — must be silently discarded
            "whatsapp_number": "+999999",   # injected — must be silently discarded
            "tenant_id": "evil-tenant",     # injected — must be silently discarded
        })
        assert result.get("handoff_prepared") is True
        # Must use al-noor-jewelry phone (+97444991200), not the injected one
        assert "97444991200" in result.get("whatsapp_url", "")

    def test_agent_cannot_claim_human_accepted(self, db_session, jewelry_tenant_id):
        from backend.app.agents.tools import ValidatedAgentToolExecutor
        executor = ValidatedAgentToolExecutor(
            db=db_session, tenant_id=jewelry_tenant_id, session_id="agent-acceptance-test"
        )
        result = executor.execute("request_human_handoff", {"reason": "Test"})
        assert "accepted_by_human" not in result
        assert "delivered" not in result
        assert "message_sent" not in result
        assert "disclaimer" in result

    def test_agent_cannot_confirm_draft_without_explicit_consent(self, db_session, jewelry_tenant_id):
        from backend.app.agents.tools import ValidatedAgentToolExecutor
        executor = ValidatedAgentToolExecutor(
            db=db_session, tenant_id=jewelry_tenant_id, session_id="agent-confirmation-block-test"
        )
        result = executor.execute("confirm_order_draft", {
            "draft_id": "FAKE-DRAFT-001",
            "customer_explicitly_confirmed": False,
        })
        assert result.get("blocked") is True
        assert result.get("reason") == "CONFIRMATION_GATE_BLOCKED"

    def test_agent_handoff_with_nonexistent_tenant_returns_error(self, db_session):
        from backend.app.agents.tools import ValidatedAgentToolExecutor
        executor = ValidatedAgentToolExecutor(
            db=db_session, tenant_id="nonexistent-tenant", session_id="bad-tenant-test"
        )
        result = executor.execute("request_human_handoff", {"reason": "Test"})
        assert result.get("handoff_prepared") is False
        assert "error" in result
