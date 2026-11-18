from __future__ import annotations

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.dsh_client import DshGatewayClient, DshGatewayError


class DeepSeekHarnessProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        base_url = str(credentials.get("base_url") or "").strip()
        api_key = str(credentials.get("api_key") or "").strip()
        if not base_url or not api_key:
            raise ToolProviderCredentialValidationError(
                "Both 'Gateway Base URL' and 'API Key' are required."
            )
        client = DshGatewayClient(
            base_url=base_url, api_key=api_key, timeout_seconds=15.0
        )
        try:
            client.list_models()
        except DshGatewayError as e:
            raise ToolProviderCredentialValidationError(e.message) from e
