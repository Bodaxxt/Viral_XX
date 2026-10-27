"""
Authentication Endpoints: Token Generation, Refresh, and Principal Information
Sprint 5: Secure Authentication & Authorization
"""

import json
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from backend.app.core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    get_current_principal,
    revoke_token,
)
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.models import Tenant, User
from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    DEFAULT_ROLE_PERMISSIONS,
    AuthenticatedPrincipal,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login & Token Issuance",
    description="Authenticates local user credentials and issues signed short-lived access and refresh JWT tokens.",
)
def login_for_access_token(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_user(db=db, username=request.username, password=request.password)
    if not user:
        # Generic error message to prevent username enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Resolve custom permissions if configured, otherwise use role defaults
    permissions = None
    if user.permissions_json:
        try:
            permissions = json.loads(user.permissions_json)
        except Exception:
            permissions = None
    if not permissions:
        permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        role=user.role,
        permissions=permissions,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        role=user.role,
    )

    expires_in_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token (With Rotation & Replay Protection)",
    description=(
        "Validates a refresh token, ensures it has not been revoked or replayed, "
        "immediately revokes the old refresh token, and issues a new access token and rotated refresh token."
    ),
)
def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    payload = decode_jwt_token(request.refresh_token, expected_type="refresh", db=db)

    user_id = payload.get("sub")
    username = payload.get("username", user_id)
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "customer")
    old_jti = payload.get("jti")

    # If user exists in DB, ensure user is still active
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )
        tenant_id = user.tenant_id
        role = user.role
        permissions = None
        if user.permissions_json:
            try:
                permissions = json.loads(user.permissions_json)
            except Exception:
                permissions = None
        if not permissions:
            permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
    else:
        permissions = DEFAULT_ROLE_PERMISSIONS.get(role, [])

    # Token Rotation & Replay Prevention:
    # Immediately revoke the consumed refresh token so it cannot be used again
    if old_jti:
        exp_dt = None
        if payload.get("exp"):
            exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        revoke_token(
            db=db,
            jti=old_jti,
            token_type="refresh",
            user_id=user_id,
            expires_at=exp_dt,
            reason="token_rotated",
        )

    new_access_token = create_access_token(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        role=role,
        permissions=permissions,
    )
    new_refresh_token = create_refresh_token(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        role=role,
    )

    expires_in_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout & Token Revocation",
    description="Explicitly revokes active access and refresh tokens, invalidating the session.",
)
def logout(
    request: LogoutRequest = LogoutRequest(),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    # Revoke current access token if it has a jti
    if principal.token_jti:
        exp_dt = None
        if principal.token_exp:
            exp_dt = datetime.fromtimestamp(principal.token_exp, tz=timezone.utc)
        revoke_token(
            db=db,
            jti=principal.token_jti,
            token_type="access",
            user_id=principal.user_id,
            expires_at=exp_dt,
            reason="logout",
        )

    # If refresh token was supplied in body, revoke it as well
    if request.refresh_token and request.refresh_token.strip():
        try:
            refresh_payload = decode_jwt_token(request.refresh_token, expected_type="refresh")
            if refresh_payload.get("jti"):
                exp_dt = None
                if refresh_payload.get("exp"):
                    exp_dt = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
                revoke_token(
                    db=db,
                    jti=refresh_payload["jti"],
                    token_type="refresh",
                    user_id=principal.user_id,
                    expires_at=exp_dt,
                    reason="logout",
                )
        except Exception as exc:
            logger.info("Optional refresh token decode on logout encountered non-fatal error: %s", exc)

    return LogoutResponse(
        success=True,
        message="Successfully logged out. Tokens have been revoked.",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Authenticated Principal",
    description="Returns the details, tenant binding, and permissions of the caller.",
)
def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> UserResponse:
    return UserResponse(
        id=principal.user_id,
        username=principal.username,
        tenant_id=principal.tenant_id,
        role=principal.role,
        permissions=principal.permissions,
        is_active=True,
    )
