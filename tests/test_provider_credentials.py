import httpx
import pytest
import respx
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.deepseek_harness import DeepSeekHarnessProvider

BASE = "http://127.0.0.1:41540"


def _provider() -> DeepSeekHarnessProvider:
    return DeepSeekHarnessProvider()


def _creds(base_url=BASE, api_key="sk-dsh-test"):
    return {"base_url": base_url, "api_key": api_key}


@respx.mock
def test_valid_credentials_returns_none():
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "p/m"}]})
    )
    assert _provider()._validate_credentials(_creds()) is None


def test_missing_fields_rejected_without_http_call():
    with pytest.raises(ToolProviderCredentialValidationError):
        _provider()._validate_credentials({"base_url": "", "api_key": ""})


@respx.mock
def test_invalid_key_message():
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(401, text="invalid_api_key")
    )
    with pytest.raises(ToolProviderCredentialValidationError) as ei:
        _provider()._validate_credentials(_creds())
    assert "API key" in str(ei.value)


@respx.mock
def test_gateway_down_message_mentions_docker():
    respx.get(f"{BASE}/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ToolProviderCredentialValidationError) as ei:
        _provider()._validate_credentials(_creds())
    assert "host.docker.internal" in str(ei.value)


@respx.mock
def test_base_url_with_trailing_v1_normalized():
    route = respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    _provider()._validate_credentials(_creds(base_url=f"{BASE}/v1/"))
    assert route.called
