"""
Analytics & Telemetry API Endpoints
Sprint 4 — Business Intelligence & Analytics Migration

Exposes secure, versioned, tenant-isolated endpoints for:
- Telemetry event ingestion (with client fabrication defenses)
- Telemetry event query listing
- 5-stage conversion funnel metrics
- Customer objection breakdowns
- Unfulfilled demand signals
- Consolidated telemetry summaries
- Repeatable demo event seeding

Sprint 5: Uses centralized authenticated principal resolution from core.auth.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.core.auth import get_authorized_tenant, require_permission
from backend.app.schemas.auth import Permissions
from backend.app.schemas.analytics import (
    DemandSignalsResponse,
    FunnelResponse,
    ObjectionsResponse,
    TelemetrySummaryResponse,
)
from backend.app.schemas.telemetry import (
    DemoSeedRequest,
    DemoSeedResponse,
    TelemetryEventCreate,
    TelemetryEventsListResponse,
    TelemetryIngestResponse,
)
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.telemetry_service import (
    ClientFabricationError,
    CrossTenantViolationError,
    InvalidEventType,
    PayloadSizeExceededError,
    TelemetryService,
    TelemetryServiceError,
    TenantNotFoundError,
)
from backend.app.core.logging import logger

router = APIRouter(prefix="/analytics", tags=["analytics"])



def _map_analytics_error(exc: Exception) -> HTTPException:
    """Maps domain service exceptions to safe, structured HTTP exceptions without stack traces."""
    if isinstance(exc, TenantNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    elif isinstance(exc, ClientFabricationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    elif isinstance(exc, CrossTenantViolationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    elif isinstance(exc, PayloadSizeExceededError):
        return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    elif isinstance(exc, (InvalidEventType, TelemetryServiceError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    else:
        logger.error(f"Unexpected analytics error: {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal analytics processing error occurred.",
        )


@router.get("/events", response_model=TelemetryEventsListResponse)
def get_telemetry_events(
    tenant_id_query: Optional[str] = Query(None, alias="tenantId"),
    event_type: Optional[str] = Query(None, alias="eventType"),
    session_id: Optional[str] = Query(None, alias="sessionId"),
    is_demo: Optional[bool] = Query(None, alias="isDemo"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_READ)),
):
    """
    Queries telemetry events for the authorized tenant workspace.
    Enforces strict tenant scoping and pagination.
    """
    if tenant_id_query and tenant_id_query != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access forbidden. Authorized for '{authorized_tenant}' but requested '{tenant_id_query}'.",
        )

    service = TelemetryService(db)
    try:
        events = service.get_events(
            tenant_id=authorized_tenant,
            event_type=event_type,
            session_id=session_id,
            is_demo=is_demo,
            limit=limit,
            offset=offset,
        )
        return {
            "tenantId": authorized_tenant,
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        raise _map_analytics_error(e)


@router.post("/events", response_model=TelemetryIngestResponse)
def ingest_telemetry_event(
    event_req: TelemetryEventCreate,
    x_source: Optional[str] = Header("client", alias="X-Internal-Source"),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_EVENTS)),
):
    """
    Ingests a validated BI telemetry event.
    Rejects client attempts to fabricate server-verified business outcomes.
    """
    if event_req.tenant_id and event_req.tenant_id != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant event ingestion forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = TelemetryService(db)
    try:
        result = service.record_event(
            tenant_id=authorized_tenant,
            event_type=event_req.event_type,
            session_id=event_req.session_id,
            category=event_req.category,
            product_id=event_req.product_id,
            sku=event_req.sku,
            draft_id=event_req.draft_id,
            outcome=event_req.outcome,
            metadata=event_req.metadata,
            is_demo=event_req.is_demo,
            idempotency_key=event_req.idempotency_key,
            schema_version=event_req.schema_version or "1.0",
            source=x_source or "client",
        )
        return result
    except Exception as e:
        raise _map_analytics_error(e)


@router.post("/events/demo-seed", response_model=DemoSeedResponse)
def seed_demo_events(
    seed_req: DemoSeedRequest,
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_SEED)),
):
    """
    Generates repeatable demo seed events for testing & dashboard preview.
    """
    target_tenant = seed_req.tenant_id or authorized_tenant
    if target_tenant != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant demo seeding forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = AnalyticsService(db)
    try:
        return service.seed_demo_events(authorized_tenant)
    except Exception as e:
        raise _map_analytics_error(e)


@router.get("/summary", response_model=TelemetrySummaryResponse)
def get_telemetry_summary(
    tenant_id_query: Optional[str] = Query(None, alias="tenantId"),
    is_demo: Optional[bool] = Query(None, alias="isDemo"),
    days: int = Query(30, ge=1, le=365),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_READ)),
):
    """
    Aggregates consolidated event telemetry summary and conversion counters.
    """
    if tenant_id_query and tenant_id_query != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = AnalyticsService(db)
    try:
        summary_data = service.get_telemetry_summary(
            tenant_id=authorized_tenant,
            is_demo=is_demo,
            days=days,
        )
        return {
            "success": True,
            "summary": summary_data,
        }
    except Exception as e:
        raise _map_analytics_error(e)


@router.get("/funnel", response_model=FunnelResponse)
def get_funnel_metrics(
    tenant_id_query: Optional[str] = Query(None, alias="tenantId"),
    is_demo: Optional[bool] = Query(None, alias="isDemo"),
    days: int = Query(30, ge=1, le=365),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_READ)),
):
    """
    Calculates 5-stage customer conversion funnel metrics for the authorized tenant.
    """
    if tenant_id_query and tenant_id_query != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = AnalyticsService(db)
    try:
        funnel_data = service.get_funnel_metrics(
            tenant_id=authorized_tenant,
            is_demo=is_demo,
            days=days,
        )
        return {
            "success": True,
            "funnel": funnel_data,
        }
    except Exception as e:
        raise _map_analytics_error(e)


@router.get("/objections", response_model=ObjectionsResponse)
def get_objection_breakdown(
    tenant_id_query: Optional[str] = Query(None, alias="tenantId"),
    is_demo: Optional[bool] = Query(None, alias="isDemo"),
    days: int = Query(30, ge=1, le=365),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_READ)),
):
    """
    Retrieves categorized purchase objections and friction points.
    """
    if tenant_id_query and tenant_id_query != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = AnalyticsService(db)
    try:
        objections_data = service.get_objection_breakdown(
            tenant_id=authorized_tenant,
            is_demo=is_demo,
            days=days,
        )
        return {
            "success": True,
            "objections": objections_data,
        }
    except Exception as e:
        raise _map_analytics_error(e)


@router.get("/demand", response_model=DemandSignalsResponse)
def get_demand_signals(
    tenant_id_query: Optional[str] = Query(None, alias="tenantId"),
    is_demo: Optional[bool] = Query(None, alias="isDemo"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    authorized_tenant: str = Depends(get_authorized_tenant),
    db: Session = Depends(get_db),
    _perm=Depends(require_permission(Permissions.ANALYTICS_READ)),
):
    """
    Extracts top unfulfilled product search queries and out-of-stock demand signals.
    """
    if tenant_id_query and tenant_id_query != authorized_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access forbidden. Authorized for '{authorized_tenant}'.",
        )

    service = AnalyticsService(db)
    try:
        signals = service.get_unfulfilled_demand_signals(
            tenant_id=authorized_tenant,
            is_demo=is_demo,
            days=days,
            limit=limit,
        )
        return {
            "success": True,
            "demandSignals": signals,
        }
    except Exception as e:
        raise _map_analytics_error(e)
