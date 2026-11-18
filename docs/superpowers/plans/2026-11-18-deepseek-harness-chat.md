# DeepSeek Harness Chat 插件实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Dify 工具插件 `deepseek_harness_chat`，通过 dsh-openai-gateway（OpenAI 兼容 API，默认 `127.0.0.1:41540`）与本地 DeepSeek Harness Agent 对话，支持会话级/用户级/无状态三种会话级别。

**Architecture:** Tool 插件。`tools/dsh_client.py`（纯函数 + httpx 客户端，SSE 内部流式累积）、`tools/session_manager.py`（scope 键推导、dsh_session_id 映射、404 自动重建）、`tools/chat.py`（薄编排层）、`provider/deepseek_harness.py`（凭据校验 GET /v1/models）。

**Tech Stack:** Python 3.12、`dify_plugin>=0.9.0,<0.11.0`、`httpx>=0.28.1`、pytest + respx（dev）、uv。

**Spec:** `docs/superpowers/specs/2026-11-18-deepseek-harness-chat-design.md`（本计划从 spec 出发，执行者须同时阅读 spec）

## Global Constraints

- Python 3.12；依赖：`dify_plugin>=0.9.0,<0.11.0`、`httpx>=0.28.1`；dev：`pytest`、`respx`、`pyyaml`
- 插件 `name: deepseek_harness_chat`、`author: sawyer-shi`；provider `name: deepseek_harness`；tool `name: chat`
- `base_url` 默认 `http://127.0.0.1:41540`；规范化规则：去尾部 `/`，再去尾部 `/v1`
- 粘性会话头：`X-DSH-Session: new`（新建）或 `X-DSH-Session: <id>`（复用）
- 所有文件 UTF-8 无 BOM；仓库根目录 = 插件目录
- 每个任务结束前 `uv run pytest -v` 必须全绿
- 环境（Windows PowerShell）：工作目录 `D:\Cursor\dify-plugins-deepseek_harness_chat`

## Preflight: 环境准备（一次性）

- [ ] **Step 0.1: 检查工具链**

```powershell
python --version   # 期望 3.12.x；若非，尝试 py -3.12 --version
uv --version       # 若无：pip install uv
```

- [ ] **Step 0.2: 初始化依赖（Task 1 创建 pyproject.toml 之后执行 `uv sync`）**

uv 不可用时的备选（后续所有 `uv run X` 替换为 `.venv\Scripts\X`）：

```powershell
python -m venv .venv
.venv\Scripts\pip install "dify_plugin>=0.9.0,<0.11.0" "httpx>=0.28.1" pytest respx pyyaml
```

---

### Task 1: 插件骨架（结构文件 + 静态配置）

**Files:**
- Create: `manifest.yaml`, `main.py`, `pyproject.toml`, `.python-version`, `conftest.py`, `.gitignore`, `.difyignore`, `PRIVACY.md`, `README.md`（占位，Task 7 完善）
- Create: `_assets/icon.svg`, `_assets/icon-dark.svg`
- Create: `provider/__init__.py`, `provider/deepseek_harness.yaml`, `provider/deepseek_harness.py`（骨架，Task 6 实现）
- Create: `tools/__init__.py`, `tools/chat.yaml`, `tools/chat.py`（骨架，Task 5 实现）
- Create: `tests/__init__.py`, `tests/test_structure.py`

**Interfaces:**
- Consumes: 无（首任务）
- Produces: 包结构 `tools.*`、`provider.*` 可导入；`manifest.yaml`/`provider/deepseek_harness.yaml`/`tools/chat.yaml` 三个 YAML 可被解析（Task 6/5 依赖）

- [ ] **Step 1.1: 创建 `manifest.yaml`**

```yaml
version: 0.0.1
type: plugin
author: sawyer-shi
name: deepseek_harness_chat
label:
  en_US: DeepSeek Harness Chat
  zh_Hans: DeepSeek Harness 对话
description:
  en_US: >
    Chat with a local DeepSeek Harness (DSH) agent through the dsh-openai-gateway
    OpenAI-compatible API. Supports session-level and user-level sticky agent sessions.
  zh_Hans: >
    通过 dsh-openai-gateway 的 OpenAI 兼容 API 与本地 DeepSeek Harness (DSH) Agent
    对话。支持会话级与用户级粘性会话。
icon: icon.svg
icon_dark: icon-dark.svg
created_at: "2026-11-18T00:00:00Z"
tags:
  - productivity
  - utilities
resource:
  memory: 268435456
  permission:
    tool:
      enabled: true
plugins:
  tools:
    - provider/deepseek_harness.yaml
meta:
  version: 0.0.1
  arch:
    - amd64
    - arm64
  runner:
    language: python
    version: "3.12"
    entrypoint: main
privacy: PRIVACY.md
repo: https://github.com/sawyer-shi/dify-plugins-deepseek_harness_chat
verified: false
```

