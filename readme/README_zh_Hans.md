# deepseek_harness_chat

Dify 工具插件：通过 [dsh-openai-gateway](https://github.com/sawyer-shi/dsh-openai-gateway)
的 OpenAI 兼容 API，与本地 [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness)
Agent 对话。每次调用都在**带工具与工作区的真实 Agent 会话**中执行——Agent 可以运行代码、
联网检索，并把产出的交付文件直接返回到对话中成为可下载附件。

> English documentation: [README.md](../README.md)

## 版本信息

- **当前版本**: v0.0.1
- **发布日期**: 2026-11-19
- **兼容性**: Dify 插件框架
- **Python 版本**: 3.12

### 版本历史
- **v0.0.1** (2026-11-19): 首个发布版本
  - 通过 dsh-openai-gateway 与本地 DeepSeek Harness Agent 对话，每次调用都在带工具与工作区的真实 Agent 会话中执行
  - 粘性会话：会话级、用户级、无状态三种模式，会话自动管理
  - **文件输入**：随消息上传文件，先进入 Agent 工作区再执行任务
  - **文件输出**：本轮生成的文件（Excel / CSV / PDF / docx / 图片 / zip…）直接作为附件返回对话，支持扩展名过滤与每轮文件数上限
  - **截断控制**：Dify 侧回复文本（`max_text_chars`）与 DSH 单轮输出（`max_tokens`）独立设限

## 功能特性

- **真实 Agent，而非普通补全**：每轮由带工具、Shell 与工作区的 DSH Agent 执行
- **粘性会话**：会话级（同一 Dify 会话）、用户级（同一用户跨应用）、无状态三档可选
- **文件输入**：随消息上传文件（文档、表格、图片…），先进入 Agent 工作区，再让 Agent 读取后完成任务
- **文件输出**：本轮生成的文件（Excel / CSV / PDF / docx / 图片 / zip…）直接作为附件返回对话
- **截断控制**：Dify 侧文本（`max_text_chars`）与 DSH 侧 token（`max_tokens`）独立设上限

## 前置条件

1. 安装并运行 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（dsh 0.2.x），登录 DeepSeek 账号。
2. 安装网关插件到 DSH 并重启 DSH：

   ```bash
   dsh plugin --profile web add github:sawyer-shi/dsh-openai-gateway#v0.3.2
   ```

   网关自带默认 `agentPreset: ptc` + `permissionPreset: workspace-write`，安装后 Agent 即可直接执行代码、写文件，无需额外配置。

3. 获取网关地址与密钥：

   ```bash
   cat $DSH_HOME/openai-gateway/state.json      # {"host": "127.0.0.1", "port": 41540, ...}
   cat $DSH_HOME/openai-gateway/api-keys.json   # {"keys": ["sk-dsh-..."]}
   ```

## 在 Dify 中安装

1. 从 Release 下载 `deepseek_harness_chat-<version>.difypkg`，或在 Dify「插件 → 安装插件 → 通过本地文件安装」上传。
2. 配置凭据：
   - **API 密钥**：`sk-dsh-...`（见 `api-keys.json`）
   - **网关地址**：默认 `http://127.0.0.1:41540`

### 网络拓扑与网关地址（Base URL）

| 拓扑 | Base URL | 额外要求 |
|---|---|---|
| Dify（Docker）与 DSH 同机 | `http://host.docker.internal:41540` | 无 |
| Dify 与 DSH 跨机 | `http://<DSH 机器局域网 IP>:41540` | 网关 patch 配置中 `host` 改为 `0.0.0.0`，防火墙放行 41540 |

Docker 注意：容器内的 `127.0.0.1` 不是宿主机。Linux 需在 `docker-compose` 中为 Dify 容器配置
`extra_hosts: ["host.docker.internal:host-gateway"]`，或直接改用宿主机内网 IP。

DSH 必须处于运行状态（桌面版已启动）——网关是 DSH 的插件，随其进程存活。每台 DSH 机器各自独立生成 API key。

## 使用

在 Chatflow / Workflow / Agent 应用中添加「DeepSeek Harness 对话」工具节点：

| 参数 | 默认值 | 说明 |
|---|---|---|
| 用户消息（prompt） | — | 本轮发给 Agent 的内容；粘性会话下只需填写新消息 |
| 随消息上传的文件（files） | — | 随消息上传的文件，先上传到 Agent 工作区，并提示 Agent 读取后再完成任务 |
| 模型（model） | `default` | `default`（跟随 DSH 默认）、`provider/model` 精确路由（如 `deepseek-official/deepseek-v4-flash`）或裸模型名 |
| 会话级别（session_scope） | `session` | `session` / `user` / `none`，见下 |
| 超时（秒）（timeout_seconds） | `300` | 单轮超时；Agent 单轮执行可能耗时数分钟 |
| 附带思考内容（include_reasoning） | `false` | 开启后在回复正文前以 `<think>` 段附带思考内容 |
| 返回生成的文件（return_files） | `true` | 返回本轮在 Agent 工作区新生成的文件作为附件 |
| 每轮最多返回文件数（max_files） | `5` | 返回文件数量上限（1-10） |
| 回复文本上限（max_text_chars） | `6000` | 返回给 Dify 的文本回复最大字符数，`0` 不限制。过长报告会撑爆 Dify 应用输出 token 导致截断；文件不受影响 |
| DSH 单轮输出上限（max_tokens） | `32768` | 传给 DSH Agent 的输出 token 上限。过小（如 8192）会导致长回复中途截断；DSH 会按模型容量自动钳制；`0` 跟随 DSH 默认 |
| 返回文件的扩展名过滤（file_extensions） | 空 | 留空：只返回交付类文件（xlsx/xls/csv/pdf/docx/pptx/txt/md/图片/html/json/zip），中间脚本（.py 等）不返回；`*` 返回全部新文件；或填逗号分隔白名单如 `xlsx,csv,pdf` |

### 会话级别

- **会话级（默认）**：同一 Dify 会话复用同一个 DSH Agent，上下文与工作区跨节点连续
- **用户级**：同一 Dify 用户跨会话、跨应用复用同一个 DSH Agent（个人专属工作区）
- **无状态**：每次调用独立，回合结束即销毁

会话由插件自动管理（新建 / 复用 / 网关逐出后自动重建）。

### 输出结构

工具产出：一条文本消息（回复正文）+ 零或多条文件附件 + 一条 JSON 消息，JSON 含
`session_id`、`scope`、`reply_chars`、`reply_preview`、`reply_truncated`、`tool_calls`、
`tool_call_names`、`model` 等字段，可在后续工作流节点中引用。

## 已知限制

- 会话映射保存在插件进程内存中，插件重启后自动新建会话（网关侧会话 LRU 上限默认 16）
- Agent 内部工具调用只返回名称与次数，不返回执行结果
- `include_reasoning` 仅在模型输出思考内容（`reasoning_content`）时有效

## 开发

```bash
uv sync
uv run pytest -v
```

打包：`dify plugin package . -o deepseek_harness_chat-<version>.difypkg`（需
[dify-plugin-daemon](https://github.com/langgenius/dify-plugin-daemon) CLI），或直接发
Release 由 GitHub Actions 自动打包。

## License

MIT
