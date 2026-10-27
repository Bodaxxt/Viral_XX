"""
Tenants API Endpoints
Provides workspace metadata for active demo and live businesses.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.catalog_service import CatalogService
from backend.app.schemas.tenant import TenantResponse, TenantListResponse

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get(
    "",
    response_model=TenantListResponse,
    summary="List active tenant businesses",
    description="Returns metadata for all configured demo and live businesses.",
)
def list_tenants(
    category: Optional[str] = Query(None, description="Filter by business category: jewelry, restaurant, healthcare"),
    db: Session = Depends(get_db),
) -> TenantListResponse:
    service = CatalogService(db)
    return service.list_tenants(category=category)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant details",
    description="Returns metadata for a specific tenant workspace.",
)
def get_tenant(
    tenant_id: str = Path(..., description="Unique tenant identifier (e.g. 'al-noor-jewelry')"),
    db: Session = Depends(get_db),
) -> TenantResponse:
    service = CatalogService(db)
    return service.get_tenant(tenant_id=tenant_id)