- [ ] **Step 1.2: 创建 `main.py`**

```python
from dify_plugin import DifyPluginEnv, Plugin

plugin = Plugin(DifyPluginEnv())

if __name__ == "__main__":
    plugin.run()
```

- [ ] **Step 1.3: 创建 `pyproject.toml`**

```toml
[project]
name = "deepseek-harness-chat-pLg7Wq2x"
version = "0.1.0"
description = "Dify tool plugin: chat with a local DeepSeek Harness agent via dsh-openai-gateway"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "dify_plugin>=0.9.0,<0.11.0",
    "httpx>=0.28.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "respx>=0.22.0",
    "pyyaml>=6.0",
]
```

- [ ] **Step 1.4: 创建小文件**

`.python-version`：

```
3.12
```

`conftest.py`（空文件，使 pytest 将仓库根加入 `sys.path`）：

```python
```

`.gitignore`：

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.env
*.difypkg
```

`.difyignore`：

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.env
*.difypkg
.github/
tests/
docs/
```

`PRIVACY.md`：

```markdown
# Privacy Statement

This plugin runs locally inside your Dify plugin daemon. It sends only the tool
parameters you provide (prompt, model, session scope, timeout) directly to the
gateway base URL you configure (by default `http://127.0.0.1:41540`, your local
dsh-openai-gateway). No data is collected, stored, or shared with any third
party by this plugin.
```

`README.md`（占位，Task 7 替换全文）：

```markdown
# deepseek_harness_chat

Dify tool plugin: chat with a local DeepSeek Harness (DSH) agent via
dsh-openai-gateway. (Full documentation coming with implementation.)
```

- [ ] **Step 1.5: 创建图标 `_assets/icon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <rect x="2" y="2" width="44" height="44" rx="10" fill="#2962FF"/>
  <path d="M11 15h26v15H23l-6 5v-5h-6z" fill="#FFFFFF"/>
  <text x="16" y="26.5" font-family="Consolas,monospace" font-size="10" font-weight="bold" fill="#2962FF">&gt;_</text>
</svg>
```

`_assets/icon-dark.svg`（仅背景色不同）：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <rect x="2" y="2" width="44" height="44" rx="10" fill="#5B8CFF"/>
  <path d="M11 15h26v15H23l-6 5v-5h-6z" fill="#0D1117"/>
  <text x="16" y="26.5" font-family="Consolas,monospace" font-size="10" font-weight="bold" fill="#5B8CFF">&gt;_</text>
</svg>
```

- [ ] **Step 1.6: 创建 `provider/deepseek_harness.yaml`**

```yaml
identity:
  author: sawyer-shi
  name: deepseek_harness
  label:
    en_US: DeepSeek Harness
    zh_Hans: DeepSeek Harness
  description:
    en_US: >
      Chat with a local DeepSeek Harness (DSH) agent through the dsh-openai-gateway
      OpenAI-compatible API, with session-level and user-level sticky agent sessions.
    zh_Hans: >
      通过 dsh-openai-gateway 的 OpenAI 兼容 API 与本地 DeepSeek Harness (DSH) Agent
      对话，支持会话级与用户级粘性会话。
  icon: icon.svg
  tags:
    - productivity
    - utilities
credentials_for_provider:
  api_key:
    type: secret-input
    required: true
    label:
      en_US: API Key
      zh_Hans: API 密钥
    placeholder:
      en_US: sk-dsh-...
      zh_Hans: sk-dsh-...
    help:
      en_US: >
        Bearer key of dsh-openai-gateway, found in $DSH_HOME/openai-gateway/api-keys.json.
      zh_Hans: >
        dsh-openai-gateway 的 Bearer 密钥，见 $DSH_HOME/openai-gateway/api-keys.json。
  base_url:
    type: text-input
    required: true
    default: http://127.0.0.1:41540
    label:
      en_US: Gateway Base URL
      zh_Hans: 网关地址
    placeholder:
      en_US: http://127.0.0.1:41540
      zh_Hans: http://127.0.0.1:41540
    help:
      en_US: >
        dsh-openai-gateway address. If Dify runs in Docker, use
        http://host.docker.internal:41540 instead of 127.0.0.1.
      zh_Hans: >
        dsh-openai-gateway 地址。Dify 以 Docker 部署时请改用
        http://host.docker.internal:41540，而非 127.0.0.1。
tools:
  - tools/chat.yaml
extra:
  python:
    source: provider/deepseek_harness.py
```

