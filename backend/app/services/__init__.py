"""
Services package exports
"""

from backend.app.services.catalog_service import CatalogService
from backend.app.services.draft_service import (
    DraftService,
    DraftServiceError,
    DraftNotFoundError,
    CrossTenantAccessError,
    InvalidStateTransitionError,
    InsufficientStockError,
    TenantNotFoundError,
    ProductNotFoundError,
)

__all__ = [
    "CatalogService",
    "DraftService",
    "DraftServiceError",
    "DraftNotFoundError",
    "CrossTenantAccessError",
    "InvalidStateTransitionError",
    "InsufficientStockError",
    "TenantNotFoundError",
    "ProductNotFoundError",
    "BookingService",
    "BookingServiceError",
    "SlotNotFoundError",
    "SlotUnavailableError",
    "InsufficientCapacityError",
]

from backend.app.services.booking_service import (
    BookingService,
    BookingServiceError,
    SlotNotFoundError,
    SlotUnavailableError,
    InsufficientCapacityError,
)

from backend.app.services.handoff_service import (
    HandoffService,
    HandoffServiceError,
    HandoffNotFoundError,
    MissingOrInvalidPhoneError,
)

from backend.app.services.whatsapp_adapter import (
    WhatsAppAdapter,
    InvalidPhoneNumberError,
    MaliciousUrlDestinationError,
)

from backend.app.services.telemetry_service import (
    TelemetryService,
    TelemetryServiceError,
    TenantNotFoundError as TelemetryTenantNotFoundError,
    InvalidEventType,
    ClientFabricationError,
    CrossTenantViolationError as TelemetryCrossTenantViolationError,
    PayloadSizeExceededError,
)

from backend.app.services.analytics_service import AnalyticsService

__all__.extend([
    "HandoffService",
    "HandoffServiceError",
    "HandoffNotFoundError",
    "MissingOrInvalidPhoneError",
    "WhatsAppAdapter",
    "InvalidPhoneNumberError",
    "MaliciousUrlDestinationError",
    "TelemetryService",
    "TelemetryServiceError",
    "TelemetryTenantNotFoundError",
    "InvalidEventType",
    "ClientFabricationError",
    "TelemetryCrossTenantViolationError",
    "PayloadSizeExceededError",
    "AnalyticsService",
])

