# DeepSeek Harness Chat — Dify 插件设计文档

- 日期：2026-11-18
- 插件名：`deepseek_harness_chat`
- 形态：Tool 插件（工具供应商）
- 目标 Dify 规范：最新插件规范（`dify_plugin>=0.9.0,<0.11.0`，manifest `resource`/`plugins` 段，pyproject/uv，Python 3.12）
- 参考项目：`sawyer-shi/dify-plugins-hermes_agent_chat`（无法访问，设计已经用户逐项确认）

## 1. 背景与目标

[DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness) 是本地编码 Agent 运行时。社区插件 [dsh-openai-gateway](https://github.com/backrooms-yrc/dsh-openai-gateway)（backrooms-yrc 版）把 DSH 暴露为 OpenAI 兼容 API，默认监听 `127.0.0.1:41540`，**每次 API 调用背后是一个带工具、带工作区的真实 DSH Agent 会话**。

目标：做一个 Dify 工具插件，让 Dify 工作流 / Agent 应用中的节点能与本地 DSH Agent 对话，并支持：

1. 会话级粘性会话（同一 Dify 会话复用同一 Agent）
2. 用户级粘性会话（同一 Dify 用户跨会话/跨应用复用同一 Agent）
3. 无状态单轮调用

## 2. 依赖契约：dsh-openai-gateway API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 免鉴权探活 |
| GET | `/v1/models`、`/v1/models/:id` | Bearer 鉴权；模型名为 `provider/model` |
| POST | `/v1/chat/completions` | Bearer 鉴权；`stream` 真/假均可 |

关键行为：

- **粘性会话**：请求头 `X-DSH-Session: new` 新建常驻会话；`X-DSH-Session: <id>` 复用会话（body 扩展字段 `dsh_session` 亦可）。响应携带 `dsh_session_id`。
- **模型名**：`default`（跟随 DSH 默认模型）/ `provider/model` 精确路由 / 裸模型名自动匹配。
- **流式**：标准 SSE（`data: {...}` 帧、`[DONE]` 收尾）；思考内容以 `delta.reasoning_content`（DeepSeek 风格）下发；工具调用以 SSE 注释帧 `: dsh tool-call <name>` 呈现（不投影为 OpenAI tool_calls）。
- **错误**：`401 invalid_api_key` / `404 model_not_found` / `404 session_not_found`（会话被 LRU 逐出或 id 错误）/ `504 timeout`（超过网关 `timeoutSeconds`，默认 300s）。
- **网关限制**：粘性会话簿记 LRU 上限默认 16；无状态模式 `messages` 全量拼接。

## 3. 目录结构（符合最新插件规范）

```
deepseek_harness_chat/                # 仓库根目录 = 插件目录
├── manifest.yaml                     # 见 §4
├── main.py                           # Plugin(DifyPluginEnv()) 入口
├── pyproject.toml                    # uv；dify_plugin + httpx
├── uv.lock                           # uv 生成并提交（官方惯例）
├── conftest.py                       # 空；使 pytest 将根目录加入 sys.path
├── .python-version                   # 3.12
├── .difyignore / .gitignore
├── README.md                         # 使用说明（含 Docker 网络注意事项）
├── PRIVACY.md                        # 隐私声明（marketplace 要求）
├── _assets/
│   ├── icon.svg                      # 插件图标
│   └── icon-dark.svg                 # 暗色主题图标
├── .github/workflows/plugin-publish.yml   # release → 打包 → 提 PR 到 marketplace
├── provider/
│   ├── __init__.py
│   ├── deepseek_harness.py           # ToolProvider + _validate_credentials
│   └── deepseek_harness.yaml         # 供应商凭据表单
├── tools/
│   ├── __init__.py
│   ├── chat.py                       # 工具实现
│   ├── chat.yaml                     # 工具定义（identity/parameters/extra）
│   ├── dsh_client.py                 # 网关 HTTP/SSE 客户端（纯逻辑，可单测）
│   └── session_manager.py            # scope 键 → dsh_session_id 映射（纯逻辑，可单测）
└── tests/
    ├── __init__.py
    ├── test_dsh_client.py            # 纯函数 + HTTP 客户端（respx mock）
    ├── test_session_manager.py
    ├── test_chat_tool.py
    └── test_provider_credentials.py
```

## 4. manifest.yaml（字段级规范）

```yaml
version: 0.0.1                       # 插件版本
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
created_at: "2026-11-18T00:00:00.000000000Z"
icon: icon.svg
resource:
  memory: 268435456                  # 256 MiB
  permission:
    tool:
      enabled: true
plugins:
  tools:
    - provider/deepseek_harness.yaml
meta:
  version: 0.0.1                     # manifest 规范版本
  arch:
    - amd64
    - arm64
  runner:
    language: python
    version: "3.12"
    entrypoint: main
tags:
  - productivity
  - utilities
privacy: PRIVACY.md
repo: https://github.com/sawyer-shi/dify-plugins-deepseek_harness_chat
verified: false
```

pyproject.toml 依赖：`dify_plugin>=0.9.0,<0.11.0`、`httpx>=0.28.1`；dev 组：`pytest`、`respx`（httpx mock）。

## 5. 供应商凭据（provider/deepseek_harness.yaml）

| 变量 | 类型 | 必填 | 默认/说明 |
|---|---|---|---|
| `api_key` | secret-input | 是 | `sk-dsh-...`，来自 `$DSH_HOME/openai-gateway/api-keys.json` |
| `base_url` | text-input | 是 | 默认 `http://127.0.0.1:41540`；帮助文本注明：Dify 以 Docker 部署时改用 `http://host.docker.internal:41540` |

**凭据校验**：`GET {base_url}/v1/models`（同时验证连通性与密钥）。连接被拒 → 提示「无法连接网关，请确认 DSH 与 dsh-openai-gateway 已启动且地址正确（Docker 部署用 host.docker.internal）」；401 → 「API Key 无效，请对照 $DSH_HOME/openai-gateway/api-keys.json」。

## 6. 工具定义（tools/chat.yaml）

- name: `chat`；label：`DeepSeek Harness Chat` / `DeepSeek Harness 对话`
- identity：author 同 manifest，name `chat`

**参数**：

| 变量 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `prompt` | string（paragraph） | 是 | — | 本轮用户消息；粘性会话下只发新消息即可 |
| `model` | string | 否 | `default` | `default` / `provider/model` / 裸模型名 |
| `session_scope` | select | 否 | `session` | `session`（会话级）/ `user`（用户级）/ `none`（无状态） |
| `timeout_seconds` | number | 否 | `300` | Agent 单轮可能很长；上限受网关 `timeoutSeconds` 约束 |
| `include_reasoning` | boolean | 否 | `false` | 为真时回复正文前以 `<think>...</think>` 附带思考内容 |

**输出**（`_invoke` yield 两条消息）：

1. 文本消息：Agent 回复正文（`include_reasoning` 时含 `<think>` 段）
2. JSON 消息：`{"session_id", "scope", "reply", "tool_calls", "tool_call_names", "model"}`

- `session_id`：本轮实际使用的 DSH 会话 id（`none` 时为空字符串），工作流可引用
- `tool_calls`：本轮 Agent 内部工具调用次数（解析 SSE 注释帧）
- `tool_call_names`：去重后的工具名列表

## 7. 会话管理（tools/session_manager.py）

**映射**：`scope键 → dsh_session_id`，进程内 dict + `threading.Lock`（插件运行于单进程同步生成器 `_invoke`）。

**scope 键推导**（`Tool.runtime` 提供 `session_id`、`user_id`，均为 `Optional[str]`）：

| session_scope | 键 | 降级规则 |
|---|---|---|
| `session` | `f"session:{runtime.session_id}"` | `session_id` 为空 → 视为 `none` |
| `user` | `f"user:{runtime.user_id}"` | `user_id` 为空 → 降级 `session:` 键；仍为空 → `none` |
| `none` | — | 每次新建临时会话，不做映射 |

**流程**：

1. 取映射命中 → 请求头 `X-DSH-Session: <id>`；未命中 → `X-DSH-Session: new`
2. 从响应解析 `dsh_session_id`（见 §8 解析规则），若本次为新建则写入映射
3. 收到 `404 session_not_found`（网关 LRU 逐出/DSH 重启）→ 删除该映射项，以 `new` 重试**一次**；重试仍失败则报错
4. 映射不设上限（网关侧 LRU 16 已是实际上限）；插件重启映射清空，属可接受行为（README 说明）

## 8. 网关客户端（tools/dsh_client.py）

- `httpx.Client` 同步调用（工具 `_invoke` 为同步生成器），`POST {base_url}/v1/chat/completions`，`stream: true`（**内部流式**：网关明确警告非流式长任务会命中任何读超时）
- 请求头：`Authorization: Bearer <api_key>`、`X-DSH-Session: ...`、`Content-Type: application/json`
- 请求体：`{"model": model, "messages": [{"role": "user", "content": prompt}], "stream": true, "max_tokens": 8192}`（`max_tokens` 为网关单轮输出上限，取宽松默认值）
- **SSE 解析**：逐行读取；`data: [DONE]` 结束；`data: {...}` 解析 JSON：
  - `choices[0].delta.content` → 追加正文
  - `choices[0].delta.reasoning_content` → 追加思考
  - 帧顶层 `dsh_session_id`（若存在）→ 记录
  - `: dsh tool-call <name>` 注释行 → 工具调用计数
- **dsh_session_id 兜底**：帧内未出现时读响应头 `X-DSH-Session`（开放验证项 A，见 §11）
- **超时**：httpx `timeout=timeout_seconds`（连接/读/写同值）；超时或网关 504 → 报错提示调大 `timeout_seconds` 或精简任务

**base_url 规范化**：去除尾部 `/`；若以 `/v1` 结尾则去除（用户误填兼容）。客户端拼接 `{base_url}/v1/chat/completions` 与 `{base_url}/v1/models`。

**错误映射**（运行时错误直接 `raise Exception`（官方工具插件惯例，daemon 会包装展示）；凭据校验失败抛 `dify_plugin.errors.tool.ToolProviderCredentialValidationError`。消息含原因与处置建议）：

| 网关响应 | 工具报错消息（要点） |
|---|---|
| 连接被拒 | DSH/网关未启动或地址错误；Docker 部署用 host.docker.internal |
| 401 | API Key 无效 |
| 404 model_not_found | 模型名无效，建议 `default` 或 GET /v1/models 查询 |
| 404 session_not_found | 重试一次后仍失败 → 会话已失效，请重试以新建会话 |
| 504 / 读超时 | Agent 单轮超时，调大 timeout_seconds |

## 9. README 要点

- 前置条件：安装 DSH + dsh-openai-gateway（backrooms-yrc 版），获取端口（`state.json`）与密钥（`api-keys.json`）
- Dify 侧安装 `.difypkg`、配置凭据、在 Chatflow/Workflow/Agent 中使用
- 会话级别说明（session/user/none 的语义与适用场景）
- Docker 网络注意事项（`host.docker.internal`，Linux 需 `extra_hosts` 或 `--network=host`）
- 已知限制：映射重启丢失、网关 LRU 16、工具调用仅计数不返回结果

## 10. 测试策略

pytest + respx（mock httpx，不打真实网关）：

1. **SSE 解析**：正常流、含 reasoning_content、含注释帧、`[DONE]`、残缺 JSON 行（应跳过不崩）
2. **会话管理**：新建/复用/`user` 降级 `session`、双空降级 `none`、404 后删映射重试、重试成功
3. **请求构造**：头（Bearer、X-DSH-Session new/id）、体（model/stream/max_tokens）
4. **错误映射**：各错误码 → 对应异常消息
5. **凭据校验**：`/v1/models` 成功/401/连接拒绝

**人工冒烟**（交付前，需真实网关环境）：`default` 模型单轮、粘性会话两轮（第二轮能记住第一轮暗号）、`user` 级跨会话连续性。

## 11. 开放验证项（实现期确认）

- **A. 流式响应中 `dsh_session_id` 的确切位置**（首帧/尾帧/响应头/均无）：按 §8 多处 best-effort 解析，实测后若有固定位置可简化
- **B. Dify 各应用类型（Chatflow/Workflow/Agent）下 `runtime.session_id` 的粒度与是否恒有值**：以实测为准，降级规则已覆盖空值场景

## 12. 交付物

- 本仓库（插件源码 + tests + README + spec/plan 文档）
- `.difypkg` 打包产物（`dify plugin package`）