- [ ] **Step 1.7: 创建 `provider/__init__.py`（空）与 `provider/deepseek_harness.py`（骨架）**

`provider/__init__.py`：

```python
```

`provider/deepseek_harness.py`：

```python
from __future__ import annotations

from dify_plugin import ToolProvider


class DeepSeekHarnessProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        pass
```

- [ ] **Step 1.8: 创建 `tools/chat.yaml`**

```yaml
identity:
  name: chat
  author: sawyer-shi
  label:
    en_US: DeepSeek Harness Chat
    zh_Hans: DeepSeek Harness 对话
description:
  human:
    en_US: >
      Chat with a local DeepSeek Harness (DSH) agent through the dsh-openai-gateway
      OpenAI-compatible API. Each call runs in a real agent session with tools and a
      workspace. Supports session-level and user-level sticky sessions.
    zh_Hans: >
      通过 dsh-openai-gateway 的 OpenAI 兼容 API 与本地 DeepSeek Harness (DSH) Agent
      对话。每次调用都在带工具与工作区的真实 Agent 会话中执行。支持会话级与用户级粘性会话。
  llm: >
    Tool for chatting with a local DeepSeek Harness coding agent. Send a user message
    (prompt); the agent replies after running its own tools in its local workspace.
extra:
  python:
    source: tools/chat.py
parameters:
  - name: prompt
    type: string
    required: true
    label:
      en_US: Prompt
      zh_Hans: 用户消息
    human_description:
      en_US: The user message sent to the DSH agent for this turn.
      zh_Hans: 本轮发送给 DSH Agent 的用户消息；粘性会话下只需填写新消息。
    llm_description: The user message to send to the DeepSeek Harness agent for this turn.
    form: llm
  - name: model
    type: string
    required: false
    default: default
    label:
      en_US: Model
      zh_Hans: 模型
    human_description:
      en_US: 'Model name: "default", "provider/model", or a bare model name.'
      zh_Hans: '模型名："default"（跟随 DSH 默认模型）、"provider/model" 精确路由，或裸模型名。'
    form: form
  - name: session_scope
    type: select
    required: false
    default: session
    label:
      en_US: Session Scope
      zh_Hans: 会话级别
    human_description:
      en_US: >
        session: one agent per Dify conversation; user: one agent per Dify user across
        conversations; none: stateless single turn.
      zh_Hans: >
        会话级：同一 Dify 会话复用同一 Agent；用户级：同一 Dify 用户跨会话复用同一
        Agent；无状态：每次调用独立。
    form: form
    options:
      - value: session
        label:
          en_US: Session
          zh_Hans: 会话级
      - value: user
        label:
          en_US: User
          zh_Hans: 用户级
      - value: none
        label:
          en_US: Stateless
          zh_Hans: 无状态
  - name: timeout_seconds
    type: number
    required: false
    default: 300
    label:
      en_US: Timeout (seconds)
      zh_Hans: 超时（秒）
    human_description:
      en_US: Per-turn timeout in seconds. Agent turns can take minutes.
      zh_Hans: 单轮超时（秒）。Agent 单轮执行可能耗时数分钟。
    form: form
  - name: include_reasoning
    type: boolean
    required: false
    default: false
    label:
      en_US: Include Reasoning
      zh_Hans: 附带思考内容
    human_description:
      en_US: If enabled, prepend the agent's thinking as a <think> block.
      zh_Hans: 开启后在回复正文前以 &lt;think&gt; 段附带思考内容。
    form: form
```

- [ ] **Step 1.9: 创建 `tools/__init__.py`（空）、`tests/__init__.py`（空）与 `tools/chat.py`（骨架）**

`tools/chat.py`：

```python
from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class DeepSeekHarnessChatTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        yield self.create_text_message("not implemented yet")
```

- [ ] **Step 1.10: 创建结构测试 `tests/test_structure.py`**

