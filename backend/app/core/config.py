"""
Viral-X Core Configuration Module
Safe environment variable loading with Pydantic BaseSettings.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project directory paths
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Application settings
    APP_NAME: str = "Viral-X AI Sales Agent & BI Platform"
    APP_VERSION: str = "2.5.0-alpha"
    ENVIRONMENT: str = Field(default="development", description="development | testing | production")
    DEBUG: bool = Field(default=False)
    APP_HOST: str = Field(default="127.0.0.1")
    APP_PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # Database settings
    # Compatible with existing SQLite database by default
    DATABASE_URL: Optional[str] = None

    # Fallback to Node.js style DATABASE_PATH if set
    DATABASE_PATH: Optional[str] = None

    # Security & limits
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000")
    MAX_REQUEST_SIZE_BYTES: int = Field(default=1_048_576, description="1 MB maximum request body size")
    REQUEST_TIMEOUT_SECONDS: float = Field(default=30.0, description="30 seconds request processing timeout")

    # Server-side AI secrets & model configurations (Never exposed to client)
    GEMINI_API_KEY: Optional[str] = Field(default=None, repr=False)
    GEMINI_MODEL: str = Field(default="gemini-flash-lite-latest")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, repr=False)
    ANTHROPIC_MODEL: str = Field(default="claude-sonnet-4-5")
    OPENAI_API_KEY: Optional[str] = Field(default=None, repr=False)
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    AI_REQUEST_TIMEOUT_SECONDS: float = Field(default=25.0, description="Timeout for external LLM API calls")

    # Sprint 5: Authentication & Authorization Configuration
    JWT_SECRET_KEY: str = Field(
        default="dev-insecure-jwt-secret-key-change-in-production-viral-x-2026",
        repr=False,
        description="Cryptographic secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token TTL in minutes")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token TTL in days")
    JWT_ISSUER: str = Field(default="viral-x-auth")
    JWT_AUDIENCE: str = Field(default="viral-x-api")
    ALLOW_DEV_HEADER_AUTH: bool = Field(
        default=True,
        description="Permits dev/test X-Tenant-ID fallback. Automatically disabled in production.",
    )

    @field_validator("ALLOW_DEV_HEADER_AUTH", mode="after")
    @classmethod
    def enforce_production_no_dev_headers(cls, v: bool, info) -> bool:
        # In production, never allow permissive header-only authentication
        env = os.environ.get("ENVIRONMENT", "").lower()
        if env == "production":
            return False
        return v

    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def is_dev_header_auth_allowed(self) -> bool:
        return (not self.is_production()) and self.ALLOW_DEV_HEADER_AUTH

    def validate_production_configuration(self) -> None:
        """
        Fails closed if critical security configuration is missing or insecure in production.
        """
        if self.is_production():
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "dev-insecure-jwt-secret-key-change-in-production-viral-x-2026":
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: Production environment detected "
                    "with insecure default or missing JWT_SECRET_KEY. Failing closed."
                )
            if self.ALLOW_DEV_HEADER_AUTH:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: ALLOW_DEV_HEADER_AUTH must be False in production."
                )

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def effective_database_url(self) -> str:
        """
        Resolves effective database URL with fallback to existing viral_x.db.
        """
        if self.DATABASE_URL:
            # Handle relative SQLite paths properly
            if self.DATABASE_URL.startswith("sqlite:///./") or self.DATABASE_URL.startswith("sqlite:///../"):
                rel_path = self.DATABASE_URL.replace("sqlite:///", "")
                abs_path = (BACKEND_DIR / rel_path).resolve()
                return f"sqlite:///{abs_path}"
            return self.DATABASE_URL

        if self.DATABASE_PATH:
            db_file = Path(self.DATABASE_PATH)
            if not db_file.is_absolute():
                db_file = (ROOT_DIR / db_file).resolve()
            return f"sqlite:///{db_file}"

        # Default fallback to existing root viral_x.db
        default_db = (ROOT_DIR / "viral_x.db").resolve()
        return f"sqlite:///{default_db}"

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_url.startswith("sqlite")


# Global settings singleton
settings = Settings()
settings.validate_production_configuration()
