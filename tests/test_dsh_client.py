import pytest

from tools.dsh_client import (
    DEFAULT_MAX_TOKENS,
    ChatResult,
    DshGatewayError,
    build_body,
    build_headers,
    friendly_error_message,
    normalize_base_url,
    parse_sse_lines,
)


class TestNormalizeBaseUrl:
    def test_strips_trailing_slash(self):
        assert normalize_base_url("http://127.0.0.1:41540/") == "http://127.0.0.1:41540"

    def test_strips_trailing_v1(self):
        assert normalize_base_url("http://127.0.0.1:41540/v1") == "http://127.0.0.1:41540"

    def test_strips_trailing_v1_slash(self):
        assert normalize_base_url("http://x:1/v1/") == "http://x:1"

    def test_plain_url_unchanged(self):
        assert normalize_base_url("http://127.0.0.1:41540") == "http://127.0.0.1:41540"

    def test_strips_whitespace(self):
        assert normalize_base_url("  http://x:1  ") == "http://x:1"


class TestBuildHeaders:
    def test_bearer_and_session(self):
        h = build_headers("sk-dsh-abc", "new")
        assert h["Authorization"] == "Bearer sk-dsh-abc"
        assert h["X-DSH-Session"] == "new"
        assert h["Content-Type"] == "application/json"

    def test_existing_session_id(self):
        h = build_headers("k", "openai-123")
        assert h["X-DSH-Session"] == "openai-123"

    def test_no_session_header_when_none(self):
        h = build_headers("k", None)
        assert "X-DSH-Session" not in h

    def test_accept_override(self):
        assert build_headers("k", None, accept="text/event-stream")["Accept"] == "text/event-stream"


class TestBuildBody:
    def test_structure(self):
        body = build_body("default", "hello", max_tokens=512)
        assert body == {
            "model": "default",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "max_tokens": 512,
        }

    def test_default_max_tokens(self):
        assert build_body("m", "p")["max_tokens"] == DEFAULT_MAX_TOKENS


class TestParseSseLines:
    def test_content_accumulation(self):
        lines = [
            'data: {"choices": [{"delta": {"content": "Hel"}}]}',
            'data: {"choices": [{"delta": {"content": "lo"}}]}',
            "data: [DONE]",
        ]
        result = parse_sse_lines(lines)
        assert result.content == "Hello"

    def test_reasoning_accumulation(self):
        lines = [
            'data: {"choices": [{"delta": {"reasoning_content": "think-"}}]}',
            'data: {"choices": [{"delta": {"reasoning_content": "ing"}}]}',
            'data: {"choices": [{"delta": {"content": "answer"}}]}',
            "data: [DONE]",
        ]
        result = parse_sse_lines(lines)
        assert result.reasoning == "think-ing"
        assert result.content == "answer"

    def test_tool_call_comment_frames(self):
        lines = [
            ": dsh tool-call read_file",
            'data: {"choices": [{"delta": {"content": "x"}}]}',
            ": dsh tool-call read_file",
            ": dsh tool-call write_file",
            "data: [DONE]",
        ]
        result = parse_sse_lines(lines)
        assert result.tool_call_names == ["read_file", "read_file", "write_file"]

    def test_ignores_other_comments_and_blank_lines(self):
        lines = ["", ": keep-alive", 'data: {"choices": [{"delta": {"content": "a"}}]}']
        result = parse_sse_lines(lines)
        assert result.content == "a"

    def test_session_id_and_model_from_top_level_fields(self):
        lines = [
            'data: {"dsh_session_id": "openai-abc", "model": "deepseek-official/deepseek-v4-flash", "choices": [{"delta": {"content": "a"}}]}',
            "data: [DONE]",
        ]
        result = parse_sse_lines(lines)
        assert result.session_id == "openai-abc"
        assert result.model == "deepseek-official/deepseek-v4-flash"

    def test_malformed_json_skipped(self):
        lines = ["data: {not json", 'data: {"choices": [{"delta": {"content": "ok"}}]}']
        result = parse_sse_lines(lines)
        assert result.content == "ok"

    def test_crLf_lines(self):
        lines = ['data: {"choices": [{"delta": {"content": "a"}}]}\r\n', "data: [DONE]\r\n"]
        result = parse_sse_lines(lines)
        assert result.content == "a"

    def test_empty_input(self):
        assert parse_sse_lines([]) == ChatResult()


