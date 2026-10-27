"""
Schemas package exports
"""

from backend.app.schemas.health import DependencyStatus, HealthResponse, ReadinessResponse
from backend.app.schemas.tenant import TenantBase, TenantResponse, TenantListResponse
from backend.app.schemas.product import InventoryInfo, ProductResponse, CatalogResponse
from backend.app.schemas.draft import (
    DraftItemRequest,
    DraftItemResponse,
    DraftCreateRequest,
    DraftUpdateRequest,
    DraftConfirmRequest,
    DraftCancelRequest,
    DraftResponse,
    DraftConfirmResponse,
    DraftCancelResponse,
)

__all__ = [
    "DependencyStatus",
    "HealthResponse",
    "ReadinessResponse",
    "TenantBase",
    "TenantResponse",
    "TenantListResponse",
    "InventoryInfo",
    "ProductResponse",
    "CatalogResponse",
    "DraftItemRequest",
    "DraftItemResponse",
    "DraftCreateRequest",
    "DraftUpdateRequest",
    "DraftConfirmRequest",
    "DraftCancelRequest",
    "DraftResponse",
    "DraftConfirmResponse",
    "DraftCancelResponse",
    "BookingSlotResponse",
    "BookingAvailabilityResponse",
    "BookingCreateRequest",
    "BookingCancelRequest",
    "BookingResponse",
]

from backend.app.schemas.booking import (
    BookingSlotResponse,
    BookingAvailabilityResponse,
    BookingCreateRequest,
    BookingCancelRequest,
    BookingResponse,
)
from backend.app.schemas.handoff import (
    HandoffCreateRequest,
    HandoffCloseRequest,
    HandoffSummary,
    HandoffResponse,
)

from backend.app.schemas.telemetry import (
    BIEventType,
    ALLOWED_EVENT_TYPES,
    CLIENT_REPORTABLE_EVENT_TYPES,
    SERVER_VERIFIED_EVENT_TYPES,
    TelemetryEventCreate,
    TelemetryEventResponse,
    TelemetryIngestResponse,
    TelemetryEventsListResponse,
    DemoSeedRequest,
    DemoSeedResponse,
)
from backend.app.schemas.analytics import (
    FunnelStage,
    FunnelMetrics,
    FunnelResponse,
    ObjectionCategorySummary,
    ObjectionBreakdownItem,
    ObjectionsData,
    ObjectionsResponse,
    DemandSignalsResponse,
    FunnelCounters,
    TelemetrySummaryData,
    TelemetrySummaryResponse,
)

__all__.extend([
    "HandoffCreateRequest",
    "HandoffCloseRequest",
    "HandoffSummary",
    "HandoffResponse",
    "BIEventType",
    "ALLOWED_EVENT_TYPES",
    "CLIENT_REPORTABLE_EVENT_TYPES",
    "SERVER_VERIFIED_EVENT_TYPES",
    "TelemetryEventCreate",
    "TelemetryEventResponse",
    "TelemetryIngestResponse",
    "TelemetryEventsListResponse",
    "DemoSeedRequest",
    "DemoSeedResponse",
    "FunnelStage",
    "FunnelMetrics",
    "FunnelResponse",
    "ObjectionCategorySummary",
    "ObjectionBreakdownItem",
    "ObjectionsData",
    "ObjectionsResponse",
    "DemandSignalsResponse",
    "FunnelCounters",
    "TelemetrySummaryData",
    "TelemetrySummaryResponse",
])

from backend.app.schemas.auth import (
    Permissions,
    ALL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    TokenResponse,
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    LogoutResponse,
    TokenPayload,
    AuthenticatedPrincipal,
    UserResponse,
)

__all__.extend([
    "Permissions",
    "ALL_PERMISSIONS",
    "DEFAULT_ROLE_PERMISSIONS",
    "TokenResponse",
    "LoginRequest",
    "RefreshRequest",
    "LogoutRequest",
    "LogoutResponse",
    "TokenPayload",
    "AuthenticatedPrincipal",
    "UserResponse",
])
