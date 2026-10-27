"""
Pydantic v2 Schemas for Human Handoff & WhatsApp Escalation
Sprint 3.6 - Migration to Python
"""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class HandoffCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: Optional[str] = Field(None, alias="tenantId", description="Tenant identifier (must match authorized header if provided)")
    session_id: Optional[str] = Field(None, alias="sessionId", description="Session identifier")
    reason: str = Field(
        default="Customer requested live specialist communication",
        min_length=1,
        max_length=500,
        description="Reason for human escalation"
    )
    notes: Optional[str] = Field(None, max_length=1000, description="Optional customer or agent notes")
    draft_id: Optional[str] = Field(None, alias="draftId", description="Optional associated draft order ID")
    escalation_trigger: Optional[str] = Field(
        default="customer_request",
        description="Trigger category: explicit_request, complaint, uncertainty, workflow_approval, provider_failure"
    )
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey", max_length=128, description="Optional key to prevent duplicate handoffs")


class HandoffCloseRequest(BaseModel):
    resolution_notes: Optional[str] = Field(None, max_length=1000, description="Notes on resolution of the handoff")


class HandoffSummary(BaseModel):
    business: str
    reason: str
    draft_id: Optional[str] = None
    notes: Optional[str] = None


class HandoffResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: str = Field(..., alias="tenantId")
    session_id: Optional[str] = Field(None, alias="sessionId")
    status: str = Field(default="link_prepared", description="Handoff lifecycle status: requested, link_prepared, waiting_for_customer, closed")
    success: bool = True
    handoff_prepared: bool = True
    whatsapp_number: str
    whatsapp_url: str
    summary: HandoffSummary
    user_message: str
    escalation_trigger: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    already_created: bool = False
    disclaimer: str = (
        "URL prepared for client-side click-to-chat. No backend delivery was performed. "
        "Preparing this link does not send an automated message or guarantee delivery until opened by the customer."
    )
    handoffUrl: Optional[str] = Field(None, description="Node.js compatibility alias for whatsapp_url")
    tenantName: Optional[str] = Field(None, description="Node.js compatibility alias for tenant name")
    escalationReason: Optional[str] = Field(None, description="Node.js compatibility alias for reason")
    draftId: Optional[str] = Field(None, description="Node.js compatibility alias for draft_id")
