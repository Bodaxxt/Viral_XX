"""
Catalog Service
Domain logic for catalog inspection, tenant isolation, and inventory mapping.
"""

import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.repositories.tenant_repository import TenantRepository
from backend.app.repositories.product_repository import ProductRepository
from backend.app.schemas.product import ProductResponse, InventoryInfo, CatalogResponse
from backend.app.schemas.tenant import TenantResponse, TenantListResponse
from backend.app.core.logging import logger


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.tenant_repo = TenantRepository(db)
        self.product_repo = ProductRepository(db)

    def list_tenants(self, category: Optional[str] = None) -> TenantListResponse:
        """
        Lists all active demo/live tenant workspaces.
        """
        tenants = self.tenant_repo.get_all_active(category=category)
        tenant_responses = [TenantResponse.model_validate(t) for t in tenants]
        return TenantListResponse(
            count=len(tenant_responses),
            tenants=tenant_responses,
        )

    def get_tenant(self, tenant_id: str) -> TenantResponse:
        """
        Retrieves a single tenant by ID, or raises 404 if not found.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found.",
            )
        return TenantResponse.model_validate(tenant)

    def get_tenant_catalog(
        self,
        tenant_id: str,
        category: Optional[str] = None,
        max_budget: Optional[float] = None,
        query: Optional[str] = None,
        in_stock_only: bool = False,
    ) -> CatalogResponse:
        """
        Retrieves products for a verified tenant workspace with inventory grounding.
        Guarantees cross-tenant boundary isolation.
        """
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found.",
            )

        items = self.product_repo.get_catalog_with_inventory(
            tenant_id=tenant_id,
            category=category,
            max_budget=max_budget,
            query_text=query,
            in_stock_only=in_stock_only,
        )

        product_responses: List[ProductResponse] = []
        for product, inv in items:
            inventory_info = None
            if inv:
                available = max(0, inv.stock_count - inv.reserved_count)
                inventory_info = InventoryInfo(
                    stock_count=inv.stock_count,
                    reserved_count=inv.reserved_count,
                    available_count=available,
                    location=inv.location,
                    in_stock=(available > 0),
                )

            # Safely parse JSON attributes if present
            attributes_dict: Optional[Dict[str, Any]] = None
            if product.attributes_json:
                try:
                    attributes_dict = json.loads(product.attributes_json)
                except Exception as e:
                    logger.debug(f"Failed to parse attributes_json for product {product.id}: {e}")
                    attributes_dict = None

            product_responses.append(
                ProductResponse(
                    id=product.id,
                    tenant_id=product.tenant_id,
                    sku=product.sku,
                    name=product.name,
                    name_ar=product.name_ar,
                    category=product.category,
                    base_price=product.base_price,
                    currency=product.currency,
                    description=product.description,
                    description_ar=product.description_ar,
                    attributes=attributes_dict,
                    attributes_json=product.attributes_json,
                    is_active=product.is_active,
                    created_at=product.created_at,
                    inventory=inventory_info,
                )
            )

        return CatalogResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            currency=tenant.currency,
            count=len(product_responses),
            products=product_responses,
        )
