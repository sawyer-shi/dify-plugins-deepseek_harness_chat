from tools.chat import normalize_params


class TestNormalizeParams:
    def test_defaults(self):
        p = normalize_params({"prompt": "hi"})
        assert p == {
            "prompt": "hi",
            "model": "default",
            "session_scope": "session",
            "timeout_seconds": 300.0,
            "include_reasoning": False,
        }

    def test_empty_prompt_kept_for_validation_in_invoke(self):
        p = normalize_params({})
        assert p["prompt"] == ""
        assert p["model"] == "default"

    def test_model_falls_back_to_default_when_blank(self):
        assert normalize_params({"prompt": "x", "model": "  "})["model"] == "default"

    def test_scope_invalid_falls_back_to_session(self):
        assert normalize_params({"prompt": "x", "session_scope": "wat"})["session_scope"] == "session"

    def test_scope_user_and_none_pass_through(self):
        assert normalize_params({"prompt": "x", "session_scope": "user"})["session_scope"] == "user"
        assert normalize_params({"prompt": "x", "session_scope": "none"})["session_scope"] == "none"

    def test_timeout_string_coerced(self):
        assert normalize_params({"prompt": "x", "timeout_seconds": "60"})["timeout_seconds"] == 60.0

    def test_timeout_invalid_falls_back(self):
        assert normalize_params({"prompt": "x", "timeout_seconds": "abc"})["timeout_seconds"] == 300.0

    def test_timeout_minimum_clamped(self):
        assert normalize_params({"prompt": "x", "timeout_seconds": 0})["timeout_seconds"] == 1.0

    def test_include_reasoning_truthy(self):
        assert normalize_params({"prompt": "x", "include_reasoning": True})["include_reasoning"] is True
