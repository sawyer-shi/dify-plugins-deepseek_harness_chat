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
