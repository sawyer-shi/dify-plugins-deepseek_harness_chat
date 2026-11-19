# deepseek_harness_chat

A Dify tool plugin that chats with a local [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness) agent through the [dsh-openai-gateway](https://github.com/sawyer-shi/dsh-openai-gateway) OpenAI-compatible API. Every call runs inside a **real agent session with tools and a workspace** — the agent can execute code, browse, and produce deliverable files that come back into the conversation as downloadable attachments.

> 简体中文文档：[readme/README_zh_Hans.md](readme/README_zh_Hans.md)

## Features

- **Real agent, not a chat completion** — each turn is executed by a DSH agent with tools, shell access and a workspace
- **Sticky sessions** — session-level (per Dify conversation), user-level (per Dify user across apps), or stateless
- **File in** — attach files (documents, spreadsheets, images…); they are uploaded into the agent workspace and the agent is instructed to read them
- **File out** — files generated during the turn (Excel / CSV / PDF / docx / images / zip…) are returned as conversation attachments
- **Truncation control** — independent caps for Dify-side text (`max_text_chars`) and DSH-side tokens (`max_tokens`)

## Prerequisites

1. Install and run [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (dsh 0.2.x), logged in with your DeepSeek account.
2. Install the gateway plugin into DSH and restart DSH:

   ```bash
   dsh plugin --profile web add github:sawyer-shi/dsh-openai-gateway#v0.3.2
   ```

   The gateway ships with `agentPreset: ptc` + `permissionPreset: workspace-write` by default, so the agent can run code and write files out of the box.

3. Get the gateway address and API key:

   ```bash
   cat $DSH_HOME/openai-gateway/state.json      # {"host": "127.0.0.1", "port": 41540, ...}
   cat $DSH_HOME/openai-gateway/api-keys.json   # {"keys": ["sk-dsh-..."]}
   ```

## Install in Dify

1. Download `deepseek_harness_chat-<version>.difypkg` from Releases, or in Dify go to **Plugins → Install plugin → Install via local package file** and upload it.
2. Configure credentials:
   - **API Key**: `sk-dsh-...` from `api-keys.json`
   - **Gateway Base URL**: default `http://127.0.0.1:41540`

### Network topology (Base URL)

| Topology | Base URL | Extra requirements |
|---|---|---|
| Dify (Docker) and DSH on the same host | `http://host.docker.internal:41540` | none |
| Dify and DSH on different hosts | `http://<DSH-host-LAN-IP>:41540` | set gateway `host: 0.0.0.0` in its patch config and open port 41540 in the firewall |

Docker note: `127.0.0.1` inside a container is not the host machine. On Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` to the Dify containers in `docker-compose`, or use the host's LAN IP directly.

DSH must be running (desktop app started) — the gateway is a DSH plugin and lives in its process. Each DSH machine generates its own API key.

## Usage

Add the **DeepSeek Harness Chat** tool node in a Chatflow / Workflow / Agent app.

| Parameter | Default | Description |
|---|---|---|
| Prompt | — | The user message for this turn. With sticky sessions, send only the new message. |
| Attached Files | — | Files uploaded with the message; uploaded to the agent workspace first, then the agent is told to read them. |
| Model | `default` | `default` (follow DSH default), `provider/model` (e.g. `deepseek-official/deepseek-v4-flash`), or a bare model name. |
| Session Scope | `session` | `session` / `user` / `none` — see below. |
| Timeout (seconds) | `300` | Per-turn timeout; agent turns can take minutes. |
| Include Reasoning | `false` | Prepend the agent's thinking as a `<think>` block. |
| Return Generated Files | `true` | Return files newly created in the workspace during this turn as attachments. |
| Max Files Per Turn | `5` | Upper limit (1–10) on returned files. |
| Max Reply Characters | `6000` | Cap on the text reply returned to Dify; `0` = unlimited. Long reports can exhaust the Dify app's output tokens and get truncated — files are unaffected. |
| Max Output Tokens (DSH turn) | `32768` | Output token cap passed to the DSH agent. Too small (e.g. 8192) truncates long turns mid-answer; DSH clamps to model capacity; `0` = DSH default. |
| File Extensions Filter | *(empty)* | Empty: only deliverable types (xlsx/xls/csv/pdf/docx/pptx/txt/md/images/html/json/zip), intermediate scripts like `.py` are excluded. `*`: every new file. Or a comma-separated whitelist, e.g. `xlsx,csv,pdf`. |

### Session scopes

- **Session** (default): one DSH agent per Dify conversation — context and workspace persist across nodes.
- **User**: one DSH agent per Dify user across conversations and apps (a personal workspace).
- **Stateless**: every call is independent; the session is destroyed after the turn.

Sessions are managed automatically by the plugin (create / reuse / recreate after gateway eviction).

### Output

The tool yields one text message (the reply), zero or more file attachments, and a JSON message with fields for downstream workflow references: `session_id`, `scope`, `reply_chars`, `reply_preview`, `reply_truncated`, `tool_calls`, `tool_call_names`, `model`.

## Known limitations

- Session mapping lives in plugin process memory; after a plugin restart sessions are recreated (gateway sticky-session LRU cap is 16 by default).
- Agent-internal tool calls are returned as names/counts only, not results.
- `Include Reasoning` only takes effect when the model emits `reasoning_content`.

## Development

```bash
uv sync
uv run pytest -v
```

Package: `dify plugin package . -o deepseek_harness_chat-<version>.difypkg` (requires the [dify-plugin-daemon](https://github.com/langgenius/dify-plugin-daemon) CLI), or cut a GitHub Release and let GitHub Actions package it.

## License

MIT
