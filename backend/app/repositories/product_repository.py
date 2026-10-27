"""
Product Repository
Enforces strict multi-tenant boundary checks and inventory joins.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.db.models import Product, Inventory
from backend.app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session):
        super().__init__(Product, db)

    def get_catalog_with_inventory(
        self,
        tenant_id: str,
        category: Optional[str] = None,
        max_budget: Optional[float] = None,
        query_text: Optional[str] = None,
        in_stock_only: bool = False,
    ) -> List[Tuple[Product, Optional[Inventory]]]:
        """
        Retrieves products strictly partitioned by tenant_id, joined with live inventory.
        Tenant boundary is enforced via explicit WHERE product.tenant_id = :tenant_id.
        """
        # Outer join product with inventory ensuring tenant-matching
        query = (
            self.db.query(Product, Inventory)
            .outerjoin(
                Inventory,
                (Inventory.product_id == Product.id) & (Inventory.tenant_id == tenant_id),
            )
            .filter(Product.tenant_id == tenant_id)
            .filter(Product.is_active == 1)
        )

        if category:
            query = query.filter(Product.category.ilike(f"%{category.strip()}%"))

        if max_budget is not None and max_budget > 0:
            query = query.filter(Product.base_price <= max_budget)

        if query_text:
            cleaned = query_text.strip()
            pattern = f"%{cleaned}%"
            query = query.filter(
                or_(
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.category.ilike(pattern),
                )
            )

        if in_stock_only:
            query = query.filter(
                Inventory.stock_count > Inventory.reserved_count
            )

        return query.order_by(Product.base_price.asc()).all()

    def get_product_by_id(
        self, tenant_id: str, product_id: str
    ) -> Optional[Tuple[Product, Optional[Inventory]]]:
        """
        Retrieve single product ensuring strict tenant isolation.
        """
        return (
            self.db.query(Product, Inventory)
            .outerjoin(
                Inventory,
                (Inventory.product_id == Product.id) & (Inventory.tenant_id == tenant_id),
            )
            .filter(Product.tenant_id == tenant_id)
            .filter(Product.id == product_id)
            .first()
        )