```python
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
```

- [ ] **Step 1.11: 安装依赖并运行测试**

```powershell
uv sync
uv run pytest -v
```

Expected: `4 passed`（test_structure 的 4 个用例）

- [ ] **Step 1.12: 验证插件 Python 模块可导入**

```powershell
uv run python -m compileall main.py provider tools
uv run python -c "from provider.deepseek_harness import DeepSeekHarnessProvider; from tools.chat import DeepSeekHarnessChatTool; print('imports ok')"
```

Expected: `imports ok`

- [ ] **Step 1.13: Commit**

```powershell
git add manifest.yaml main.py pyproject.toml uv.lock .python-version conftest.py .gitignore .difyignore PRIVACY.md README.md _assets provider tools tests
git commit -m "chore: scaffold deepseek_harness_chat plugin skeleton"
```

---

### Task 2: dsh_client 纯函数（URL 规范化 / 请求构造 / SSE 解析 / 错误映射）

**Files:**
- Create: `tools/dsh_client.py`（本任务只实现纯函数部分；HTTP 客户端类在 Task 3 追加）
- Test: `tests/test_dsh_client.py`

**Interfaces:**
- Consumes: 无
- Produces（Task 3/4/5/6 依赖，签名精确如下）:
  - `DEFAULT_MAX_TOKENS: int = 8192`
  - `class DshGatewayError(Exception)`：属性 `message: str`、`status_code: int | None`、`detail: str`
  - `@dataclass ChatResult`：字段 `content: str = ""`、`reasoning: str = ""`、`session_id: str = ""`、`model: str = ""`、`tool_call_names: list[str] = field(default_factory=list)`
  - `normalize_base_url(url: str) -> str`
  - `build_headers(api_key: str, session_header: str | None, accept: str = "application/json") -> dict[str, str]`
  - `build_body(model: str, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> dict`
  - `parse_sse_lines(lines: Iterable[str]) -> ChatResult`
  - `friendly_error_message(status_code: int | None, detail: str = "") -> str`

- [ ] **Step 2.1: 写失败测试 `tests/test_dsh_client.py`**

```python
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
```

- [ ] **Step 2.2: 运行测试验证失败**

```powershell
uv run pytest tests/test_dsh_client.py -v
```

Expected: FAIL（`ModuleNotFoundError: No module named 'tools.dsh_client'`）

- [ ] **Step 2.3: 实现 `tools/dsh_client.py`（纯函数部分）**

```python
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

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
```

- [ ] **Step 2.4: 运行测试验证通过**

```powershell
uv run pytest tests/test_dsh_client.py -v
```

Expected: 全部 PASS

- [ ] **Step 2.5: Commit**

```powershell
git add tools/dsh_client.py tests/test_dsh_client.py
git commit -m "feat: add dsh gateway pure helpers (url/headers/body/sse/errors)"
```

---

### Task 3: DshGatewayClient（httpx 流式客户端）

**Files:**
- Modify: `tools/dsh_client.py`（文件末尾追加客户端类与 import）
- Test: `tests/test_dsh_client.py`（追加 `TestDshGatewayClient` 类）

**Interfaces:**
- Consumes: Task 2 的全部纯函数
- Produces（Task 4/5/6 依赖）:
  - `class DshGatewayClient`：
    - `__init__(self, base_url: str, api_key: str, timeout_seconds: float = 300.0)`
    - `chat(self, prompt: str, model: str = "default", session_header: str = "new") -> ChatResult`
    - `list_models(self) -> list[dict]`
    - 非 200 / 连接失败 / 超时均抛 `DshGatewayError`（连接失败 `status_code=None`）

- [ ] **Step 3.1: 追加失败测试（`tests/test_dsh_client.py` 末尾）**

```python
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
```

- [ ] **Step 3.2: 运行测试验证失败**

```powershell
uv run pytest tests/test_dsh_client.py::TestDshGatewayClient -v
```

Expected: FAIL（`ImportError: cannot import name 'DshGatewayClient'`）

- [ ] **Step 3.3: 在 `tools/dsh_client.py` 顶部 import 区追加，并在文件末尾追加客户端类**

顶部 import 区（合并进现有 import，保持分组）：

```python
import httpx
```

文件末尾追加：

```python
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
```

- [ ] **Step 3.4: 运行测试验证通过**

```powershell
uv run pytest tests/test_dsh_client.py -v
```

