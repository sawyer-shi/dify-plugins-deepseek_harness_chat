from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dsh_client import DEFAULT_MAX_TOKENS as _DEFAULT_MAX_TOKENS
from tools.dsh_client import DshGatewayClient, DshGatewayError
from tools.session_manager import (
    SessionManager,
    chat_with_session_retry,
    resolve_scope_key,
)

SESSION_MANAGER = SessionManager()

_DEFAULT_TIMEOUT_SECONDS = 300.0
_VALID_SCOPES = {"session", "user", "none"}
_MAX_RETURN_FILES = 5
# Deliverable file types returned to the conversation by default. Intermediate
# artifacts the agent writes while producing the deliverable (build scripts,
# source code, temp files) are excluded unless the caller overrides the list
# with "*" (everything) or a custom comma-separated extension list.
_DEFAULT_FILE_EXTENSIONS = (
    ".xlsx", ".xls", ".csv", ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".html",
    ".json", ".zip",
)
# Default cap on how much of the DSH agent's text reply is handed back to the
# Dify LLM. Long reports blow up the agent app's context and cause Dify's
# "output token limit" truncation; generated files are returned separately, so
# the full prose is usually noise. 0 disables the cap.
_DEFAULT_MAX_TEXT_CHARS = 2000
# Grace window so files written a moment before the turn starts (or under mild
# clock skew between the Dify container and the DSH host) are still picked up.
_FILE_SCAN_GRACE_SECONDS = 30.0


