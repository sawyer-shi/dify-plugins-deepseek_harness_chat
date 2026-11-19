import pytest

from tools.dsh_client import ChatResult, DshGatewayError
from tools.session_manager import (
    SESSION_HEADER_NEW,
    SessionManager,
    chat_with_session_retry,
    resolve_scope_key,
)


class TestResolveScopeKey:
    def test_session_scope(self):
        assert resolve_scope_key("session", "conv-1", "u-1") == "session:conv-1"

    def test_session_scope_without_session_id(self):
        assert resolve_scope_key("session", None, "u-1") is None

    def test_user_scope(self):
        assert resolve_scope_key("user", "conv-1", "u-1") == "user:u-1"

    def test_user_scope_falls_back_to_session(self):
        assert resolve_scope_key("user", "conv-1", None) == "session:conv-1"

    def test_user_scope_without_both(self):
        assert resolve_scope_key("user", None, None) is None

    def test_none_scope(self):
        assert resolve_scope_key("none", "conv-1", "u-1") is None

    def test_unknown_scope_treated_as_stateless(self):
        assert resolve_scope_key("bogus", "conv-1", "u-1") is None


class TestSessionManager:
    def test_set_get_drop(self):
        m = SessionManager()
        assert m.get("session:conv-1") is None
        m.set("session:conv-1", "openai-1")
        assert m.get("session:conv-1") == "openai-1"
        m.drop("session:conv-1")
        assert m.get("session:conv-1") is None

    def test_drop_missing_key_is_noop(self):
        m = SessionManager()
        m.drop("nope")

    def test_none_key_is_ignored(self):
        m = SessionManager()
        m.set(None, "x")
        assert m.get(None) is None


class FakeClient:
    def __init__(self, results=None, error=None):
        self.results = list(results or [])
        self.error = error
        self.calls: list[str] = []

    def chat(self, prompt, model="default", session_header="new", max_tokens=None):
        self.calls.append(session_header)
        if self.error is not None:
            raise self.error
        return self.results.pop(0)


def _result(session_id="openai-new", content="ok"):
    return ChatResult(content=content, session_id=session_id)


class TestChatWithSessionRetry:
    def test_first_call_creates_and_stores_session(self):
        m = SessionManager()
        client = FakeClient(results=[_result("openai-1")])
        result, retried = chat_with_session_retry(
            client, m, "session:conv-1", "hi", "default"
        )
        assert client.calls == [SESSION_HEADER_NEW]
        assert result.session_id == "openai-1"
        assert retried is False
        assert m.get("session:conv-1") == "openai-1"

    def test_second_call_reuses_stored_session(self):
        m = SessionManager()
        m.set("session:conv-1", "openai-1")
        client = FakeClient(results=[_result("openai-1")])
        result, retried = chat_with_session_retry(
            client, m, "session:conv-1", "hi again", "default"
        )
        assert client.calls == ["openai-1"]
        assert retried is False

    def test_stateless_key_none_always_new(self):
        m = SessionManager()
        client = FakeClient(results=[_result("openai-temp")])
        chat_with_session_retry(client, m, None, "hi", "default")
        assert client.calls == [SESSION_HEADER_NEW]
        assert m.get(None) is None

    def test_session_not_found_recreates_and_stores(self):
        m = SessionManager()
        m.set("session:conv-1", "openai-stale")
        err = DshGatewayError(
            "Session not found (404)",
            status_code=404,
            detail='{"error": "session_not_found"}',
        )

        class RetryClient(FakeClient):
            def chat(self, prompt, model="default", session_header="new", max_tokens=None):
                self.calls.append(session_header)
                if len(self.calls) == 1:
                    raise self.error
                return self.results.pop(0)

        retry_client = RetryClient(results=[_result("openai-fresh")])
        retry_client.error = err
        result, retried = chat_with_session_retry(
            retry_client, m, "session:conv-1", "hi", "default"
        )
        assert retry_client.calls == ["openai-stale", SESSION_HEADER_NEW]
        assert retried is True
        assert result.session_id == "openai-fresh"
        assert m.get("session:conv-1") == "openai-fresh"

    def test_model_not_found_not_retried(self):
        m = SessionManager()
        m.set("session:conv-1", "openai-1")
        err = DshGatewayError(
            "Model not found (404)",
            status_code=404,
            detail='{"error": "model_not_found"}',
        )
        client = FakeClient(error=err)
        with pytest.raises(DshGatewayError):
            chat_with_session_retry(client, m, "session:conv-1", "hi", "bad-model")
        assert client.calls == ["openai-1"]

    def test_non_404_error_not_retried(self):
        m = SessionManager()
        m.set("session:conv-1", "openai-1")
        err = DshGatewayError("Gateway error (500): boom", status_code=500, detail="boom")
        client = FakeClient(error=err)
        with pytest.raises(DshGatewayError):
            chat_with_session_retry(client, m, "session:conv-1", "hi", "default")
        assert client.calls == ["openai-1"]
