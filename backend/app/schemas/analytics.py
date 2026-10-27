"""
Analytics Pydantic Schemas
Sprint 4 — Business Intelligence & Analytics Migration

Defines validated response schemas for sales conversion funnel, customer objection breakdown,
unfulfilled demand signals, and comprehensive telemetry summaries.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.telemetry import TelemetryEventResponse


class FunnelStage(BaseModel):
    stage: str
    count: int
    conversionRate: str


class FunnelMetrics(BaseModel):
    tenant_id: str
    timeframe_days: int
    overallConversionRate: str
    stages: List[FunnelStage]


class FunnelResponse(BaseModel):
    success: bool = True
    funnel: FunnelMetrics


class ObjectionCategorySummary(BaseModel):
    out_of_stock: int = 0
    unfulfilled_searches: int = 0
    unanswered_questions: int = 0
    cancelled_drafts: int = 0


class ObjectionBreakdownItem(BaseModel):
    event_type: str
    category: Optional[str] = None
    outcome: Optional[str] = None
    count: int


class ObjectionsData(BaseModel):
    tenant_id: str
    timeframe_days: int
    total_objections: int
    summary: ObjectionCategorySummary
    breakdown: List[ObjectionBreakdownItem]


class ObjectionsResponse(BaseModel):
    success: bool = True
    objections: ObjectionsData


class DemandSignalsResponse(BaseModel):
    success: bool = True
    demandSignals: List[TelemetryEventResponse]


class FunnelCounters(BaseModel):
    searches: int = 0
    unfulfilled: int = 0
    out_of_stock: int = 0
    drafts_created: int = 0
    drafts_confirmed: int = 0
    drafts_cancelled: int = 0
    handoffs: int = 0


class TelemetrySummaryData(BaseModel):
    tenant_id: str
    timeframe_days: int
    total_events: int
    by_event_type: Dict[str, int]
    funnel: FunnelCounters


class TelemetrySummaryResponse(BaseModel):
    success: bool = True
    summary: TelemetrySummaryData
