"""
API v1 Router aggregator
"""

from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    health,
    auth,
    tenants,
    products,
    agent,
    drafts,
    bookings,
    handoff,
    analytics,
)

api_router = APIRouter()

# Sprint 5: Authentication & Authorization
api_router.include_router(auth.router)

# Mount health routes at both / and /health
api_router.include_router(health.router)
api_router.include_router(tenants.router)
api_router.include_router(products.router)
# Sprint 3: Python AI agent (test-only; production remains Node.js /api/chat)
api_router.include_router(agent.router)
# Sprint 3.5: Draft orders lifecycle and explicit confirmation gates
api_router.include_router(drafts.router)
api_router.include_router(bookings.router)
# Sprint 3.6: Human handoff and WhatsApp escalation (isolated; production remains Node.js)
api_router.include_router(handoff.router)
# Sprint 4: Business Intelligence & Telemetry Analytics (isolated; production remains Node.js)
api_router.include_router(analytics.router)