Expected: 全部 PASS（Task 2 + Task 3）

- [ ] **Step 3.5: Commit**

```powershell
git add tools/dsh_client.py tests/test_dsh_client.py
git commit -m "feat: add DshGatewayClient with streaming chat and model listing"
```

---

### Task 4: SessionManager（scope 键推导 + 映射 + 404 自动重建）

**Files:**
- Create: `tools/session_manager.py`
- Test: `tests/test_session_manager.py`

**Interfaces:**
- Consumes: Task 2/3 的 `DshGatewayError`、`ChatResult`、`DshGatewayClient`
- Produces（Task 5 依赖）:
  - `SESSION_HEADER_NEW = "new"`
  - `resolve_scope_key(scope: str, dify_session_id: str | None, dify_user_id: str | None) -> str | None`
  - `class SessionManager`：`get(key) -> str | None`、`set(key, session_id) -> None`、`drop(key) -> None`
  - `chat_with_session_retry(client, manager: SessionManager, key: str | None, prompt: str, model: str) -> tuple[ChatResult, bool]`（第二元素=是否因 404 重建重试过）

- [ ] **Step 4.1: 写失败测试 `tests/test_session_manager.py`**

```python
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

    def chat(self, prompt, model="default", session_header="new"):
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
            def chat(self, prompt, model="default", session_header="new"):
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
```

- [ ] **Step 4.2: 运行测试验证失败**

```powershell
uv run pytest tests/test_session_manager.py -v
```

Expected: FAIL（`ModuleNotFoundError: No module named 'tools.session_manager'`）

- [ ] **Step 4.3: 实现 `tools/session_manager.py`**

```python
from __future__ import annotations

import threading

from tools.dsh_client import ChatResult, DshGatewayClient, DshGatewayError

SESSION_HEADER_NEW = "new"
_VALID_SCOPES = {"session", "user", "none"}


def resolve_scope_key(
    scope: str, dify_session_id: str | None, dify_user_id: str | None
) -> str | None:
    """Map (scope, Dify runtime ids) to a sticky-session mapping key.

    Returns None for stateless behavior (scope "none", unknown scope, or no
    usable runtime id after fallbacks).
    """
    if scope not in _VALID_SCOPES:
        return None
    if scope == "user":
        if dify_user_id:
            return f"user:{dify_user_id}"
        if dify_session_id:
            return f"session:{dify_session_id}"
        return None
    if scope == "session":
        return f"session:{dify_session_id}" if dify_session_id else None
    return None


class SessionManager:
    """In-memory mapping: scope key -> dsh_session_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str | None) -> str | None:
        if not key:
            return None
        with self._lock:
            return self._sessions.get(key)

    def set(self, key: str | None, session_id: str) -> None:
        if not key or not session_id:
            return
        with self._lock:
            self._sessions[key] = session_id

    def drop(self, key: str | None) -> None:
        if not key:
            return
        with self._lock:
            self._sessions.pop(key, None)


def _is_session_not_found(error: DshGatewayError) -> bool:
    return error.status_code == 404 and "session_not_found" in error.detail


def chat_with_session_retry(
    client: DshGatewayClient,
    manager: SessionManager,
    key: str | None,
    prompt: str,
    model: str,
) -> tuple[ChatResult, bool]:
    """Call client.chat with sticky-session handling.

    Reuses the mapped session id when present, otherwise creates one. On 404
    session_not_found, drops the mapping and retries exactly once with a new
    session. Returns (ChatResult, retried_flag).
    """
    session_id = manager.get(key)
    session_header = session_id or SESSION_HEADER_NEW
    try:
        result = client.chat(prompt, model=model, session_header=session_header)
    except DshGatewayError as e:
        if session_id and _is_session_not_found(e):
            manager.drop(key)
            result = client.chat(prompt, model=model, session_header=SESSION_HEADER_NEW)
            manager.set(key, result.session_id)
            return result, True
        raise
    manager.set(key, result.session_id)
    return result, False
```

- [ ] **Step 4.4: 运行测试验证通过**

```powershell
uv run pytest tests/test_session_manager.py -v
```

Expected: 全部 PASS

- [ ] **Step 4.5: Commit**

```powershell
git add tools/session_manager.py tests/test_session_manager.py
git commit -m "feat: add session manager with scope resolution and sticky retry"
```

---

### Task 5: chat 工具编排（参数归一化 + 输出消息）

