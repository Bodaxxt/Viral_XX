"""
Health and readiness schemas
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    name: str = Field(..., description="Dependency identifier, e.g., 'sqlite_database'")
    status: str = Field(..., description="'healthy' | 'unhealthy'")
    connected: bool = Field(..., description="True if dependency responded successfully")
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="'ok' | 'degraded'")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Semantic version")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    environment: str = Field(..., description="Runtime environment")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="'ready' | 'not_ready'")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Semantic version")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ready: bool = Field(..., description="True if all critical dependencies are ready")
    dependencies: Dict[str, DependencyStatus] = Field(..., description="Status breakdown of dependencies")
