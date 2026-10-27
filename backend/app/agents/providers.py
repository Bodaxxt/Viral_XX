"""
AI Provider Adapters — direct HTTP implementations mirroring the Node.js agents.
Each adapter converts the common message list and tool definitions to provider format,
executes the multi-round tool loop, and returns a normalized AgentTurnResult.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import logger


class ProviderError(Exception):
    """Raised on non-retryable provider failures."""


class ProviderTimeoutError(ProviderError):
    """Raised when the LLM provider exceeds the configured request timeout."""


MAX_TOOL_ROUNDS = 6


def _safe_json_args(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def call(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        current_message: str,
        tool_definitions: List[Dict[str, Any]],
        tool_executor,
        tenant_id: str,
        session_id: str,
    ) -> Tuple[str, List[Dict[str, Any]], str]:
        """
        Returns (reply_text, tool_calls_executed, grounding_note)
        """
        ...


# ────────────────────────────────────────────────────────────────
#  GOOGLE GEMINI
# ────────────────────────────────────────────────────────────────

def _to_gemini_functions(tool_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"name": t["name"], "description": t["description"],
             "parameters": t.get("parameters", {"type": "object", "properties": {}})}
            for t in tool_defs]


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.timeout = settings.AI_REQUEST_TIMEOUT_SECONDS

    async def call(self, system_prompt, history, current_message, tool_definitions,
                   tool_executor, tenant_id, session_id):
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured.")

        candidate_models = [m for m in [self.model, "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"] if m]
        seen_models = []
        unique_models = []
        for m in candidate_models:
            if m not in seen_models:
                seen_models.append(m)
                unique_models.append(m)

        contents = [
            {"role": "user" if m["sender"] == "user" else "model", "parts": [{"text": m["content"]}]}
            for m in history if m.get("sender") in ("user", "ai")
        ]
        contents.append({"role": "user", "parts": [{"text": current_message}]})

        tools_payload = [{"functionDeclarations": _to_gemini_functions(tool_definitions)}]
        tool_calls_executed: List[Dict[str, Any]] = []
        selected_model = unique_models[0]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _ in range(MAX_TOOL_ROUNDS):
                resp = None
                last_err = ""
                for m in unique_models:
                    selected_model = m
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                    try:
                        r = await client.post(url, json={
                            "systemInstruction": {"parts": [{"text": system_prompt}]},
                            "contents": contents,
                            "tools": tools_payload,
                            "generationConfig": {
                                "temperature": 0.15,
                                "maxOutputTokens": 1200,
                                "candidateCount": 1,
                            },
                        })
                        if r.status_code == 200:
                            resp = r
                            break
                        else:
                            last_err = f"HTTP {r.status_code}: {r.text[:80]}"
                            logger.warning("Gemini model %s returned status %d, trying fallback...", m, r.status_code)
                    except httpx.TimeoutException:
                        last_err = "Timeout"
                    except Exception as e:
                        last_err = str(e)

                if resp is None:
                    raise ProviderError(f"Gemini API error. All candidate models failed: {last_err}")

                data = resp.json()
                candidate = (data.get("candidates") or [{}])[0]
                parts = candidate.get("content", {}).get("parts", [])
                function_calls = [p for p in parts if "functionCall" in p]
                text_parts = [p for p in parts if "text" in p]

                if not function_calls:
                    reply_text = "".join(p["text"] for p in text_parts)
                    return (
                        reply_text,
                        tool_calls_executed,
                        f"Grounded: Google Gemini ({selected_model}) — {len(tool_calls_executed)} tools invoked",
                    )

                tool_result_parts = []
                for fc in function_calls:
                    name = fc["functionCall"]["name"]
                    args = fc["functionCall"].get("args", {})
                    result = tool_executor.execute(name, args)
                    tool_calls_executed.append({"tool": name, "args": args, "result": result})
                    tool_result_parts.append({
                        "functionResponse": {"name": name, "response": {"content": json.dumps(result)}}
                    })

                contents.append({"role": "model", "parts": parts})
                contents.append({"role": "user", "parts": tool_result_parts})

        raise ProviderError("Gemini exceeded maximum tool execution rounds.")


# ────────────────────────────────────────────────────────────────
#  ANTHROPIC CLAUDE
# ────────────────────────────────────────────────────────────────

def _to_anthropic_tools(tool_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"name": t["name"], "description": t["description"],
             "input_schema": t.get("parameters", {"type": "object", "properties": {}})}
            for t in tool_defs]


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL
        self.timeout = settings.AI_REQUEST_TIMEOUT_SECONDS

    async def call(self, system_prompt, history, current_message, tool_definitions,
                   tool_executor, tenant_id, session_id):
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured.")

        url = "https://api.anthropic.com/v1/messages"
        messages = [
            {"role": "user" if m["sender"] == "user" else "assistant", "content": m["content"]}
            for m in history if m.get("sender") in ("user", "ai")
        ]
        messages.append({"role": "user", "content": current_message})

        tools_payload = _to_anthropic_tools(tool_definitions)
        tool_calls_executed: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _ in range(MAX_TOOL_ROUNDS):
                try:
                    resp = await client.post(url, json={
                        "model": self.model,
                        "system": system_prompt,
                        "messages": messages,
                        "tools": tools_payload,
                        "max_tokens": 1500,
                        "temperature": 0.15,
                    }, headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    })
                except httpx.TimeoutException:
                    raise ProviderTimeoutError(f"Anthropic request timed out after {self.timeout}s.")

                if resp.status_code != 200:
                    raise ProviderError(f"Anthropic API error {resp.status_code}. Service temporarily unavailable.")

                data = resp.json()
                stop_reason = data.get("stop_reason")
                content_blocks = data.get("content", [])

                if stop_reason != "tool_use":
                    reply_text = "".join(b["text"] for b in content_blocks if b.get("type") == "text")
                    return (
                        reply_text,
                        tool_calls_executed,
                        f"Grounded: Anthropic Claude ({self.model}) — {len(tool_calls_executed)} tools invoked",
                    )

                messages.append({"role": "assistant", "content": content_blocks})
                tool_results = []
                for block in content_blocks:
                    if block.get("type") == "tool_use":
                        name, tool_input, use_id = block["name"], block.get("input", {}), block["id"]
                        result = tool_executor.execute(name, tool_input)
                        tool_calls_executed.append({"tool": name, "args": tool_input, "result": result})
                        tool_results.append({"type": "tool_result", "tool_use_id": use_id, "content": json.dumps(result)})

                messages.append({"role": "user", "content": tool_results})

        raise ProviderError("Anthropic exceeded maximum tool execution rounds.")


# ────────────────────────────────────────────────────────────────
#  OPENAI GPT
# ────────────────────────────────────────────────────────────────

def _to_openai_tools(tool_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": t.get("parameters", {"type": "object", "properties": {}}),
    }} for t in tool_defs]


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.timeout = settings.AI_REQUEST_TIMEOUT_SECONDS

    async def call(self, system_prompt, history, current_message, tool_definitions,
                   tool_executor, tenant_id, session_id):
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured.")

        url = "https://api.openai.com/v1/chat/completions"
        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": "user" if m["sender"] == "user" else "assistant", "content": m["content"]}
              for m in history if m.get("sender") in ("user", "ai")],
            {"role": "user", "content": current_message},
        ]
        tools_payload = _to_openai_tools(tool_definitions)
        tool_calls_executed: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _ in range(MAX_TOOL_ROUNDS):
                try:
                    resp = await client.post(url, json={
                        "model": self.model,
                        "messages": messages,
                        "tools": tools_payload,
                        "tool_choice": "auto",
                        "temperature": 0.15,
                        "max_tokens": 1500,
                    }, headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    })
                except httpx.TimeoutException:
                    raise ProviderTimeoutError(f"OpenAI request timed out after {self.timeout}s.")

                if resp.status_code != 200:
                    raise ProviderError(f"OpenAI API error {resp.status_code}. Service temporarily unavailable.")

                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                assistant_msg = choice.get("message", {})
                messages.append(assistant_msg)

                if choice.get("finish_reason") != "tool_calls" or not assistant_msg.get("tool_calls"):
                    reply_text = assistant_msg.get("content") or ""
                    return (
                        reply_text,
                        tool_calls_executed,
                        f"Grounded: OpenAI ({self.model}) — {len(tool_calls_executed)} tools invoked",
                    )

                tool_result_msgs = []
                for tc in assistant_msg["tool_calls"]:
                    name = tc["function"]["name"]
                    args = _safe_json_args(tc["function"].get("arguments", "{}"))
                    result = tool_executor.execute(name, args)
                    tool_calls_executed.append({"tool": name, "args": args, "result": result})
                    tool_result_msgs.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })
                messages.extend(tool_result_msgs)

        raise ProviderError("OpenAI exceeded maximum tool execution rounds.")