**Files:**
- Modify: `tools/chat.py`（替换骨架实现）
- Test: `tests/test_chat_tool.py`

**Interfaces:**
- Consumes: Task 2/3 `DshGatewayClient`、`DshGatewayError`；Task 4 `SessionManager`、`chat_with_session_retry`、`resolve_scope_key`
- Produces:
  - `normalize_params(tool_parameters: dict[str, Any]) -> dict`：键为 `prompt`、`model`、`session_scope`、`timeout_seconds`、`include_reasoning`
  - `SESSION_MANAGER: SessionManager`（模块级单例）
  - `class DeepSeekHarnessChatTool(Tool)`（`_invoke` 为薄封装：归一化 → client → retry → yield 文本 + JSON 消息；运行时错误 `raise Exception(e.message)`）

- [ ] **Step 5.1: 写失败测试 `tests/test_chat_tool.py`**

```python
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
```

- [ ] **Step 5.2: 运行测试验证失败**

```powershell
uv run pytest tests/test_chat_tool.py -v
```

Expected: FAIL（`ImportError: cannot import name 'normalize_params'`）

- [ ] **Step 5.3: 替换 `tools/chat.py` 全文**

```python
from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dsh_client import DshGatewayClient, DshGatewayError
from tools.session_manager import (
    SessionManager,
    chat_with_session_retry,
    resolve_scope_key,
)

SESSION_MANAGER = SessionManager()

_DEFAULT_TIMEOUT_SECONDS = 300.0
_VALID_SCOPES = {"session", "user", "none"}


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
    return {
        "prompt": prompt,
        "model": model,
        "session_scope": scope,
        "timeout_seconds": timeout_seconds,
        "include_reasoning": include_reasoning,
    }


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
        try:
            result, _retried = chat_with_session_retry(
                client, SESSION_MANAGER, key, prompt, params["model"]
            )
        except DshGatewayError as e:
            raise Exception(e.message) from e

        reply = result.content
        if params["include_reasoning"] and result.reasoning:
            reply = f"<think>\n{result.reasoning}\n</think>\n\n{reply}"

        yield self.create_text_message(reply)
        yield self.create_json_message(
            {
                "session_id": result.session_id,
                "scope": params["session_scope"],
                "reply": result.content,
                "tool_calls": len(result.tool_call_names),
                "tool_call_names": sorted(set(result.tool_call_names)),
                "model": result.model or params["model"],
            }
        )
```

- [ ] **Step 5.4: 运行测试验证通过**

```powershell
uv run pytest tests/test_chat_tool.py -v
uv run pytest -v
```

Expected: 全部 PASS

- [ ] **Step 5.5: Commit**

```powershell
git add tools/chat.py tests/test_chat_tool.py
git commit -m "feat: wire chat tool with parameters and outputs"
```

---

### Task 6: Provider 凭据校验

**Files:**
- Modify: `provider/deepseek_harness.py`（替换骨架实现）
- Test: `tests/test_provider_credentials.py`

**Interfaces:**
- Consumes: Task 3 `DshGatewayClient`、`DshGatewayError`
- Produces: `DeepSeekHarnessProvider._validate_credentials(credentials: dict) -> None`（成功返回 None；失败抛 `ToolProviderCredentialValidationError`，消息为友好英文提示）

- [ ] **Step 6.1: 写失败测试 `tests/test_provider_credentials.py`**

```python
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
```

- [ ] **Step 6.2: 运行测试验证失败**

```powershell
uv run pytest tests/test_provider_credentials.py -v
```

Expected: `test_valid_credentials_returns_none` FAIL（当前骨架直接返回 None 但没发请求？注意：骨架 `pass` 会让前两个用例中的 `test_missing_fields_rejected_without_http_call` FAIL——以它为红条标准）

- [ ] **Step 6.3: 替换 `provider/deepseek_harness.py` 全文**

```python
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
```

- [ ] **Step 6.4: 运行测试验证通过**

```powershell
uv run pytest tests/test_provider_credentials.py -v
uv run pytest -v
```

Expected: 全部 PASS

- [ ] **Step 6.5: Commit**

```powershell
git add provider/deepseek_harness.py tests/test_provider_credentials.py
git commit -m "feat: add provider credential validation"
```

---

### Task 7: README、发布工作流与打包验证

**Files:**
- Modify: `README.md`（替换占位全文）
- Create: `.github/workflows/plugin-publish.yml`

