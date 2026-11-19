from __future__ import annotations

import threading

from tools.dsh_client import (
    DEFAULT_MAX_TOKENS,
    ChatResult,
    DshGatewayClient,
    DshGatewayError,
)

SESSION_HEADER_NEW = "new"
_VALID_SCOPES = {"session", "user", "none"}


def resolve_scope_key(
    scope: str, dify_session_id: str | None, dify_user_id: str | None
) -> str | None:
    """Map (scope, Dify runtime ids) to a sticky-session mapping key.

    Returns None for stateless behavior (scope "none", unknown scope, or no
    usable runtime id after fallbacks).
    """
    if scope not in _VALID_SCOPES:
        return None
    if scope == "user":
        if dify_user_id:
            return f"user:{dify_user_id}"
        if dify_session_id:
            return f"session:{dify_session_id}"
        return None
    if scope == "session":
        return f"session:{dify_session_id}" if dify_session_id else None
    return None


class SessionManager:
    """In-memory mapping: scope key -> dsh_session_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str | None) -> str | None:
        if not key:
            return None
        with self._lock:
            return self._sessions.get(key)

    def set(self, key: str | None, session_id: str) -> None:
        if not key or not session_id:
            return
        with self._lock:
            self._sessions[key] = session_id

    def drop(self, key: str | None) -> None:
        if not key:
            return
        with self._lock:
            self._sessions.pop(key, None)


def _is_session_not_found(error: DshGatewayError) -> bool:
    return error.status_code == 404 and "session_not_found" in error.detail


def chat_with_session_retry(
    client: DshGatewayClient,
    manager: SessionManager,
    key: str | None,
    prompt: str,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[ChatResult, bool]:
    """Call client.chat with sticky-session handling.

    Reuses the mapped session id when present, otherwise creates one. On 404
    session_not_found, drops the mapping and retries exactly once with a new
    session. Returns (ChatResult, retried_flag).
    """
    session_id = manager.get(key)
    session_header = session_id or SESSION_HEADER_NEW
    try:
        result = client.chat(prompt, model=model, session_header=session_header, max_tokens=max_tokens)
    except DshGatewayError as e:
        if session_id and _is_session_not_found(e):
            manager.drop(key)
            result = client.chat(prompt, model=model, session_header=SESSION_HEADER_NEW, max_tokens=max_tokens)
            manager.set(key, result.session_id)
            return result, True
        raise
    manager.set(key, result.session_id)
    return result, False
