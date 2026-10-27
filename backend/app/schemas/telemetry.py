"""
Telemetry Pydantic Schemas
Sprint 4 — Business Intelligence & Analytics Migration

Defines validated schemas for telemetry event ingestion, query filtering,
event responses, and demo seed generation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BIEventType(str, Enum):
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    UNFULFILLED_DEMAND = "UNFULFILLED_DEMAND"
    OUT_OF_STOCK_DETECTED = "OUT_OF_STOCK_DETECTED"
    UNANSWERED_QUESTION = "UNANSWERED_QUESTION"
    DRAFT_CREATED = "DRAFT_CREATED"
    DRAFT_UPDATED = "DRAFT_UPDATED"
    DRAFT_CANCELLED = "DRAFT_CANCELLED"
    DRAFT_CONFIRMED = "DRAFT_CONFIRMED"
    HUMAN_HANDOFF_REQUESTED = "HUMAN_HANDOFF_REQUESTED"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    LLM_PROVIDER_FAILED = "LLM_PROVIDER_FAILED"
    SECURITY_GUARDRAIL_TRIGGERED = "SECURITY_GUARDRAIL_TRIGGERED"


# Set of all valid event types for strict validation
ALLOWED_EVENT_TYPES = frozenset(e.value for e in BIEventType)

# Events that untrusted clients are permitted to report (behavioral signals)
CLIENT_REPORTABLE_EVENT_TYPES = frozenset({
    BIEventType.PRODUCT_SEARCH.value,
    BIEventType.UNFULFILLED_DEMAND.value,
    BIEventType.UNANSWERED_QUESTION.value,
})

# Events that represent server-verified state transitions
SERVER_VERIFIED_EVENT_TYPES = frozenset({
    BIEventType.DRAFT_CREATED.value,
    BIEventType.DRAFT_UPDATED.value,
    BIEventType.DRAFT_CANCELLED.value,
    BIEventType.DRAFT_CONFIRMED.value,
    BIEventType.HUMAN_HANDOFF_REQUESTED.value,
    BIEventType.TOOL_EXECUTION_FAILED.value,
    BIEventType.LLM_PROVIDER_FAILED.value,
    BIEventType.SECURITY_GUARDRAIL_TRIGGERED.value,
    BIEventType.OUT_OF_STOCK_DETECTED.value,
})


class TelemetryEventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: Optional[str] = Field(None, alias="tenantId", description="Target tenant workspace ID")
    event_type: str = Field(..., alias="eventType", description="Standard BI event type")
    session_id: Optional[str] = Field(None, alias="sessionId", description="Associated customer chat session ID")
    category: Optional[str] = Field(None, description="Event category e.g. search, inventory, product_order")
    product_id: Optional[str] = Field(None, alias="productId", description="Catalog product ID if applicable")
    sku: Optional[str] = Field(None, description="Product SKU code if applicable")
    draft_id: Optional[str] = Field(None, alias="draftId", description="Order draft ID if applicable")
    outcome: Optional[str] = Field("success", description="Outcome string e.g. success, no_results, out_of_stock")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Sanitized event metadata")
    is_demo: Optional[bool] = Field(None, alias="isDemo", description="Whether this event belongs to demo traffic")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey", description="Unique idempotency key")
    schema_version: Optional[str] = Field("1.0", alias="schemaVersion", description="Telemetry schema version")


class TelemetryEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: str = Field(..., alias="tenantId")
    session_id: Optional[str] = Field(None, alias="sessionId")
    event_type: str = Field(..., alias="eventType")
    category: Optional[str] = None
    product_id: Optional[str] = Field(None, alias="productId")
    sku: Optional[str] = None
    draft_id: Optional[str] = Field(None, alias="draftId")
    outcome: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_demo: bool = Field(..., alias="isDemo")
    schema_version: str = Field("1.0", alias="schemaVersion")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    created_at: Optional[str] = Field(None, alias="createdAt")


class TelemetryIngestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    duplicate: bool = False
    event: TelemetryEventResponse


class TelemetryEventsListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    count: int
    events: List[TelemetryEventResponse]


class DemoSeedRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field("al-noor-jewelry", alias="tenantId", description="Target tenant for demo seeds")


class DemoSeedResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: str
    events_count: int = Field(..., alias="eventsCount")
