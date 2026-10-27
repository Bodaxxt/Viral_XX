"""
Viral-X Authentication and Authorization Core Module
Sprint 5: Secure Authentication & Authorization

Provides:
- Cryptographic password hashing and verification with bcrypt
- JWT token issuance, signing, expiration, and claims verification with PyJWT
- Principle-to-tenant server-side binding
- Untrusted tenant input rejection (forged headers, query params, bodies)
- Role and permission validation dependencies
- Secure fail-closed behavior
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.models import Tenant, User, RevokedToken
from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    ALL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    AuthenticatedPrincipal,
    Permissions,
)


# ─────────────────────────────────────────────────────────────
# 1. Cryptographic Password Hashing & Verification
# ─────────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hashes a password using bcrypt with automatic salt generation."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as exc:
        logger.warning("Password verification failed with exception: %s", type(exc).__name__)
        return False


# ─────────────────────────────────────────────────────────────
# 2. JWT Token Issuance & Verification
# ─────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    username: str,
    tenant_id: Optional[str] = None,
    role: str = "customer",
    permissions: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    Creates a signed JWT access token with standard claims.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    perms = permissions if permissions is not None else DEFAULT_ROLE_PERMISSIONS.get(role, [])

    payload: Dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": perms,
        "type": "access",
        "iss": issuer or settings.JWT_ISSUER,
        "aud": audience or settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    key = secret_key or settings.JWT_SECRET_KEY
    return jwt.encode(payload, key, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    username: str,
    tenant_id: Optional[str] = None,
    role: str = "customer",
    expires_delta: Optional[timedelta] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    Creates a signed JWT refresh token with standard claims.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS))

    payload: Dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "role": role,
        "type": "refresh",
        "iss": issuer or settings.JWT_ISSUER,
        "aud": audience or settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    key = secret_key or settings.JWT_SECRET_KEY
    return jwt.encode(payload, key, algorithm=settings.JWT_ALGORITHM)


def is_token_revoked(db: Optional[Session], jti: Optional[str]) -> bool:
    """Checks if a token's unique jti has been recorded in the revocation table."""
    if not db or not jti:
        return False
    try:
        revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
        return revoked is not None
    except Exception as exc:
        logger.warning("Error checking token revocation: %s", exc)
        return False


def revoke_token(
    db: Session,
    jti: str,
    token_type: str,
    user_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    reason: str = "revoked",
) -> None:
    """Records a token jti as revoked in the database."""
    if not jti:
        return
    try:
        existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
        if not existing:
            revoked = RevokedToken(
                id=str(uuid.uuid4()),
                jti=jti,
                token_type=token_type,
                user_id=user_id,
                reason=reason,
                expires_at=expires_at,
            )
            db.add(revoked)
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist token revocation: %s", exc)
        raise


def decode_jwt_token(
    token: str,
    expected_type: str = "access",
    expected_issuer: Optional[str] = None,
    expected_audience: Optional[str] = None,
    secret_key: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Decodes and rigorously validates a JWT token: signature, expiration, issuer, audience, and type.
    Rejects algorithm confusion attacks, missing required claims, and revoked tokens.
    Never leaks keys, credentials, or internal exceptions.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token credentials.",
        )

    key = secret_key or settings.JWT_SECRET_KEY
    iss = expected_issuer or settings.JWT_ISSUER
    aud = expected_audience or settings.JWT_AUDIENCE

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=iss,
            audience=aud,
            options={"require": ["exp", "iss", "aud", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        )
    except jwt.ImmatureSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is not yet valid (nbf).",
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer claim.",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience claim.",
        )
    except jwt.PyJWTError as exc:
        logger.warning("JWT validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature or claims.",
        )

    token_type = payload.get("type")
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type: expected '{expected_type}' token, received '{token_type}'.",
        )

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject claim is missing.",
        )

    if not payload.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token unique identifier (jti) claim is missing.",
        )

    # Replay & Revocation verification
    if db and is_token_revoked(db, payload.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked.",
        )

    return payload


# ─────────────────────────────────────────────────────────────
# 3. Principal Resolution & Tenant Binding Dependencies
# ─────────────────────────────────────────────────────────────

def get_current_principal(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    """
    Resolves the authenticated principal from verified Bearer JWT tokens.
    If no Bearer token is provided, checks if development-only header authentication
    is explicitly permitted by settings. Fail-closed in production.
    """
    # 1. Bearer Token Authentication
    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Expected 'Bearer <token>'.",
            )

        raw_token = parts[1]
        payload = decode_jwt_token(raw_token, expected_type="access", db=db)

        user_id = payload["sub"]
        username = payload.get("username", user_id)
        tenant_id = payload.get("tenant_id")
        role = payload.get("role", "customer")
        permissions = payload.get("permissions") or DEFAULT_ROLE_PERMISSIONS.get(role, [])

        return AuthenticatedPrincipal(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
            is_authenticated=True,
            auth_method="bearer_jwt",
            token_jti=payload.get("jti"),
            token_exp=payload.get("exp"),
        )

    # 2. Development / Test Fallback (Disabled in Production)
    if settings.is_dev_header_auth_allowed():
        if x_tenant_id and x_tenant_id.strip():
            clean_tenant = x_tenant_id.strip()
            tenant = db.query(Tenant).filter(Tenant.id == clean_tenant).first()
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Authorized tenant workspace '{clean_tenant}' does not exist.",
                )
            return AuthenticatedPrincipal(
                user_id="dev_user",
                username="dev_user",
                tenant_id=clean_tenant,
                role="admin",
                permissions=ALL_PERMISSIONS,
                is_authenticated=True,
                auth_method="dev_header",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials ('X-Tenant-ID' header or Bearer token required).",
            )

    # 3. Production Environment: Header auth strictly forbidden
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing required Bearer authentication token. Client header authentication is forbidden in this environment.",
    )


def get_authorized_tenant(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> str:
    """
    Enforces tenant binding and authorization boundary:
    1. Resolves tenant from verified principal, NOT from untrusted client header.
    2. Rejects principals with no tenant membership (HTTP 403).
    3. Rejects client-supplied tenant header mismatch (HTTP 403).
    4. Validates that the authorized tenant exists in the database.
    """
    if not principal.tenant_id or not principal.tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated principal has no tenant membership binding.",
        )

    authorized_tenant_id = principal.tenant_id.strip()

    # Reject forged or conflicting client tenant header
    if x_tenant_id and x_tenant_id.strip() != authorized_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tenant authorization mismatch: client provided header '{x_tenant_id.strip()}' "
                f"does not match authenticated principal tenant '{authorized_tenant_id}'."
            ),
        )

    tenant = db.query(Tenant).filter(Tenant.id == authorized_tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Authorized tenant workspace '{authorized_tenant_id}' does not exist.",
        )

    return authorized_tenant_id


def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency factory enforcing that the authenticated principal possesses
    the specified permission (or has ADMIN privilege).
    """
    def dependency(principal: AuthenticatedPrincipal = Depends(get_current_principal)) -> AuthenticatedPrincipal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires '{permission}' permission.",
            )
        return principal
    return dependency


def require_admin(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """
    Enforces administrative permissions.
    """
    if not principal.has_permission(Permissions.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required.",
        )
    return principal


# ─────────────────────────────────────────────────────────────
# 4. User Database Lookup & Verification
# ─────────────────────────────────────────────────────────────

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Looks up a user by username and verifies the local password using bcrypt.
    """
    user = db.query(User).filter(User.username == username, User.is_active == 1).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
