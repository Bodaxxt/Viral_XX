"""
Pydantic Schemas for Authentication and Authorization
Sprint 5: Secure Authentication & Authorization
"""

from typing import List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


class Permissions:
    READ = "read"
    DRAFT_CREATE = "draft:create"
    DRAFT_UPDATE = "draft:update"
    DRAFT_CONFIRM = "draft:confirm"
    DRAFT_CANCEL = "draft:cancel"
    BOOKING_READ = "booking:read"
    BOOKING_RESERVE = "booking:reserve"
    BOOKING_CANCEL = "booking:cancel"
    HANDOFF_CREATE = "handoff:create"
    HANDOFF_MANAGE = "handoff:manage"
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_SEED = "analytics:seed"
    ANALYTICS_EVENTS = "analytics:events"
    AGENT_TEST = "agent:test"
    ADMIN = "admin"


ALL_PERMISSIONS: List[str] = [
    Permissions.ADMIN,
    Permissions.READ,
    Permissions.DRAFT_CREATE,
    Permissions.DRAFT_UPDATE,
    Permissions.DRAFT_CONFIRM,
    Permissions.DRAFT_CANCEL,
    Permissions.BOOKING_READ,
    Permissions.BOOKING_RESERVE,
    Permissions.BOOKING_CANCEL,
    Permissions.HANDOFF_CREATE,
    Permissions.HANDOFF_MANAGE,
    Permissions.ANALYTICS_READ,
    Permissions.ANALYTICS_SEED,
    Permissions.ANALYTICS_EVENTS,
    Permissions.AGENT_TEST,
]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": ALL_PERMISSIONS,
    "manager": [
        Permissions.READ,
        Permissions.DRAFT_CREATE,
        Permissions.DRAFT_UPDATE,
        Permissions.DRAFT_CONFIRM,
        Permissions.DRAFT_CANCEL,
        Permissions.BOOKING_READ,
        Permissions.BOOKING_RESERVE,
        Permissions.BOOKING_CANCEL,
        Permissions.HANDOFF_CREATE,
        Permissions.HANDOFF_MANAGE,
        Permissions.ANALYTICS_READ,
        Permissions.ANALYTICS_SEED,
        Permissions.ANALYTICS_EVENTS,
        Permissions.AGENT_TEST,
    ],
    "staff": [
        Permissions.READ,
        Permissions.DRAFT_CREATE,
        Permissions.DRAFT_UPDATE,
        Permissions.DRAFT_CANCEL,
        Permissions.BOOKING_READ,
        Permissions.BOOKING_RESERVE,
        Permissions.BOOKING_CANCEL,
        Permissions.HANDOFF_CREATE,
        Permissions.HANDOFF_MANAGE,
        Permissions.ANALYTICS_READ,
        Permissions.ANALYTICS_EVENTS,
    ],
    "customer": [
        Permissions.READ,
        Permissions.DRAFT_CREATE,
        Permissions.DRAFT_UPDATE,
        Permissions.DRAFT_CONFIRM,
        Permissions.DRAFT_CANCEL,
        Permissions.BOOKING_READ,
        Permissions.BOOKING_RESERVE,
        Permissions.BOOKING_CANCEL,
        Permissions.HANDOFF_CREATE,
        Permissions.ANALYTICS_EVENTS,
    ],
    "read_only": [
        Permissions.READ,
        Permissions.BOOKING_READ,
        Permissions.ANALYTICS_READ,
    ],
}


class TokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = Field("bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn", description="Expiration time in seconds")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken", min_length=10)


class TokenPayload(BaseModel):
    sub: str
    username: Optional[str] = None
    tenant_id: Optional[str] = None
    role: str = "customer"
    permissions: List[str] = Field(default_factory=list)
    type: str = "access"  # "access" or "refresh"
    iss: str
    aud: str
    exp: int
    iat: int
    jti: str


class AuthenticatedPrincipal(BaseModel):
    """
    Verified Principal resolved from server-side credentials.
    """
    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    username: str
    tenant_id: Optional[str] = None
    role: str = "customer"
    permissions: List[str] = Field(default_factory=list)
    is_authenticated: bool = True
    auth_method: str = "bearer_jwt"  # "bearer_jwt" | "dev_header"
    token_jti: Optional[str] = None
    token_exp: Optional[int] = None

    def has_permission(self, permission: str) -> bool:
        """Checks if principal has the requested permission or ADMIN power."""
        return (Permissions.ADMIN in self.permissions) or (permission in self.permissions)

    def has_any_permission(self, *permissions: str) -> bool:
        return any(self.has_permission(p) for p in permissions)


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    username: str
    tenant_id: Optional[str] = Field(None, alias="tenantId")
    role: str
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = Field(True, alias="isActive")


class LogoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: Optional[str] = Field(None, alias="refreshToken")


class LogoutResponse(BaseModel):
    success: bool = True
    message: str = "Successfully logged out. Tokens have been revoked."
