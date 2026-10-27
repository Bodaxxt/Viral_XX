"""
Product Catalog Endpoints
Migration Proof-of-Concept vertical slice: read-only, typed catalog retrieval with strict tenant boundaries.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.catalog_service import CatalogService
from backend.app.schemas.product import CatalogResponse

router = APIRouter(prefix="/tenants", tags=["Products & Catalog"])


@router.get(
    "/{tenant_id}/catalog",
    response_model=CatalogResponse,
    summary="Get tenant product catalog (Proof of Concept)",
    description=(
        "Retrieves active products and live inventory state strictly partitioned by tenant ID. "
        "Enforces database-level isolation so no other tenant's data can leak."
    ),
)
def get_tenant_catalog(
    tenant_id: str = Path(..., description="Target tenant ID (e.g. 'al-noor-jewelry')"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    max_budget: Optional[float] = Query(None, ge=0, description="Optional maximum price filter"),
    q: Optional[str] = Query(None, max_length=100, description="Optional search term (name, sku, description)"),
    in_stock_only: bool = Query(False, description="Filter only items with real-time available stock > 0"),
    db: Session = Depends(get_db),
) -> CatalogResponse:
    service = CatalogService(db)
    return service.get_tenant_catalog(
        tenant_id=tenant_id,
        category=category,
        max_budget=max_budget,
        query=q,
        in_stock_only=in_stock_only,
    )
