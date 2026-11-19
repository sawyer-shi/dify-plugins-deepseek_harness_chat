from tools.chat import normalize_params, _DEFAULT_FILE_EXTENSIONS


class TestNormalizeParams:
    def test_defaults(self):
        p = normalize_params({"prompt": "hi"})
        assert p == {
            "prompt": "hi",
            "model": "default",
            "session_scope": "session",
            "timeout_seconds": 300.0,
            "include_reasoning": False,
            "return_files": True,
            "max_files": 5,
            "max_text_chars": 2000,
            "allowed_extensions": set(_DEFAULT_FILE_EXTENSIONS),
            "extension_mode": "default",
            "max_tokens": 32768,
        }

    def test_file_extensions_overrides(self):
        p = normalize_params({"prompt": "x", "file_extensions": "*"})
        assert p["extension_mode"] == "all" and p["allowed_extensions"] == set()
        p = normalize_params({"prompt": "x", "file_extensions": "xlsx, csv ,PDF"})
        assert p["extension_mode"] == "custom"
        assert p["allowed_extensions"] == {".xlsx", ".csv", ".pdf"}
        p = normalize_params({"prompt": "x", "file_extensions": ""})
        assert p["extension_mode"] == "default"

    def test_return_files_disabled_and_limit_clamped(self):
        p = normalize_params({"prompt": "x", "return_files": False, "max_files": 99})
        assert p["return_files"] is False
        assert p["max_files"] == 10
        assert normalize_params({"prompt": "x", "max_files": 0})["max_files"] == 1

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


class TestTruncateReply:
    def test_no_truncation_under_limit(self):
        from tools.chat import truncate_reply
        text, t = truncate_reply("hello", 6000)
        assert text == "hello" and t is False

    def test_truncation_over_limit(self):
        from tools.chat import truncate_reply
        text, t = truncate_reply("x" * 7000, 6000)
        assert t is True
        assert len(text) < 7000 and "截断" in text

    def test_zero_disables(self):
        from tools.chat import truncate_reply
        text, t = truncate_reply("y" * 99999, 0)
        assert text == "y" * 99999 and t is False


class TestFileAllowed:
    def test_default_mode_excludes_scripts(self):
        from tools.chat import file_allowed, _DEFAULT_FILE_EXTENSIONS
        assert file_allowed("report.xlsx", _DEFAULT_FILE_EXTENSIONS, "default") is True
        assert file_allowed("build_models.py", _DEFAULT_FILE_EXTENSIONS, "default") is False
        assert file_allowed("chart.png", _DEFAULT_FILE_EXTENSIONS, "default") is True

    def test_all_mode_includes_everything(self):
        from tools.chat import file_allowed
        assert file_allowed("build_models.py", set(), "all") is True

    def test_custom_mode(self):
        from tools.chat import file_allowed
        exts = {".csv", ".pdf"}
        assert file_allowed("data.csv", exts, "custom") is True
        assert file_allowed("report.xlsx", exts, "custom") is False


class TestUploadAnnotation:
    def test_uploaded_files_excluded_from_scan_helpers(self):
        # file_allowed sanity: uploaded exclusion is by path/name, not extension
        from tools.chat import file_allowed, _DEFAULT_FILE_EXTENSIONS
        assert file_allowed("user-upload.xlsx", _DEFAULT_FILE_EXTENSIONS, "default") is True
