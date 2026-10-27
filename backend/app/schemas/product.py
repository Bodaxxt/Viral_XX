"""
Product and catalog schemas
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryInfo(BaseModel):
    stock_count: int = Field(default=0, description="Available stock quantity")
    reserved_count: int = Field(default=0, description="Units held in unconfirmed drafts")
    available_count: int = Field(default=0, description="Real-time purchasable stock (stock - reserved)")
    location: str = Field(..., description="Warehouse or showroom location")
    in_stock: bool = Field(default=False, description="True if available_count > 0")

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: str = Field(..., description="Unique product ID (e.g., J-101)")
    tenant_id: str = Field(..., description="Owner tenant ID")
    sku: str = Field(..., description="Stock keeping unit")
    name: str = Field(..., description="Product name in English")
    name_ar: Optional[str] = Field(default=None, description="Product name in Arabic")
    category: str = Field(..., description="Product category")
    base_price: float = Field(..., description="Base price in tenant currency")
    currency: str = Field(..., description="ISO currency code")
    description: str = Field(..., description="Product description in English")
    description_ar: Optional[str] = Field(default=None, description="Product description in Arabic")
    attributes: Optional[Dict[str, Any]] = Field(default=None, description="Parsed attributes object")
    attributes_json: Optional[str] = Field(default=None, description="Raw JSON attributes")
    is_active: int = Field(default=1, description="1 if active, 0 if discontinued")
    created_at: Optional[datetime] = None
    inventory: Optional[InventoryInfo] = Field(default=None, description="Current inventory state")

    model_config = ConfigDict(from_attributes=True)


class CatalogResponse(BaseModel):
    tenant_id: str = Field(..., description="Tenant workspace ID")
    tenant_name: str = Field(..., description="Tenant workspace name")
    currency: str = Field(..., description="Tenant currency")
    count: int = Field(..., description="Total products returned")
    products: List[ProductResponse] = Field(..., description="List of catalog products")