def normalize_params(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    prompt = str(tool_parameters.get("prompt") or "").strip()
    model = str(tool_parameters.get("model") or "").strip() or "default"
    scope = str(tool_parameters.get("session_scope") or "").strip() or "session"
    if scope not in _VALID_SCOPES:
        scope = "session"
    raw_timeout = tool_parameters.get("timeout_seconds")
    try:
        timeout_seconds = (
            float(raw_timeout) if raw_timeout not in (None, "") else _DEFAULT_TIMEOUT_SECONDS
        )
    except (TypeError, ValueError):
        timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
    timeout_seconds = max(timeout_seconds, 1.0)
    include_reasoning = bool(tool_parameters.get("include_reasoning"))
    return_files = tool_parameters.get("return_files")
    return_files = True if return_files in (None, "") else bool(return_files)
    raw_limit = tool_parameters.get("max_files")
    try:
        max_files = int(raw_limit) if raw_limit not in (None, "") else _MAX_RETURN_FILES
    except (TypeError, ValueError):
        max_files = _MAX_RETURN_FILES
    max_files = max(1, min(max_files, 10))
    raw_chars = tool_parameters.get("max_text_chars")
    try:
        max_text_chars = (
            int(raw_chars) if raw_chars not in (None, "") else _DEFAULT_MAX_TEXT_CHARS
        )
    except (TypeError, ValueError):
        max_text_chars = _DEFAULT_MAX_TEXT_CHARS
    max_text_chars = max(0, max_text_chars)
    raw_mt = tool_parameters.get("max_tokens")
    try:
        max_tokens = int(raw_mt) if raw_mt not in (None, "") else _DEFAULT_MAX_TOKENS
    except (TypeError, ValueError):
        max_tokens = _DEFAULT_MAX_TOKENS
    if max_tokens < 0:
        max_tokens = _DEFAULT_MAX_TOKENS
    raw_exts = str(tool_parameters.get("file_extensions") or "").strip()
    if raw_exts == "":
        allowed_extensions = set(_DEFAULT_FILE_EXTENSIONS)
        extension_mode = "default"
    elif raw_exts == "*":
        allowed_extensions = set()
        extension_mode = "all"
    else:
        allowed_extensions = {
            ("." + token.strip().lower().lstrip(".").strip())
            for token in raw_exts.split(",")
            if token.strip()
        }
        extension_mode = "custom"
    return {
        "prompt": prompt,
        "model": model,
        "session_scope": scope,
        "timeout_seconds": timeout_seconds,
        "include_reasoning": include_reasoning,
        "return_files": return_files,
        "max_files": max_files,
        "max_text_chars": max_text_chars,
        "allowed_extensions": allowed_extensions,
        "extension_mode": extension_mode,
        "max_tokens": max_tokens,
    }


def file_allowed(name: str, allowed_extensions: set[str], mode: str) -> bool:
    if mode == "all":
        return True
    suffix = name.rsplit(".", 1)
    ext = f".{suffix[1].lower()}" if len(suffix) == 2 else ""
    return ext in allowed_extensions


def truncate_reply(text: str, limit: int) -> tuple[str, bool]:
    """Return (text, truncated). limit <= 0 means no truncation."""
    if limit <= 0 or len(text) <= limit:
        return text, False
    note = (
        f"\n\n[... DSH Agent 完整回复共 {len(text)} 字符，此处按 max_text_chars={limit} "
        "截断；生成的文件已作为附件返回，如需完整文本请在 DSH 侧查看会话。]"
    )
    return text[:limit].rstrip() + note, True


class DeepSeekHarnessChatTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        params = normalize_params(tool_parameters)
        prompt = params["prompt"]
        if not prompt:
            raise Exception("Parameter 'prompt' is required.")

        key = resolve_scope_key(
            params["session_scope"], self.runtime.session_id, self.runtime.user_id
        )
        client = DshGatewayClient(
            base_url=str(self.runtime.credentials.get("base_url") or ""),
            api_key=str(self.runtime.credentials.get("api_key") or ""),
            timeout_seconds=params["timeout_seconds"],
        )

        # Upload user-attached files into the gateway workspace and tell the
        # agent where they live, so it can read them with its workspace tools.
        uploaded: list[dict] = []
        raw_files = tool_parameters.get("files") or []
        if not isinstance(raw_files, list):
            raw_files = [raw_files]
        for item in raw_files:
            try:
                blob = item.blob
                name = str(getattr(item, "filename", "") or getattr(item, "extension", "") or "upload.bin")
                info = client.upload_file(blob, name)
                uploaded.append(
                    {
                        "name": info.get("name") or name,
                        "path": info.get("path") or "",
                        "size": info.get("size"),
                    }
                )
            except DshGatewayError as e:
                raise Exception(f"Failed to upload attachment '{getattr(item, 'filename', '?')}': {e.message}") from e
            except Exception as e:
                raise Exception(f"Failed to read attachment: {e}") from e

        effective_prompt = prompt
        if uploaded:
            listing = "; ".join(f"{f['name']} (工作区相对路径: {f['name']})" for f in uploaded)
            effective_prompt = (
                f"{prompt}\n\n[系统提示] 用户随消息上传了以下文件，已保存到你的工作区：{listing}。"
                "请先用工作区工具读取/检查这些文件，再基于其内容完成用户任务。"
            )

        turn_started_at = time.time() - _FILE_SCAN_GRACE_SECONDS
        uploaded_paths = {str(f.get("path") or "") for f in uploaded if f.get("path")}
        uploaded_names = {str(f.get("name") or "") for f in uploaded if f.get("name")}
        try:
            result, _retried = chat_with_session_retry(
                client, SESSION_MANAGER, key, effective_prompt, params["model"],
                max_tokens=params["max_tokens"],
            )
        except DshGatewayError as e:
            raise Exception(e.message) from e

        reply = result.content
        if params["include_reasoning"] and result.reasoning:
            reply = f"<think>\n{result.reasoning}\n</think>\n\n{reply}"

        reply_text, truncated = truncate_reply(reply, params["max_text_chars"])
        yield self.create_text_message(reply_text)

        produced_files: list[dict] = []
        if params["return_files"]:
            try:
                candidates = client.list_files(since=turn_started_at)
            except DshGatewayError:
                candidates = []
            for entry in candidates:
                path = str(entry.get("path") or "")
                name = str(entry.get("name") or "")
                if not path or not name:
                    continue
                # Never hand the user's own uploads back as "generated files".
                if path in uploaded_paths or name in uploaded_names:
                    continue
                if not file_allowed(name, params["allowed_extensions"], params["extension_mode"]):
                    continue
                if len(produced_files) >= params["max_files"]:
                    break
                try:
                    blob, mime_type = client.download_file(path)
                except DshGatewayError:
                    continue
                if not blob:
                    continue
                produced_files.append(
                    {"name": name, "size": entry.get("size"), "mime_type": mime_type}
                )
                yield self.create_blob_message(
                    blob,
                    meta={
                        "mime_type": mime_type,
                        "mimetype": mime_type,
                        "filename": name,
                    },
                )

        yield self.create_json_message(
            {
                "session_id": result.session_id,
                "scope": params["session_scope"],
                "reply_chars": len(result.content),
                "reply_preview": result.content[:300],
                "reply_truncated": truncated,
                "tool_calls": len(result.tool_call_names),
                "tool_call_names": sorted(set(result.tool_call_names)),
                "model": result.model or params["model"],
                "uploaded_files": uploaded,
                "files": produced_files,
            }
        )