**Interfaces:**
- Consumes: Task 1-6 的全部产物
- Produces: 可发布的仓库（release 时自动打包 `.difypkg` 并向 langgenius/dify-plugins 提 PR）

- [ ] **Step 7.1: 替换 `README.md` 全文**

```markdown
# deepseek_harness_chat

Dify 工具插件：通过 [dsh-openai-gateway](https://github.com/backrooms-yrc/dsh-openai-gateway)
的 OpenAI 兼容 API，与本地 [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness)
Agent 对话。每次调用都在带工具与工作区的真实 Agent 会话中执行。

## 前置条件

1. 安装并运行 DeepSeek Harness（DSH）
2. 安装 dsh-openai-gateway 插件并重启 DSH：

   ```bash
   dsh plugin --profile <profile> add github:backrooms-yrc/dsh-openai-gateway
   ```

3. 获取网关地址与密钥：

   ```bash
   cat $DSH_HOME/openai-gateway/state.json      # {"host": "127.0.0.1", "port": 41540, ...}
   cat $DSH_HOME/openai-gateway/api-keys.json   # {"keys": ["sk-dsh-..."]}
   ```

## 在 Dify 中安装

1. 从 Release 下载 `deepseek_harness_chat-<version>.difypkg`，或在 Dify「插件 → 安装插件 → 通过本地文件安装」上传
2. 配置凭据：
   - **API 密钥**：`sk-dsh-...`（见上）
   - **网关地址**：默认 `http://127.0.0.1:41540`

## Docker 网络注意事项

Dify 以 Docker 部署时，容器内的 `127.0.0.1` 不是宿主机。请将网关地址改为：

```
http://host.docker.internal:41540
```

（Linux 需在 `docker-compose` 中为 Dify 容器配置 `extra_hosts: ["host.docker.internal:host-gateway"]`，或改用宿主机内网 IP。）

## 使用

在 Chatflow / Workflow / Agent 应用中添加「DeepSeek Harness Chat」工具节点：

| 参数 | 说明 |
|---|---|
| 用户消息 | 本轮发给 Agent 的内容；粘性会话下只需新消息 |
| 模型 | `default`（跟随 DSH 默认）、`provider/model`（如 `deepseek-official/deepseek-v4-flash`）或裸模型名 |
| 会话级别 | 见下 |
| 超时（秒） | 单轮超时，默认 300；Agent 单轮可能耗时数分钟 |
| 附带思考内容 | 开启后在回复前附加 `<think>` 段 |

### 会话级别

- **会话级（默认）**：同一 Dify 会话复用同一个 DSH Agent，上下文与工作区跨节点连续
- **用户级**：同一 Dify 用户跨会话、跨应用复用同一个 DSH Agent（个人专属工作区）
- **无状态**：每次调用独立，回合结束即销毁

会话由插件自动管理（新建 / 复用 / 网关逐出后自动重建）。工具的 JSON 输出含
`session_id`、`tool_calls`、`tool_call_names`、`model` 等字段，可在工作流中引用。

## 已知限制

- 会话映射保存在插件进程内存中，插件重启后自动新建会话（网关侧会话 LRU 上限默认 16）
- Agent 内部工具调用只返回名称与次数，不返回执行结果
- `include_reasoning` 仅在模型输出思考内容（`reasoning_content`）时有效

## 开发

```bash
uv sync
uv run pytest -v
```

