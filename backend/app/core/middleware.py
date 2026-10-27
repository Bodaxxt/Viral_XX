"""
Viral-X Core Middleware
Sprint 2.5 Security, Request Size Limit, and Traversal Defenses
"""

import asyncio
import urllib.parse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from backend.app.core.config import settings
from backend.app.core.logging import logger


class SecurityAndTraversalMiddleware(BaseHTTPMiddleware):
    """
    Guards the Python backend against path traversal, alternate separators,
    encoded null bytes, and sensitive file probing.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.blocked_patterns = [
            "/.env", "/.git", "/viral_x.db", "/test_viral_x.db",
            "/package.json", "/package-lock.json", "/schema.sql",
            "/server", "/backend", "/node_modules"
        ]

    async def dispatch(self, request: Request, call_next):
        raw_path = request.url.path
        raw_query = request.url.query
        full_raw = f"{raw_path}?{raw_query}" if raw_query else raw_path

        # Safely decode path
        try:
            decoded_path = urllib.parse.unquote(raw_path)
            decoded_full = urllib.parse.unquote(full_raw)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "BadRequest", "message": "Malformed URL encoding."}
            )

        lower_raw = full_raw.lower()
        lower_decoded = decoded_full.lower()

        # 1. Block Directory Traversal Attempts
        if (
            ".." in decoded_path
            or ".." in lower_raw
            or ".." in lower_decoded
            or "%2e%2e" in lower_raw
            or "%252e" in lower_raw
            or "\\" in lower_raw
            or "\\" in lower_decoded
            or "%5c" in lower_raw
            or "\0" in decoded_path
            or "%00" in lower_raw
        ):
            logger.warning("Blocked path traversal attempt: %s from %s", raw_path, request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Path traversal attempt detected and blocked.",
                        "status_code": 403,
                    },
                    "message": "Path traversal attempt detected and blocked.",
                    "detail": "Path traversal attempt detected and blocked.",
                }
            )

        # 2. Block direct requests for sensitive files
        for pattern in self.blocked_patterns:
            if lower_decoded == pattern or lower_decoded.startswith(f"{pattern}/") or lower_decoded.endswith(pattern):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Access to sensitive file denied. The requested resource was not found.",
                            "status_code": 404,
                        },
                        "message": "Access to sensitive file denied.",
                        "detail": "Access to sensitive file denied.",
                    }
                )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum request body size limit to protect against denial of service.
    """
    def __init__(self, app: ASGIApp, max_bytes: int = settings.MAX_REQUEST_SIZE_BYTES):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds maximum allowed limit of {self.max_bytes} bytes.",
                                "status_code": 413,
                            },
                            "message": f"Request body exceeds maximum allowed limit of {self.max_bytes} bytes.",
                            "detail": f"Request body exceeds maximum allowed limit of {self.max_bytes} bytes.",
                        }
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "BAD_REQUEST",
                            "message": "Invalid Content-Length header.",
                            "status_code": 400,
                        },
                        "message": "Invalid Content-Length header.",
                        "detail": "Invalid Content-Length header.",
                    }
                )

        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Enforces a timeout for incoming requests.
    """
    def __init__(self, app: ASGIApp, timeout_seconds: float = settings.REQUEST_TIMEOUT_SECONDS):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.error("Request to %s timed out after %s seconds", request.url.path, self.timeout_seconds)
            return JSONResponse(
                status_code=504,
                content={"error": "GatewayTimeout", "message": "Request processing timed out."}
            )