class TestFriendlyErrorMessage:
    def test_unauthorized(self):
        msg = friendly_error_message(401, '{"error":"invalid_api_key"}')
        assert "401" in msg and "API key" in msg

    def test_session_not_found(self):
        msg = friendly_error_message(404, '{"error":"session_not_found"}')
        assert "404" in msg and "session" in msg.lower()

    def test_model_not_found(self):
        msg = friendly_error_message(404, '{"error":"model_not_found"}')
        assert "404" in msg and "model" in msg.lower()

    def test_other_404(self):
        assert "404" in friendly_error_message(404, "whatever")

    def test_timeout_504(self):
        msg = friendly_error_message(504, "")
        assert "504" in msg and "timeout" in msg.lower()

    def test_connection_error(self):
        msg = friendly_error_message(None, "")
        assert "connect" in msg.lower() and "host.docker.internal" in msg

    def test_other_status(self):
        assert "500" in friendly_error_message(500, "boom")


class TestDshGatewayError:
    def test_attributes(self):
        e = DshGatewayError("msg", status_code=404, detail='{"error":"session_not_found"}')
        assert e.message == "msg"
        assert e.status_code == 404
        assert "session_not_found" in e.detail
        assert str(e) == "msg"


import httpx
import respx

from tools.dsh_client import DshGatewayClient

BASE = "http://127.0.0.1:41540"


def _sse(*events: str) -> str:
    return "".join(f"data: {e}\n\n" for e in events)


class TestDshGatewayClient:
    def _client(self, timeout: float = 30.0) -> DshGatewayClient:
        return DshGatewayClient(base_url=BASE, api_key="sk-dsh-test", timeout_seconds=timeout)

    @respx.mock
    def test_chat_streams_and_accumulates(self):
        route = respx.post(f"{BASE}/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                headers={"X-DSH-Session": "openai-hdr"},
                text=_sse(
                    '{"dsh_session_id": "openai-1", "model": "m1", "choices": [{"delta": {"content": "Hi"}}]}',
                    '{"choices": [{"delta": {"content": " there"}}]}',
                    "[DONE]",
                ),
            )
        )
        result = self._client().chat("hello", model="default", session_header="new")
        assert result.content == "Hi there"
        assert result.session_id == "openai-1"
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer sk-dsh-test"
        assert request.headers["X-DSH-Session"] == "new"
        import json as _json

        body = _json.loads(request.content)
        assert body["model"] == "default"
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        assert body["stream"] is True

    @respx.mock
    def test_chat_session_id_falls_back_to_response_header(self):
        respx.post(f"{BASE}/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                headers={"X-DSH-Session": "openai-from-header"},
                text=_sse('{"choices": [{"delta": {"content": "ok"}}]}', "[DONE]"),
            )
        )
        result = self._client().chat("hello")
        assert result.session_id == "openai-from-header"

    @respx.mock
    def test_chat_error_status_raises_with_detail(self):
        respx.post(f"{BASE}/v1/chat/completions").mock(
            return_value=httpx.Response(404, text='{"error": "model_not_found"}')
        )
        with pytest.raises(DshGatewayError) as ei:
            self._client().chat("hello", model="bad")
        assert ei.value.status_code == 404
        assert "model" in ei.value.message.lower()

    @respx.mock
    def test_chat_connect_error_raises_connection_message(self):
        respx.post(f"{BASE}/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("refused")
        )
        with pytest.raises(DshGatewayError) as ei:
            self._client().chat("hello")
        assert ei.value.status_code is None
        assert "host.docker.internal" in ei.value.message

    @respx.mock
    def test_chat_timeout_raises_timeout_message(self):
        respx.post(f"{BASE}/v1/chat/completions").mock(
            side_effect=httpx.ReadTimeout("t")
        )
        with pytest.raises(DshGatewayError) as ei:
            self._client().chat("hello")
        assert "504" in ei.value.message or "timed out" in ei.value.message.lower()

    @respx.mock
    def test_list_models_ok(self):
        respx.get(f"{BASE}/v1/models").mock(
            return_value=httpx.Response(
                200, json={"object": "list", "data": [{"id": "p/m"}]}
            )
        )
        models = self._client().list_models()
        assert models == [{"id": "p/m"}]

    @respx.mock
    def test_list_models_unauthorized(self):
        respx.get(f"{BASE}/v1/models").mock(
            return_value=httpx.Response(401, text="invalid_api_key")
        )
        with pytest.raises(DshGatewayError) as ei:
            self._client().list_models()
        assert ei.value.status_code == 401