打包：`dify plugin package . -o deepseek_harness_chat-0.0.1.difypkg`（需
[dify-plugin-daemon](https://github.com/langgenius/dify-plugin-daemon) CLI），或直接发
Release 由 GitHub Actions 自动打包。

## License

MIT
```

- [ ] **Step 7.2: 创建 `.github/workflows/plugin-publish.yml`**

```yaml
name: Plugin Publish Workflow

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download CLI tool
        run: |
          mkdir -p $RUNNER_TEMP/bin
          wget https://github.com/langgenius/dify-plugin-daemon/releases/latest/download/dify-plugin-linux-amd64
          mv dify-plugin-linux-amd64 $RUNNER_TEMP/bin/dify-plugin
          chmod +x $RUNNER_TEMP/bin/dify-plugin

      - name: Get basic info from manifest
        id: get_basic_info
        run: |
          PLUGIN_NAME=$(grep "^name:" manifest.yaml | cut -d ' ' -f2)
          echo "plugin_name=$PLUGIN_NAME" >> $GITHUB_OUTPUT
          VERSION=$(grep "^version:" manifest.yaml | cut -d ' ' -f2)
          echo "version=$VERSION" >> $GITHUB_OUTPUT
          AUTHOR=$(grep "^author:" manifest.yaml | cut -d ' ' -f2)
          echo "author=$AUTHOR" >> $GITHUB_OUTPUT

      - name: Package Plugin
        id: package
        run: |
          PACKAGE_NAME="${{ steps.get_basic_info.outputs.plugin_name }}-${{ steps.get_basic_info.outputs.version }}.difypkg"
          $RUNNER_TEMP/bin/dify-plugin plugin package . -o "$PACKAGE_NAME"
          echo "package_name=$PACKAGE_NAME" >> $GITHUB_OUTPUT

      - name: Upload package to release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release upload "${{ github.event.release.tag_name }}" \
            "${{ steps.package.outputs.package_name }}" --clobber

      - name: Checkout marketplace repo
        uses: actions/checkout@v4
        with:
          repository: ${{ steps.get_basic_info.outputs.author }}/dify-plugins
          path: dify-plugins
          token: ${{ secrets.PLUGIN_ACTION }}
          fetch-depth: 1
          persist-credentials: true

      - name: Prepare and create PR
        env:
          GH_TOKEN: ${{ secrets.PLUGIN_ACTION }}
        run: |
          PACKAGE_NAME="${{ steps.package.outputs.package_name }}"
          mkdir -p "dify-plugins/${{ steps.get_basic_info.outputs.author }}/${{ steps.get_basic_info.outputs.plugin_name }}"
          mv "$PACKAGE_NAME" "dify-plugins/${{ steps.get_basic_info.outputs.author }}/${{ steps.get_basic_info.outputs.plugin_name }}/"
          cd dify-plugins
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          BRANCH_NAME="bump-${{ steps.get_basic_info.outputs.plugin_name }}-plugin-${{ steps.get_basic_info.outputs.version }}"
          git checkout -b "$BRANCH_NAME"
          git add .
          git commit -m "bump ${{ steps.get_basic_info.outputs.plugin_name }} plugin to version ${{ steps.get_basic_info.outputs.version }}"
          git push -u origin "$BRANCH_NAME" --force
          gh pr create \
            --repo langgenius/dify-plugins \
            --head "${{ steps.get_basic_info.outputs.author }}:${{ steps.get_basic_info.outputs.plugin_name }}-${{ steps.get_basic_info.outputs.version }}" \
            --base main \
            --title "bump ${{ steps.get_basic_info.outputs.plugin_name }} plugin to version ${{ steps.get_basic_info.outputs.version }}" \
            --body "bump ${{ steps.get_basic_info.outputs.plugin_name }} plugin package to version ${{ steps.get_basic_info.outputs.version }}" || echo "PR already exists or creation skipped."
```

- [ ] **Step 7.3: 全量测试 + 编译验证**

```powershell
uv run pytest -v
uv run python -m compileall main.py provider tools tests
```

Expected: 全部 PASS

- [ ] **Step 7.4: 本地打包验证（CLI 可选）**

```powershell
dify plugin package . -o deepseek_harness_chat-0.0.1.difypkg
```

若本机无 CLI：跳过（Release 流程会自动打包）；若报图标缺失，把 `_assets/icon.svg`、`_assets/icon-dark.svg` 复制到根目录后重试。

- [ ] **Step 7.5: Commit**

```powershell
git add README.md .github/workflows/plugin-publish.yml
git commit -m "docs: add README and plugin publish workflow"
```

---

## Self-Review 记录

- **Spec 覆盖**：§2 API 契约→Task 2/3；§4 manifest→Task 1；§5 凭据→Task 1/6；§6 工具参数输出→Task 1/5；§7 会话管理→Task 4；§8 客户端→Task 2/3；§9 README→Task 7；§10 测试→各任务 TDD + Task 7 全量；§11 开放项 A（session_id 位置：帧字段+响应头双兜底，Task 3 已实现）、B（scope 键粒度：降级规则 Task 4 覆盖）
- **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码
- **类型一致性**：`DshGatewayError(message, status_code, detail)`、`ChatResult` 字段、`chat_with_session_retry` 返回 `tuple[ChatResult, bool]`、`normalize_params` 返回键集在 Task 2/4/5/6 间一致
