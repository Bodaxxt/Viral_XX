"""
Viral-X FastAPI Backend Application
Sprint 2.5 Migration Foundation
"""

from typing import Union
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.middleware import (
    SecurityAndTraversalMiddleware,
    RequestSizeLimitMiddleware,
    RequestTimeoutMiddleware,
)
from backend.app.api.v1.api import api_router
from backend.app.api.v1.endpoints.health import router as health_router


def create_application() -> FastAPI:
    """
    Application factory configuring routers, security middlewares, and error handlers.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Viral-X AI Sales Agent & Business Intelligence Platform - Python Backend",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    # 2. Custom Security & Guardrail Middlewares
    app.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.REQUEST_TIMEOUT_SECONDS,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.MAX_REQUEST_SIZE_BYTES,
    )
    app.add_middleware(SecurityAndTraversalMiddleware)

    # 3. Centralized Exception Handlers (Never leak secrets or DB internals)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "status_code": exc.status_code,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format validation errors cleanly without exposing internals
        formatted_errors = []
        for err in exc.errors():
            loc = " -> ".join([str(x) for x in err.get("loc", [])])
            formatted_errors.append({
                "field": loc,
                "message": err.get("msg"),
                "type": err.get("type"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload or query parameters.",
                    "details": formatted_errors,
                    "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        # Log internal database error safely with scrubbed details
        logger.error(f"Database error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "A database error occurred while processing the request.",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server exception on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                }
            },
        )

    # 4. Route Registrations
    # Mount top-level health probes for container runtimes
    app.include_router(health_router, prefix="")
    app.include_router(health_router, prefix="/api")

    # Mount API v1 router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
