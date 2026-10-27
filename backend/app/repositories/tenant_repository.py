"""
Tenant Repository
Handles tenant workspace data access with parameterized queries.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models import Tenant
from backend.app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, db: Session):
        super().__init__(Tenant, db)

    def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return (
            self.db.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .first()
        )

    def get_all_active(self, category: Optional[str] = None) -> List[Tenant]:
        query = self.db.query(Tenant)
        if category:
            query = query.filter(Tenant.category == category)
        return query.order_by(Tenant.name.asc()).all()
