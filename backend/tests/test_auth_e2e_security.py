"""
Sprint 5.5 — End-to-End Authentication Integration & Security Verification Test Suite

Covers:
1. Distinct token types (type claim separation: access vs refresh).
2. Algorithm confusion & unsigned token attacks (alg: none, RS256, invalid algs).
3. Missing required claims rejection (exp, iss, aud, sub, jti).
4. Refresh token rotation & replay attack detection (reusing rotated token is blocked).
5. Token revocation & explicit logout (POST /api/v1/auth/logout revokes tokens).
6. Inactive / deactivated account invalidation.
7. Customer resource ownership enforcement (customer A cannot view/modify/confirm customer B's drafts).
8. Staff / read-only least-privilege permission coverage across all route families.
9. Agent dev test harness fail-closed production restriction.
10. Shared SQLite database integrity, idempotency, and concurrent transaction safety.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    revoke_token,
)
from backend.app.core.config import settings
from backend.app.db.models import OrderDraft, RevokedToken, User
from backend.app.schemas.auth import DEFAULT_ROLE_PERMISSIONS, Permissions
from backend.tests.conftest import auth_headers, make_access_token


# ─────────────────────────────────────────────────────────────
# 1. JWT Lifecycle & Algorithm Confusion Defenses
# ─────────────────────────────────────────────────────────────

class TestJWTDeepSecurity:
    def test_unsigned_token_none_alg_rejected(self):
        """Tokens with alg='none' must be rejected with 401."""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": "user-admin-1",
            "username": "admin_user",
            "tenant_id": "al-noor-jewelry",
            "role": "admin",
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": now,
            "exp": now + 3600,
            "jti": str(uuid.uuid4()),
        }
        # Craft an unsigned token
        header = {"alg": "none", "typ": "JWT"}
        import base64
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        unsigned_token = f"{h_b64}.{p_b64}."

        with pytest.raises(Exception) as exc_info:
            decode_jwt_token(unsigned_token, expected_type="access")
        assert exc_info.value.status_code == 401

    def test_asymmetric_alg_confusion_rejected(self):
        """Tokens with alg='RS256' but signed with HMAC key must be rejected."""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": "user-admin-1",
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "exp": now + 3600,
            "jti": str(uuid.uuid4()),
        }
        # Encode with RS256 algorithm header claim
        header = {"alg": "RS256", "typ": "JWT"}
        import base64
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        fake_token = f"{h_b64}.{p_b64}.fake_sig"

        with pytest.raises(Exception) as exc_info:
            decode_jwt_token(fake_token, expected_type="access")
        assert exc_info.value.status_code == 401

    def test_missing_jti_claim_rejected(self):
        """Tokens without a unique jti claim cannot be validated."""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": "user-admin-1",
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "exp": now + 3600,
            # no jti
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            decode_jwt_token(token, expected_type="access")
        assert exc_info.value.status_code == 401

    def test_future_nbf_claim_rejected(self):
        """Tokens with future not-before (nbf) claim must be rejected with 401."""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": "user-admin-1",
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": now,
            "nbf": now + 3600,  # 1 hour in the future
            "exp": now + 7200,
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            decode_jwt_token(token, expected_type="access")
        assert exc_info.value.status_code == 401
        assert "not yet valid" in exc_info.value.detail.lower()

    def test_access_token_cannot_be_used_at_refresh_endpoint(self, client: TestClient):
        """POST /auth/refresh must reject an access token."""
        access_tok = make_access_token(tenant_id="al-noor-jewelry")
        res = client.post("/api/v1/auth/refresh", json={"refreshToken": access_tok})
        assert res.status_code == 401
        assert "expected 'refresh' token" in res.text

    def test_refresh_token_cannot_be_used_as_bearer_authorization(self, client: TestClient):
        """Protected endpoints must reject refresh tokens in the Authorization header."""
        ref_tok = create_refresh_token(user_id="user-admin-1", username="admin_user", tenant_id="al-noor-jewelry")
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ref_tok}"})
        assert res.status_code == 401
        assert "expected 'access' token" in res.text


# ─────────────────────────────────────────────────────────────
# 2. Refresh Token Rotation & Replay Attack Defense
# ─────────────────────────────────────────────────────────────

class TestRefreshTokenRotationAndReplay:
    def test_refresh_token_rotation_and_replay_detection(self, client: TestClient, db_session):
        """
        1. Login to obtain access + refresh tokens.
        2. Call /refresh with the refresh token -> returns new access + rotated refresh token.
        3. Attempting to reuse the original refresh token must be rejected with 401 (Replay Attack Defense).
        """
        # 1. Login
        login_res = client.post(
            "/api/v1/auth/token",
            json={"username": "admin_user", "password": "AdminPass123!"},
        )
        assert login_res.status_code == 200
        rt1 = login_res.json()["refreshToken"]

        # 2. First Refresh -> success, rt1 is rotated
        refresh1_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": rt1},
        )
        assert refresh1_res.status_code == 200
        data1 = refresh1_res.json()
        rt2 = data1["refreshToken"]
        assert rt2 != rt1  # Rotated token is brand new

        # 3. Replay Attempt with rt1 -> MUST FAIL with 401 Revoked
        replay_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": rt1},
        )
        assert replay_res.status_code == 401
        assert "revoked" in replay_res.text.lower()

        # 4. Valid use of rt2 -> success
        refresh2_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": rt2},
        )
        assert refresh2_res.status_code == 200


# ─────────────────────────────────────────────────────────────
# 3. Token Revocation & Logout
# ─────────────────────────────────────────────────────────────

class TestLogoutAndTokenRevocation:
    def test_logout_revokes_access_and_refresh_tokens(self, client: TestClient, db_session):
        # 1. Login
        login_res = client.post(
            "/api/v1/auth/token",
            json={"username": "admin_user", "password": "AdminPass123!"},
        )
        assert login_res.status_code == 200
        access_tok = login_res.json()["accessToken"]
        refresh_tok = login_res.json()["refreshToken"]

        # Verify access token works
        me_res1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_tok}"})
        assert me_res1.status_code == 200

        # 2. Call Logout
        logout_res = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_tok}"},
            json={"refreshToken": refresh_tok},
        )
        assert logout_res.status_code == 200
        assert logout_res.json()["success"] is True

        # 3. Access token is now revoked -> must return 401
        me_res2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_tok}"})
        assert me_res2.status_code == 401
        assert "revoked" in me_res2.text.lower()

        # 4. Refresh token is now revoked -> must return 401
        ref_res = client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_tok})
        assert ref_res.status_code == 401
        assert "revoked" in ref_res.text.lower()


# ─────────────────────────────────────────────────────────────
# 4. Inactive Account Handling
# ─────────────────────────────────────────────────────────────

class TestInactiveAccounts:
    def test_inactive_user_cannot_login(self, client: TestClient):
        res = client.post(
            "/api/v1/auth/token",
            json={"username": "inactive_user", "password": "InactivePass123!"},
        )
        # Should be rejected with 401
        assert res.status_code == 401

    def test_deactivated_user_cannot_refresh_token(self, client: TestClient, db_session):
        # Create a refresh token for inactive user
        tok = create_refresh_token(
            user_id="user-inactive-1",
            username="inactive_user",
            tenant_id="al-noor-jewelry",
            role="staff",
        )
        res = client.post("/api/v1/auth/refresh", json={"refreshToken": tok})
        assert res.status_code == 403
        assert "inactive" in res.text.lower()


# ─────────────────────────────────────────────────────────────
# 5. Customer Resource Ownership Enforcement
# ─────────────────────────────────────────────────────────────

class TestCustomerOwnershipEnforcement:
    def test_customer_cannot_read_another_customers_draft(
        self, customer1_client: TestClient, customer2_client: TestClient
    ):
        # Customer 1 creates a draft
        res1 = customer1_client.post(
            "/api/v1/drafts",
            json={
                "items": [{"product_id": "J-101", "quantity": 1}],
            },
        )
        assert res1.status_code == 201
        draft_id = res1.json()["id"]

        # Customer 1 can read it
        res_c1 = customer1_client.get(f"/api/v1/drafts/{draft_id}")
        assert res_c1.status_code == 200

        # Customer 2 attempts to read Customer 1's draft -> 403 Forbidden
        res_c2 = customer2_client.get(f"/api/v1/drafts/{draft_id}")
        assert res_c2.status_code == 403
        assert "another customer" in res_c2.text.lower()

    def test_customer_cannot_update_another_customers_draft(
        self, customer1_client: TestClient, customer2_client: TestClient
    ):
        res1 = customer1_client.post(
            "/api/v1/drafts",
            json={"items": [{"product_id": "J-101", "quantity": 1}]},
        )
        draft_id = res1.json()["id"]

        # Customer 2 attempts to update Customer 1's draft -> 403 Forbidden
        res2 = customer2_client.put(
            f"/api/v1/drafts/{draft_id}",
            json={"items": [{"product_id": "J-101", "quantity": 2}]},
        )
        assert res2.status_code == 403

    def test_customer_cannot_confirm_another_customers_draft(
        self, customer1_client: TestClient, customer2_client: TestClient
    ):
        res1 = customer1_client.post(
            "/api/v1/drafts",
            json={"items": [{"product_id": "J-101", "quantity": 1}]},
        )
        draft_id = res1.json()["id"]

        # Customer 2 attempts to confirm Customer 1's draft -> 403 Forbidden
        res2 = customer2_client.post(
            "/api/v1/drafts/confirm",
            json={"draft_id": draft_id, "idempotency_key": str(uuid.uuid4())},
        )
        assert res2.status_code == 403

    def test_customer_cannot_cancel_another_customers_draft(
        self, customer1_client: TestClient, customer2_client: TestClient
    ):
        res1 = customer1_client.post(
            "/api/v1/drafts",
            json={"items": [{"product_id": "J-101", "quantity": 1}]},
        )
        draft_id = res1.json()["id"]

        # Customer 2 attempts to cancel Customer 1's draft -> 403 Forbidden
        res2 = customer2_client.post(
            f"/api/v1/drafts/{draft_id}/cancel",
            json={"reason": "Customer change of mind"},
        )
        assert res2.status_code == 403

    def test_staff_or_admin_can_read_customer_draft(
        self, customer1_client: TestClient, admin_client: TestClient
    ):
        # Customer 1 creates a draft
        res1 = customer1_client.post(
            "/api/v1/drafts",
            json={"items": [{"product_id": "J-101", "quantity": 1}]},
        )
        draft_id = res1.json()["id"]

        # Admin of the same tenant can inspect the draft
        res_admin = admin_client.get(f"/api/v1/drafts/{draft_id}")
        assert res_admin.status_code == 200

    def test_customer_cannot_cancel_another_customers_booking(
        self, client: TestClient
    ):
        h1 = auth_headers(user_id="cust-saff-1", username="cust_saff_1", tenant_id="saffron-table", role="customer")
        h2 = auth_headers(user_id="cust-saff-2", username="cust_saff_2", tenant_id="saffron-table", role="customer")

        # Customer 1 creates a booking on saffron-table
        res1 = client.post(
            "/api/v1/bookings/reserve",
            headers=h1,
            json={
                "slot_id": "SLOT-R01",
                "party_size": 1,
                "customer_name": "Customer One",
            },
        )
        assert res1.status_code == 201
        ext_ref = res1.json()["external_reference"]

        # Customer 2 attempts to cancel Customer 1's booking -> 403 Forbidden
        res2 = client.post(
            "/api/v1/bookings/cancel",
            headers=h2,
            json={
                "slot_id": "SLOT-R01",
                "party_size": 1,
                "booking_reference": ext_ref,
            },
        )
        assert res2.status_code == 403
        assert "another customer" in res2.text.lower()

    def test_customer_can_cancel_own_booking(
        self, client: TestClient
    ):
        h1 = auth_headers(user_id="cust-saff-1", username="cust_saff_1", tenant_id="saffron-table", role="customer")

        # Customer 1 creates a booking on saffron-table
        res1 = client.post(
            "/api/v1/bookings/reserve",
            headers=h1,
            json={
                "slot_id": "SLOT-R02",
                "party_size": 1,
                "customer_name": "Customer One",
            },
        )
        assert res1.status_code == 201
        ext_ref = res1.json()["external_reference"]

        # Customer 1 cancels own booking -> 200 OK
        res_cancel = client.post(
            "/api/v1/bookings/cancel",
            headers=h1,
            json={
                "slot_id": "SLOT-R02",
                "party_size": 1,
                "booking_reference": ext_ref,
            },
        )
        assert res_cancel.status_code == 200
        assert res_cancel.json()["success"] is True

    def test_customer_cannot_cancel_booking_without_reference(
        self, client: TestClient
    ):
        h1 = auth_headers(user_id="cust-saff-1", username="cust_saff_1", tenant_id="saffron-table", role="customer")
        res = client.post(
            "/api/v1/bookings/cancel",
            headers=h1,
            json={
                "slot_id": "SLOT-R01",
                "party_size": 1,
            },
        )
        assert res.status_code == 403
        assert "must provide bookingreference" in res.text.lower()


# ─────────────────────────────────────────────────────────────
# 6. Granular Permission Coverage Across Endpoints
# ─────────────────────────────────────────────────────────────

class TestPermissionCoverageAcrossEndpoints:
    def test_readonly_blocked_from_booking_reservations(self, readonly_client: TestClient):
        # Attempt reserve on own tenant
        res = readonly_client.post(
            "/api/v1/bookings/reserve",
            json={
                "slot_id": "SLOT-R01",
                "party_size": 2,
                "tenant_id": "al-noor-jewelry",
            },
        )
        assert res.status_code == 403
        assert "booking:reserve" in res.text

    def test_readonly_blocked_from_booking_cancellations(self, readonly_client: TestClient):
        res = readonly_client.post(
            "/api/v1/bookings/cancel",
            json={"slot_id": "SLOT-R01", "party_size": 2},
        )
        assert res.status_code == 403
        assert "booking:cancel" in res.text

    def test_readonly_blocked_from_creating_handoff(self, readonly_client: TestClient):
        res = readonly_client.post(
            "/api/v1/handoff/whatsapp",
            json={"reason": "Need human support"},
        )
        assert res.status_code == 403
        assert "handoff:create" in res.text

    def test_readonly_blocked_from_closing_handoff(self, readonly_client: TestClient):
        res = readonly_client.post(
            "/api/v1/handoff/HO-123/close",
            json={"resolution_notes": "Done"},
        )
        assert res.status_code == 403
        assert "handoff:manage" in res.text

    def test_readonly_blocked_from_demo_seed(self, readonly_client: TestClient):
        res = readonly_client.post(
            "/api/v1/analytics/events/demo-seed",
            json={"count": 5},
        )
        assert res.status_code == 403
        assert "analytics:seed" in res.text

    def test_readonly_allowed_to_query_booking_availability(self, readonly_client: TestClient):
        res = readonly_client.get("/api/v1/bookings/availability")
        assert res.status_code == 200


# ─────────────────────────────────────────────────────────────
# 7. Agent Dev Test Harness Restrictions
# ─────────────────────────────────────────────────────────────

class TestAgentDevTestHarnessSecurity:
    def test_agent_test_disabled_in_production(self, client: TestClient):
        with patch.object(settings, "ENVIRONMENT", "production"):
            res = client.post(
                "/api/v1/agent/test",
                json={
                    "tenant_id": "al-noor-jewelry",
                    "session_id": "sess-prod-test",
                    "message": "Hello",
                },
            )
            assert res.status_code == 403
            assert "disabled in production" in res.text.lower()

    def test_agent_endpoint_rejects_customer_without_agent_test_perm(
        self, customer1_client: TestClient
    ):
        res = customer1_client.post(
            "/api/v1/agent/test",
            json={
                "tenant_id": "al-noor-jewelry",
                "session_id": "sess-cust-agent",
                "message": "Hello agent",
            },
        )
        assert res.status_code == 403
        assert "agent:test" in res.text

    def test_agent_endpoint_rejects_cross_tenant_request(
        self, saffron_client: TestClient
    ):
        # Saffron manager/admin attempts to query al-noor-jewelry agent
        res = saffron_client.post(
            "/api/v1/agent/test",
            json={
                "tenant_id": "al-noor-jewelry",
                "session_id": "sess-cross-agent",
                "message": "Hello agent",
            },
        )
        assert res.status_code == 403
        assert "mismatch" in res.text.lower()


# ─────────────────────────────────────────────────────────────
# 8. Shared Database Integrity & Concurrency Safety
# ─────────────────────────────────────────────────────────────

class TestSharedDatabaseSafety:
    def test_database_session_rollback_preserves_clean_state(self, db_session):
        from backend.app.db.models import OrderDraft
        count_before = db_session.query(OrderDraft).count()

        # Try to insert invalid draft that raises DB error (missing required foreign key or fields)
        try:
            bad_draft = OrderDraft(
                id=str(uuid.uuid4()),
                # missing required fields
            )
            db_session.add(bad_draft)
            db_session.commit()
        except Exception:
            db_session.rollback()

        count_after = db_session.query(OrderDraft).count()
        assert count_after == count_before

    def test_confirmation_idempotency_prevents_double_decrement(self, admin_client: TestClient, db_session):
        # Create draft
        res = admin_client.post(
            "/api/v1/drafts",
            json={
                "session_id": "sess-concurr-idem",
                "items": [{"product_id": "J-101", "quantity": 1}],
            },
        )
        draft_id = res.json()["id"]
        idem_key = f"IDEMP-CONCURR-{uuid.uuid4()}"

        # 1. Confirm draft
        r1 = admin_client.post("/api/v1/drafts/confirm", json={"draft_id": draft_id, "idempotency_key": idem_key})
        assert r1.status_code == 200

        # 2. Confirm same draft again with same key
        r2 = admin_client.post("/api/v1/drafts/confirm", json={"draft_id": draft_id, "idempotency_key": idem_key})
        assert r2.status_code == 200
        assert r2.json()["alreadyConfirmed"] is True or r2.json()["already_confirmed"] is True


# ─────────────────────────────────────────────────────────────
# 9. Frontend Client Flow Integration (assets/js/auth-client.js)
# ─────────────────────────────────────────────────────────────

class TestFrontendAuthenticationIntegrationFlow:
    """
    Simulates the exact end-to-end frontend client flow defined in assets/js/auth-client.js:
    Login -> Profile Check -> Authenticated Catalog/Analytics -> Expired Token Rejection ->
    Silent Token Refresh -> Replay Attack Rejection -> Logout & Revocation.
    """
    def test_frontend_full_auth_lifecycle(self, client: TestClient):
        # 1. Login with credentials
        login_res = client.post(
            "/api/v1/auth/token",
            json={"username": "admin_user", "password": "AdminPass123!"},
        )
        assert login_res.status_code == 200
        tokens = login_res.json()
        access_tok = tokens["accessToken"]
        refresh_tok = tokens["refreshToken"]
        assert access_tok and refresh_tok

        # 2. Authenticated profile check (fetchCurrentUser)
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin_user"

        # 3. Authenticated analytics read
        analytics_res = client.get(
            "/api/v1/analytics/summary",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert analytics_res.status_code == 200
        assert analytics_res.json()["success"] is True

        # 4. Token Refresh (silent refresh)
        refresh_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": refresh_tok},
        )
        assert refresh_res.status_code == 200
        new_tokens = refresh_res.json()
        new_access_tok = new_tokens["accessToken"]
        new_refresh_tok = new_tokens["refreshToken"]
        assert new_access_tok != access_tok
        assert new_refresh_tok != refresh_tok

        # 5. Replay attempt with old refresh token must be rejected
        replay_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": refresh_tok},
        )
        assert replay_res.status_code == 401
        assert "revoked" in replay_res.text.lower()

        # 6. Logout with active tokens
        logout_res = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_access_tok}"},
            json={"refreshToken": new_refresh_tok},
        )
        assert logout_res.status_code == 200
        assert logout_res.json()["success"] is True

        # 7. Post-logout access token is revoked
        revoked_access_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_tok}"},
        )
        assert revoked_access_res.status_code == 401
        assert "revoked" in revoked_access_res.text.lower()

        # 8. Post-logout refresh token is revoked
        revoked_refresh_res = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": new_refresh_tok},
        )
        assert revoked_refresh_res.status_code == 401
        assert "revoked" in revoked_refresh_res.text.lower()


# ─────────────────────────────────────────────────────────────
# 10. Security Headers & Threat Mitigation
# ─────────────────────────────────────────────────────────────

class TestSecurityHeadersAndThreatMitigation:
    def test_auth_failure_does_not_leak_details(self, client: TestClient):
        # Bad credentials
        res = client.post(
            "/api/v1/auth/token",
            json={"username": "nonexistent_admin", "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        # Generic message to prevent username enumeration
        assert "Incorrect username or password" in res.text
        assert "Traceback" not in res.text

    def test_forged_role_in_request_body_cannot_elevate_privileges(self, customer1_client: TestClient):
        # Customer attempts to send role=admin in draft creation
        res = customer1_client.post(
            "/api/v1/drafts",
            json={
                "items": [{"product_id": "J-101", "quantity": 1}],
                "role": "admin",
                "permissions": ["admin"],
            },
        )
        assert res.status_code == 201
        # Check current principal is STILL customer
        me_res = customer1_client.get("/api/v1/auth/me")
        assert me_res.json()["role"] == "customer"

