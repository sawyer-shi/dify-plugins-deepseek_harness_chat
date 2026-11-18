from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx

DEFAULT_MAX_TOKENS = 8192
TOOL_CALL_COMMENT_PREFIX = "dsh tool-call "


class DshGatewayError(Exception):
    def __init__(
        self, message: str, status_code: int | None = None, detail: str = ""
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


@dataclass
class ChatResult:
    content: str = ""
    reasoning: str = ""
    session_id: str = ""
    model: str = ""
    tool_call_names: list[str] = field(default_factory=list)


def normalize_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")]
    return url


def build_headers(
    api_key: str, session_header: str | None, accept: str = "application/json"
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": accept,
    }
    if session_header:
        headers["X-DSH-Session"] = session_header
    return headers


def build_body(model: str, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": max_tokens,
    }


def parse_sse_lines(lines: Iterable[str]) -> ChatResult:
    result = ChatResult()
    for raw in lines:
        line = raw.rstrip("\r").rstrip("\n")
        if not line:
            continue
        if line.startswith(":"):
            comment = line.lstrip(":").strip()
            if comment.startswith(TOOL_CALL_COMMENT_PREFIX):
                name = comment[len(TOOL_CALL_COMMENT_PREFIX):].strip()
                if name:
                    result.tool_call_names.append(name)
            continue
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(chunk, dict):
            continue
        if not result.session_id:
            sid = chunk.get("dsh_session_id")
            if isinstance(sid, str) and sid:
                result.session_id = sid
        if not result.model:
            model = chunk.get("model")
            if isinstance(model, str) and model:
                result.model = model
        choices = chunk.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str):
                    result.content += content
                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str):
                    result.reasoning += reasoning
    return result


def friendly_error_message(status_code: int | None, detail: str = "") -> str:
    base = (detail or "").strip()
    if status_code == 401:
        return (
            "Invalid API key (401). Check the key in "
            "$DSH_HOME/openai-gateway/api-keys.json."
        )
    if status_code == 404:
        if "session_not_found" in base:
            return (
                "Session not found (404). The gateway evicted or restarted the "
                "session; retrying with a new session."
            )
        if "model_not_found" in base:
            return (
                "Model not found (404). Use 'default' or a model id from "
                "GET /v1/models (e.g. 'provider/model')."
            )
        return f"Not found (404): {base}"
    if status_code == 504:
        return (
            "Agent turn timed out (504). Increase timeout_seconds or simplify "
            "the task."
        )
    if status_code is None:
        return (
            "Cannot connect to the DSH gateway. Ensure DeepSeek Harness and "
            "dsh-openai-gateway are running and the base URL is correct "
            "(use http://host.docker.internal:41540 if Dify runs in Docker)."
        )
    return f"Gateway error ({status_code}): {base}"


class DshGatewayClient:
    def __init__(
        self, base_url: str, api_key: str, timeout_seconds: float = 300.0
    ) -> None:
        self._base = normalize_base_url(base_url)
        self._api_key = api_key
        self._timeout = timeout_seconds

    def chat(
        self, prompt: str, model: str = "default", session_header: str = "new"
    ) -> ChatResult:
        url = f"{self._base}/v1/chat/completions"
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self._timeout, connect=10.0)
            ) as client:
                with client.stream(
                    "POST",
                    url,
                    headers=build_headers(
                        self._api_key,
                        session_header,
                        accept="text/event-stream",
                    ),
                    json=build_body(model, prompt),
                ) as response:
                    if response.status_code != 200:
                        body = response.read().decode("utf-8", errors="replace")
                        raise DshGatewayError(
                            friendly_error_message(response.status_code, body),
                            status_code=response.status_code,
                            detail=body,
                        )
                    result = parse_sse_lines(response.iter_lines())
                    header_session = response.headers.get("X-DSH-Session")
                    if not result.session_id and header_session:
                        result.session_id = header_session
                    return result
        except httpx.TimeoutException as e:
            raise DshGatewayError(
                "Agent turn timed out. Increase timeout_seconds or simplify "
                "the task."
            ) from e
        except httpx.ConnectError as e:
            raise DshGatewayError(friendly_error_message(None)) from e
        except httpx.HTTPError as e:
            raise DshGatewayError(f"Gateway request failed: {e}") from e

    def list_models(self) -> list[dict]:
        url = f"{self._base}/v1/models"
        try:
            with httpx.Client(timeout=httpx.Timeout(self._timeout, connect=10.0)) as client:
                response = client.get(url, headers=build_headers(self._api_key, None))
                if response.status_code != 200:
                    raise DshGatewayError(
                        friendly_error_message(response.status_code, response.text),
                        status_code=response.status_code,
                        detail=response.text,
                    )
                data = response.json()
                if isinstance(data, dict):
                    models = data.get("data")
                    if isinstance(models, list):
                        return [m for m in models if isinstance(m, dict)]
                return []
        except httpx.TimeoutException as e:
            raise DshGatewayError(
                "Timed out while listing models from the gateway."
            ) from e
        except httpx.ConnectError as e:
            raise DshGatewayError(friendly_error_message(None)) from e
        except httpx.HTTPError as e:
            raise DshGatewayError(f"Gateway request failed: {e}") from e
