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
