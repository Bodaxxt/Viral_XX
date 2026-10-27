"""
Agent Pydantic Schemas
Defines structured input/output envelopes, message types, and tool call records.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolCallRecord(BaseModel):
    tool: str = Field(..., description="Name of the invoked tool")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments supplied to the tool")
    result: Any = Field(default=None, description="Output returned by the tool execution")


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' | 'assistant' | 'model' | 'system' | 'tool'")
    content: str = Field(default="", description="Text message content")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="Provider tool calls")
    tool_call_id: Optional[str] = Field(default=None, description="OpenAI/Anthropic tool call ID")


class AgentTurnResult(BaseModel):
    reply: str = Field(..., description="Conversational text output for the customer")
    grounding: str = Field(..., description="Verification and provenance metadata")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="Executed tool records")
    has_draft_order: Optional[Dict[str, Any]] = Field(default=None, description="Associated draft order details if any")
    is_handoff: bool = Field(default=False, description="True if specialist human handoff was requested")
    whatsapp_url: Optional[str] = Field(default=None, description="Direct WhatsApp handoff link if applicable")


class AgentRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId", max_length=100, description="Target business workspace ID")
    session_id: str = Field(default="default-session", alias="sessionId", max_length=150, description="Chat session ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Customer message text")
    customer_name: Optional[str] = Field(default=None, alias="customerName", max_length=100, description="Customer name if known")

    model_config = ConfigDict(populate_by_name=True)


# Backwards compatibility alias
AgentMessageRequest = AgentRequest


class AgentResponse(BaseModel):
    reply: str = Field(..., description="Agent message response")
    grounding: str = Field(default="", description="Grounding and provider metadata")
    provider: str = Field(default="local", description="AI provider used ('gemini' | 'anthropic' | 'openai' | 'local')")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="List of tools invoked during turn")
    blocked: bool = Field(default=False, description="Whether guardrails blocked the request")
    block_reason: Optional[str] = Field(default=None, description="Reason code if blocked")
    error: Optional[str] = Field(default=None, description="Error message if any")
    is_handoff: bool = Field(default=False, description="Whether handoff was triggered")
    has_draft_order: Optional[Dict[str, Any]] = Field(default=None, description="Draft order info if present")
    whatsapp_url: Optional[str] = Field(default=None, description="Direct WhatsApp handoff link if applicable")


# Backwards compatibility alias
AgentTestResponse = AgentResponse
