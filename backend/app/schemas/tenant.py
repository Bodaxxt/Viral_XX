"""
Tenant schemas for multi-tenant workspace operations
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    id: str = Field(..., description="Unique tenant slug, e.g., 'al-noor-jewelry'")
    name: str = Field(..., description="Business display name")
    category: str = Field(..., description="Industry category: 'jewelry', 'restaurant', 'healthcare'")
    location: str = Field(..., description="Geographic location")
    currency: str = Field(..., description="Operating currency (e.g. QAR, EGP, USD)")
    whatsapp_number: str = Field(..., description="WhatsApp direct communication line")
    operating_hours: str = Field(..., description="Operating schedule")
    policy_summary: str = Field(..., description="High-level store policy summary")
    integration_mode: str = Field(default="demo", description="'demo' | 'live'")


class TenantResponse(TenantBase):
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TenantListResponse(BaseModel):
    count: int = Field(..., description="Total count of active businesses")
    tenants: List[TenantResponse] = Field(..., description="List of tenant workspaces")
