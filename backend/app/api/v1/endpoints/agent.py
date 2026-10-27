"""
POST /api/v1/agent/test — Sprint 3 test-only endpoint for the Python AI agent.

This endpoint is SEPARATE from the production Node.js /api/chat endpoint.
It is used exclusively for testing the Python migration and MUST NOT serve
production traffic until the agent has been validated and explicitly approved.
"""

from typing import Optional
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.agents.agent import AgentOrchestrator, TenantNotFoundError
from backend.app.agents.guardrails import Guardrails
from backend.app.agents.provider_factory import detect_provider_name
from backend.app.agents.schemas import AgentRequest, AgentResponse
from backend.app.core.auth import get_current_principal
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas.auth import Permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# One shared guardrails instance (stateless, safe to reuse)
_guardrails = Guardrails()


@router.post(
    "/test",
    response_model=AgentResponse,
    summary="[Test-Only] Python AI Agent",
    description=(
        "Sprint 3 test endpoint for validating the Python AI agent migration. "
        "Not for production traffic — the production endpoint remains Node.js /api/chat."
    ),
    status_code=status.HTTP_200_OK,
)
async def test_agent(
    request: AgentRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Run a single conversation turn through the Python AI agent."""
    if settings.is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development agent test harness is strictly disabled in production environments.",
        )

    # When Authorization header is provided, strictly enforce principal, permissions, and tenant isolation
    if authorization and authorization.strip():
        principal = get_current_principal(authorization=authorization, x_tenant_id=x_tenant_id, db=db)
        if not principal.has_permission(Permissions.AGENT_TEST):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires '{Permissions.AGENT_TEST}' permission.",
            )
        if principal.tenant_id and principal.tenant_id != request.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant authorization mismatch: request tenant '{request.tenant_id}' does not match principal tenant '{principal.tenant_id}'.",
            )
    elif x_tenant_id and x_tenant_id.strip():
        if x_tenant_id.strip() != request.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant authorization mismatch: request tenant '{request.tenant_id}' does not match header '{x_tenant_id}'.",
            )

    logger.info(
        "Python agent test request: tenant=%s session=%s message_length=%d",
        request.tenant_id,
        request.session_id,
        len(request.message),
    )

    orchestrator = AgentOrchestrator(db=db)
    try:
        response = await orchestrator.handle(request)
    except TenantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unhandled agent error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent encountered an unexpected error. Please try again.",
        )

    return response


@router.get(
    "/info",
    summary="Python Agent Configuration Info",
    description="Returns the active AI provider and agent configuration for diagnostics.",
)
def agent_info() -> dict:
    """Returns provider detection information for diagnostics."""
    return {
        "python_agent_status": "sprint3_test_only",
        "active_provider": detect_provider_name(),
        "note": "Production chat continues to use the Node.js /api/chat endpoint.",
    }
