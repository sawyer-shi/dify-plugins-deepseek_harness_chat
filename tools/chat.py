from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dsh_client import DshGatewayClient, DshGatewayError
from tools.session_manager import (
    SessionManager,
    chat_with_session_retry,
    resolve_scope_key,
)

SESSION_MANAGER = SessionManager()

_DEFAULT_TIMEOUT_SECONDS = 300.0
_VALID_SCOPES = {"session", "user", "none"}


def normalize_params(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    prompt = str(tool_parameters.get("prompt") or "").strip()
    model = str(tool_parameters.get("model") or "").strip() or "default"
    scope = str(tool_parameters.get("session_scope") or "").strip() or "session"
    if scope not in _VALID_SCOPES:
        scope = "session"
    raw_timeout = tool_parameters.get("timeout_seconds")
    try:
        timeout_seconds = (
            float(raw_timeout) if raw_timeout not in (None, "") else _DEFAULT_TIMEOUT_SECONDS
        )
    except (TypeError, ValueError):
        timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
    timeout_seconds = max(timeout_seconds, 1.0)
    include_reasoning = bool(tool_parameters.get("include_reasoning"))
    return {
        "prompt": prompt,
        "model": model,
        "session_scope": scope,
        "timeout_seconds": timeout_seconds,
        "include_reasoning": include_reasoning,
    }


class DeepSeekHarnessChatTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        params = normalize_params(tool_parameters)
        prompt = params["prompt"]
        if not prompt:
            raise Exception("Parameter 'prompt' is required.")

        key = resolve_scope_key(
            params["session_scope"], self.runtime.session_id, self.runtime.user_id
        )
        client = DshGatewayClient(
            base_url=str(self.runtime.credentials.get("base_url") or ""),
            api_key=str(self.runtime.credentials.get("api_key") or ""),
            timeout_seconds=params["timeout_seconds"],
        )
        try:
            result, _retried = chat_with_session_retry(
                client, SESSION_MANAGER, key, prompt, params["model"]
            )
        except DshGatewayError as e:
            raise Exception(e.message) from e

        reply = result.content
        if params["include_reasoning"] and result.reasoning:
            reply = f"<think>\n{result.reasoning}\n</think>\n\n{reply}"

        yield self.create_text_message(reply)
        yield self.create_json_message(
            {
                "session_id": result.session_id,
                "scope": params["session_scope"],
                "reply": result.content,
                "tool_calls": len(result.tool_call_names),
                "tool_call_names": sorted(set(result.tool_call_names)),
                "model": result.model or params["model"],
            }
        )
