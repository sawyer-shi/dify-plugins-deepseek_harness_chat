import glob

import yaml


def test_all_yaml_files_parse():
    files = (
        glob.glob("*.yaml")
        + glob.glob("provider/*.yaml")
        + glob.glob("tools/*.yaml")
    )
    assert len(files) >= 3
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), path


def test_manifest_fields():
    with open("manifest.yaml", encoding="utf-8") as f:
        m = yaml.safe_load(f)
    assert m["type"] == "plugin"
    assert m["name"] == "deepseek_harness_chat"
    assert m["author"] == "sawyer-shi"
    assert m["plugins"]["tools"] == ["provider/deepseek_harness.yaml"]
    assert m["meta"]["runner"]["version"] == "3.12"
    assert m["resource"]["permission"]["tool"]["enabled"] is True


def test_provider_yaml_credentials():
    with open("provider/deepseek_harness.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    creds = p["credentials_for_provider"]
    assert creds["api_key"]["type"] == "secret-input"
    assert creds["api_key"]["required"] is True
    assert creds["base_url"]["default"] == "http://127.0.0.1:41540"


def test_tool_yaml_parameters():
    with open("tools/chat.yaml", encoding="utf-8") as f:
        t = yaml.safe_load(f)
    params = {p["name"]: p for p in t["parameters"]}
    assert params["prompt"]["required"] is True
    assert params["model"]["default"] == "default"
    assert params["session_scope"]["default"] == "session"
    assert {o["value"] for o in params["session_scope"]["options"]} == {
        "session",
        "user",
        "none",
    }
    assert params["timeout_seconds"]["default"] == 300
    assert params["include_reasoning"]["default"] is False
