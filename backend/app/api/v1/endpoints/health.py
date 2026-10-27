"""
Health and Readiness Probes
Provides standardized liveness and readiness status for container orchestrators and monitoring.
"""

from fastapi import APIRouter, status, Response
from backend.app.core.config import settings
from backend.app.db.session import check_db_health
from backend.app.schemas.health import HealthResponse, ReadinessResponse, DependencyStatus

router = APIRouter(tags=["Health & Monitoring"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 OK if the FastAPI process is responsive.",
)
def get_liveness() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Verifies database connectivity before accepting live traffic.",
    responses={
        200: {"description": "Service is fully operational"},
        503: {"description": "Database or critical dependency is unavailable"},
    },
)
def get_readiness(response: Response) -> ReadinessResponse:
    db_result = check_db_health()
    is_ready = db_result["connected"]

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    dep_status = DependencyStatus(
        name="sqlite_database",
        status=db_result["status"],
        connected=db_result["connected"],
        latency_ms=db_result["latency_ms"],
        error=db_result["error"],
    )

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        ready=is_ready,
        dependencies={
            "database": dep_status,
        },
    )
