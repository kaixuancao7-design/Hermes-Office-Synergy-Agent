# Hermes Office Synergy Agent

基于 Python、FastAPI、LangChain 与 LangGraph 的办公协同 Agent 后端，提供 IM 消息接入、技能执行、工具推理、文档分析及交互式 PPT 生成。

当前仓库没有独立前端。最新全量回归为 **103 项测试通过、0 失败**，另有 20 条弃用警告；这是 2026-10-21 的本机回归结果，尚未验证真实模型、飞书端到端或全新环境安装。

- [运行与架构说明](docs/运行与架构说明.md)：模块入口、探针、重投处理与能力边界。
- [修复验证记录](docs/修复验证记录.md)：R1–R8 修改及逐项测试结果。
- [修复优先级与实施计划](docs/修复优先级与实施计划.md)：问题依据和验收标准。
- [HERMES.md](HERMES.md)：开发原则与设计目标；其中尚未实现的目标不代表已上线能力。

## 核心能力

| 能力 | 当前实现 |
| --- | --- |
| 消息处理 | HTTP API、飞书 WebSocket、IM 适配器；技能预匹配后分流到 PPT、ReAct 或直接处理 |
| 技能执行 | Tier 1 摘要匹配、Tier 2 完整技能按需加载、Tier 3 参考资料延迟读取，提供执行披露与接近匹配建议 |
| 技能学习 | 从执行轨迹或用户纠正生成草稿，支持结构验证、管理员审核、版本历史、修补提案与周期维护 |
| PPT | 规划、用户确认、生成和质检；检查点支持继续与取消，发送到 IM 需调用相应工具并配置平台凭据 |
| 记忆与检索 | 默认 `simple` 使用 SQLite 持久化并按用户隔离；基础文档检索为内存关键词索引，可接入高级检索管道 |
| 模型路由 | 注册类型包括 `ollama`、`openai`、`claude`、`zhipu`、`moonshot`、`deepseek`、`multi` |
| 工具与权限 | 参数校验、路径约束、代码执行限制、RBAC、显式危险工具授权及持久化审计哈希链 |
| MCP | 作为客户端发现和调用外部工具；作为服务端向外部应用暴露工具、资源及提示模板 |
| 请求恢复 | 持久化认领、结果复用与失败核查；避免执行结果不明时盲目重跑消息管道 |

WebSearchTool 当前返回明确标注的 Mock 数据，不能用于实时搜索。其他 IM 平台的适配或配置存在，不代表均已完成生产验收；向量持久化、数据加密、备份和告警等能力也不能仅根据设计文档视为已部署。

## 快速开始

### 安装依赖

本次验证环境为 Windows / Python 3.12.7。可在独立虚拟环境中安装：

```bash
python -m venv .venv
```

激活环境：

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS（本次未验证）
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt -c constraints-py312.txt
```

[constraints-py312.txt](constraints-py312.txt) 记录本次回归环境的直接依赖及关键间接依赖版本，尚未验证全新环境安装，也不是覆盖全部间接依赖的完整锁文件。

### 配置

复制 [.env.example](.env.example) 为 `.env`，填写需要启用的服务。以下为本地 Ollama 与 HTTP 消息接口的配置示例：

```env
HOST=127.0.0.1
PORT=3000
LOG_LEVEL=INFO

MODEL_ROUTER_TYPE=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen3.5:9b
MEMORY_STORE_TYPE=simple
SKILL_MANAGER_TYPE=hybrid
TOOL_EXECUTOR_TYPE=sandboxed
DATABASE_PATH=./data/agent.db

API_KEY_ENABLED=true
API_KEY_USERS={"replace-with-a-secret-key":"alice"}
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

受保护接口的用户身份由 `API_KEY_USERS` 绑定；只配置 `API_KEYS` 不足以调用需要认证用户的操作，传入 `user_id` 或 `X-User-ID` 也不会切换身份。示例中的 `alice` 不会自动获得管理员权限。

如使用本地模型，先启动 Ollama 并准备与配置一致的模型：

```bash
ollama serve
# 在另一个终端执行
ollama pull qwen3.5:9b
```

模型名称可按本机可用模型调整。其他模型路由的凭据与参数见 [.env.example](.env.example) 和 [src/config.py](src/config.py)。

### 启动与探针

```bash
python start.py
```

按上述配置，主 API 地址为 `http://127.0.0.1:3000`，交互式接口说明位于 `/docs`。

| 接口 | 含义 |
| --- | --- |
| `GET /health` | 存活检查，HTTP 200 表示应用可响应 |
| `GET /ready` | 必需插件初始化成功且启动完成时 HTTP 200，否则 HTTP 503 |

模型路由、记忆存储、技能管理器与工具执行器是必需组件，初始化失败会终止启动并清理资源。IM 及 MCP HTTP 子服务目前属于可选集成，失败时可能返回 `degraded`；强依赖这些集成的部署应进一步检查对应状态。

探针公开且不参与业务限流。`ready` 只表示本地初始化状态，不保证真实模型请求成功或飞书持续在线。详细状态含义见[运行与架构说明](docs/运行与架构说明.md)。

### 发送第一条消息

向 `POST /api/v1/message` 发送以下 JSON，并设置请求头 `X-API-Key: replace-with-a-secret-key`：

```json
{
  "message_id": "office-request-20261021-001",
  "content": "请帮我整理一份周报大纲"
}
```

响应格式为 `{"response":"..."}`。客户端重试同一逻辑请求时沿用 `message_id`；新请求使用新标识。未提供标识时由服务端生成，无法识别下一次客户端请求是否属于重投。

同一来源、用户和消息标识已完成时复用缓存结果；输入内容冲突时拒绝执行。失败、中断或结果尚未确认的请求不会自动重放，响应提供参考号。核查外部操作后再决定是否发起新请求，详见[失败核查流程](docs/运行与架构说明.md#消息重投与失败核查)。

## 架构与执行流程

```text
HTTP API / IM 消息
    → MessageRouter：持久化请求认领与结果缓存
    → MessageGraph（不可用时，在执行前选择手写流程）
    → 会话与消息存储 → 群消息过滤 → 文件检测 / PPT 确认状态
    → 技能摘要预匹配
        ├─ 命中：加载完整技能 → SkillStepExecutor
        └─ 未命中：意图识别 → PPT 工作流 / ReAct / 直接处理
    → 保存响应 → 返回用户

ReAct 执行轨迹 / 用户纠正 → 技能草稿 → 结构验证与管理员审核 → 发布
```

文件上传跳过技能预匹配；等待 PPT 确认时优先继续对应工作流。图运行中失败不会重跑整条手写流程；ReAct Agent 已开始执行后也不会退回 JSON 模式重放请求。TaskPlanner 仅用于相应任务路径，并非每条消息都经过的统一规划层。

技能自动生成与修补只产生草稿，不直接覆盖已发布技能。结构验证不等同于真实业务验收，发布仍需管理员审核。

中间件请求顺序为：CORS → 请求日志 → 响应日志 → IP 限流 → API Key 认证 → 业务接口。未认证请求同样限流；同一出口 IP 共享限流窗口。

## 项目结构

```text
.
├── start.py                      # Uvicorn 启动入口
├── src/
│   ├── main.py                   # 应用、显式启动与清理、探针
│   ├── config.py                 # 环境配置
│   ├── types.py                  # 消息、技能、任务、权限等数据模型
│   ├── api/v1/
│   │   ├── endpoints.py          # 聚合领域路由，统一 /api/v1 前缀
│   │   ├── dependencies.py       # 共享应用服务
│   │   └── messages.py / skills.py / learning.py / permissions.py / audit.py / mcp.py
│   ├── gateway/                  # IM 接入、会话、消息路由与 LangGraph 图
│   ├── engine/                   # ReAct、PPT、技能执行/学习、MCP、检查点与调度
│   ├── skills/                   # 领域管理、匹配、预设/自定义/学习技能与文件同步
│   ├── tools/                    # 工具实现、注册、运行约束及共享输入 schema
│   ├── plugins/                  # 模型、记忆、技能、工具和 IM 插件
│   ├── services/                 # 文件上下文、演示消息、权限、审计与技能验证
│   ├── data/                     # SQLite、请求认领、检索与重排序代码
│   └── middleware/               # 认证、限流与日志
├── tests/                        # 隔离数据库及本机模拟服务的回归测试
├── config/                       # 外部 MCP 配置示例
├── prompts/                      # ReAct 提示词
├── templates/                    # PPT 布局规范、图表及图标索引
├── skills/                       # 磁盘技能内容
├── data/                         # 运行数据库与检查点
├── workspace/                    # 工作文件
├── output/                       # 生成产物
├── logs/                         # 文件日志
├── docs/                         # 架构、修复计划及验证记录
├── requirements.txt
└── constraints-py312.txt
```

`src/skills/` 和 `src/data/` 是代码；根目录同名目录保存运行内容。导入 `src.main` 不创建数据库、目录或外部连接，资源在显式启动或首次使用时初始化。技能插件委托领域管理器，避免独立技能副本；通用工具 schema 位于 `src/tools/schemas.py`。

## API 概览

| 领域 | 主要接口 | 约束 |
| --- | --- | --- |
| 消息 | `POST /api/v1/message` | 需要绑定用户的 API Key |
| IM | `POST /api/v1/im/webhook/{adapter_type}` | 依赖平台注册、配置及认证策略 |
| 技能 | `GET/POST /api/v1/skills`、`POST /api/v1/skills/{skill_id}/execute` | 写入与执行等操作绑定认证用户并按操作检查权限 |
| 版本 | `GET /api/v1/skills/{skill_id}/versions`、`POST /api/v1/skills/{skill_id}/rollback/{version}` | 回滚需要相应权限 |
| 学习 | `POST /api/v1/feedback`、`GET /api/v1/skill-drafts`、`POST /api/v1/skill-drafts/{draft_id}/review` | 审核发布需要管理员权限 |
| 用户与记忆 | `GET/PUT /api/v1/user/{user_id}`、`GET /api/v1/memory/search` | 限制本人或管理员访问 |
| 授权 | `POST /api/v1/permissions/tool`、`POST /api/v1/users/{user_id}/role` | 授权及角色变更由管理员操作 |
| 审计 | `GET /api/v1/audit/logs`、`POST /api/v1/audit/verify` | 管理员访问 |
| MCP 客户端 | `GET /api/v1/mcp/client/status`、`GET /api/v1/mcp/client/tools` | 状态限管理员；工具目录按当前用户权限过滤 |

完整路径、参数和响应以运行后的 `/docs`、`/openapi.json` 为准。文档/PPT 操作通过消息路由或工具执行；不提供旧文档中列出的 `/api/v1/document/search`、`/api/v1/ppt/*` 专用 HTTP 接口。

## 飞书接入与 PPT

在飞书开放平台创建应用并按所需功能配置消息接收、文件读取和发送权限，然后填写：

```env
FEISHU_APP_ID=your-app-id
FEISHU_APP_SECRET=your-app-secret
FEISHU_BOT_NAME=Hermes-Office-Synergy-Agent
```

主应用在配置凭据后启动飞书 WebSocket 长连接。群消息需要提及机器人；上传文件可进入文档分析，PPT 请求通过规划与确认后生成文件。独立 PPT 工作流返回文件信息，发送到 IM 还依赖发送工具和平台权限，不能仅以文件生成成功认定已发送。

持久化状态和失败恢复、各模块入口及其他 IM 边界见[运行与架构说明](docs/运行与架构说明.md)。

## Agent 调用外部 MCP 工具

本项目同时提供两个方向：Agent 作为 MCP 客户端调用外部服务，MCP Server 则把本项目能力提供给外部应用。两者独立启用，不负责替代会话与记忆管理。

客户端支持 Stdio 和 Streamable HTTP，启动时发现外部工具并保留其 JSON Schema，注册为 `mcp__服务名__工具名`（较长或特殊名称带稳定哈希）。原生工具调用和 JSON ReAct 模式均可使用。连接按次创建并关闭，Stdio 服务必须支持每次启动；目前不导入外部 resources/prompts，不支持 OAuth 交互授权或旧版 HTTP+SSE。

配置步骤：

1. 复制 `config/mcp_servers.example.json` 为 `config/mcp_servers.json`，填写服务地址或本地命令，并把要使用的服务设为 `"enabled": true`。
2. 在 `.env` 设置 `MCP_CLIENT_ENABLED=true`、`MCP_SERVERS_CONFIG=./config/mcp_servers.json`，然后重启服务。
3. 通过 `headers_env` / `env_from` 从系统环境变量或 `.env` 读取凭证（系统环境变量优先）；配置文件仅由服务管理员维护，不接受聊天消息动态新增地址或执行命令。
4. 用 `allowed_tools` 限定远端工具，用 `allowed_users` 限定本地用户。管理员可执行允许的工具；其他用户还须通过现有工具授权接口获得对应 `mcp__...` 工具的显式 `execute` 授权（支持部门授权）。普通角色的通用工具执行权限不足以执行外部工具。

管理员可通过 `GET /api/v1/mcp/client/status` 查看发现状态和工具 ID；`GET /api/v1/mcp/client/tools` 仅返回当前认证用户可执行的工具。这些 API 沿用 `API_KEY_ENABLED=true` 和 `API_KEY_USERS` 身份映射，状态接口不返回连接凭证。个人授权使用管理员身份调用 `POST /api/v1/permissions/tool`：

```json
{"tool_id":"mcp__office__search_documents","user_id":"alice","permission":"execute"}
```

服务名称限定为字母开头、最多 16 位字母/数字/下划线/连字符。`allowed_users`、`allowed_tools` 省略表示不额外限制，空数组表示不允许任何用户或工具。工具 schema 保留嵌套定义，`$ref` 仅支持文档内引用，不下载外部 schema。`user_id` 是本地身份字段，远端 schema 若声明该参数，其值由认证身份确定。

远端服务不可用时记录发现失败并继续启动本地功能；调用失败、超时和 MCP `isError` 返回失败，不自动重试写入。`MCP_CLIENT_TIMEOUT` 控制默认超时秒数，服务配置可覆盖。工具目录在启动时发现，修改配置或远端工具后需要重启服务。外部服务使用配置的服务账号凭证，本地用户权限不会自动变成远端账号权限，应按服务账号的数据范围授权。

参考：[MCP 官方架构](https://modelcontextprotocol.io/docs/learn/architecture)、[Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

## MCP Server

服务端使用官方 Python MCP SDK，通过 Stdio 或 Streamable HTTP 提供工具、资源和提示模板。HTTP 子服务可随主应用启动：

```env
MCP_SERVER_ENABLED=true
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8000
API_KEY_USERS={"replace-with-a-secret-key":"alice"}
```

客户端地址为 `http://127.0.0.1:8000/mcp`，请求必须携带对应的 `X-API-Key`。MCP HTTP 始终验证 `API_KEY_USERS` 映射，不依赖主 API 的 `API_KEY_ENABLED` 开关；仅配置 `API_KEYS` 不足以绑定身份。

已注册工具包括文档/记忆搜索、Mock 网页搜索、代码执行、文件操作、飞书文件读取、PPT 生成与模板匹配。搜索和执行工具复用受控工具执行器；用户身份由服务端确定，传入其他 `user_id` 不会切换身份。

Stdio 不自动获得用户身份，受保护工具缺少身份时拒绝执行。需要显式初始化插件和身份上下文的独立进程集成，不能只调用 `run_server()` 就认为全部业务工具已就绪。

## 运行测试

```bash
# 全量回归
python -m pytest -q

# 消息恢复、并发隔离与就绪检查
python -m pytest tests/test_message_routing_recovery.py tests/test_application_readiness.py -q

# 工具、技能生命周期与 MCP
python -m pytest tests/test_tools_skills_contracts.py tests/test_learning_lifecycle.py tests/test_mcp_client.py -q

# API 结构和依赖约束
python -m pytest tests/test_structure_contracts.py tests/test_dependency_constraints.py -q

# 编译与差异检查
python -m compileall -q src tests
git diff --check
```

2026-10-21 全量结果：**103 passed, 20 warnings in 46.97s**。警告来自 FastAPI 生命周期接口和第三方库弃用提示。测试使用隔离数据库，并包含本机 Stdio、HTTP MCP 协议验证；真实模型、业务 MCP、飞书端到端和全新环境安装尚未验证。详细分批结果见[修复验证记录](docs/修复验证记录.md)。

## 常见问题

- **接口返回 401**：确认 `API_KEY_ENABLED=true`，请求头携带 `X-API-Key`，该 Key 在 `API_KEY_USERS` 中绑定有效用户。
- **`/health` 正常但业务不可用**：查看 `/ready` 的组件与集成状态，再检查模型/平台连通性；存活检查不验证外部服务。
- **失败请求重试没有重新执行**：这是结果不明时的保护行为。根据参考号核查请求记录及外部结果后，再明确发起新请求；不要盲目更换 ID 重试。
- **PPT 已生成但 IM 未收到**：确认实际调用了发送工具，并核查平台凭据、权限和发送结果。
- **技能未自动发布**：自动学习生成草稿，需结构验证与管理员审核后发布。
- **网页搜索返回示例链接**：当前 WebSearchTool 为 Mock，需接入真实搜索服务后才能提供实时结果。

## 许可证

MIT License

## 更新日志

### 未发布（2026-10-21）

**R1–R8 稳定性与结构修复：**

- 消除图不可用时的递归降级；仅在业务执行前选择手写流程，停止执行失败后的整条流程重放。
- 增加持久化请求认领、输入指纹和结果缓存；同一消息重投不重复执行，失败返回核查参考号。
- 必需插件失败终止启动并清理资源；新增 `/ready`，跟踪可选后台服务状态。
- 隔离技能建议、执行轨迹及图检查点，统一文件上传路由；IP 限流不再信任 `X-User-ID`。
- 技能插件复用领域管理器；统一工具 schema 与 MCP 搜索执行入口，补齐技能实际删除。
- API 按六个领域拆分；抽取文件上下文和演示消息服务，导入应用不再创建数据库、目录或外部连接。
- 增加依赖约束与运行说明。最新全量回归：**103 项通过、0 失败，20 条弃用警告**；编译与 diff 检查通过。下文 58 项为此前批次的历史结果。
- 逐项验收和未验证边界见[修复验证记录](docs/修复验证记录.md)。


**Agent 外部 MCP 客户端：**

- 新增可配置的 Stdio / Streamable HTTP 工具发现与调用，接入本地工具执行器、原生工具调用及 JSON ReAct 提示词。
- 工具名称隔离、嵌套 JSON Schema 参数验证、显式权限检查、超时及连接清理；更正 MCP 与会话管理的概念，以及工具描述符的 `inputSchema` 字段。
- 增加管理员状态和目录查询、用户可执行工具查询；支持环境变量与 `.env` 凭证引用，配置文件不纳入 Git。
- 回归共 **58 项通过**，含临时 Stdio 和回环 HTTP MCP 服务的真实发现/调用、原生工具包装、JSON ReAct、技能步骤、部门授权、凭证和错误清理；未调用真实业务 MCP 服务或真实模型。


**默认记忆、交互式 PPT、MCP HTTP 与部门权限修复：**

- `simple` 注册为 SQLite 持久化记忆存储，支持用户隔离、记忆增删查及用户资料；修复内存存储方法被同名字段覆盖的问题。
- 交互式 PPT 使用异步图调用和状态查询，支持确认、取消、继续以及从持久化检查点恢复。
- MCP HTTP 改用 SDK 的 Streamable HTTP ASGI 接口，提供 `/mcp` 端点并管理会话生命周期；HTTP 请求通过 API Key 用户映射绑定身份，启动与关闭使用同一应用工厂。记忆和文档查询绑定认证用户，偏好读取用户资料；PPT、模板与飞书文件读取复用受控工具执行器。
- 权限检查结合用户授权、当前所属部门授权及全局范围授权；部门变更后重新计算有效权限，保留角色本身授予的权限。部门和全局授权仅管理员可授予，非法权限批次在写入前拒绝；权限详情接口限制本人或管理员访问。

**自动学习机制修复：**

- 自动生成与自动修补仅保存草稿，不写入正式技能目录、不直接覆盖已发布技能；发布须经过管理员审核和结构验证。
- 审核状态、技能发布及版本历史在同一数据库事务中更新；重复批准不会重复发布，存储失败会回滚，过期修补草稿不能覆盖新版本。
- 按用户和来源轨迹去重，拒绝失败轨迹；修补仅关联当前用户有编辑权限的技能，并保留步骤 ID、条件和跳转关系。
- ReAct 执行轨迹按请求隔离，后台学习使用当前请求的独立快照，避免并发串用用户数据。默认上限调整为 8 个推理步骤、6 次工具调用，使 5 次成功调用的学习阈值可达。
- 数据库启动时增量迁移，持久化技能版本、创建者及草稿元数据；历史上已经丢失的版本和创建者信息无法自动恢复。
- 使用统计仅在实际执行后记录一次，按真实结果统计成功或失败；匹配不计为执行，归档技能停止匹配与执行，新技能按创建时间计算闲置期。
- 纠正数据明确传入执行提示词；重复反馈去重；补齐草稿验证、列表查询及访问权限。结构验证不等同于真实业务验收，发布仍需管理员审核。
- 启动时隔离无审核凭据或被修改的 learned 技能文件；旧版未经审核便导入的自动生成技能也会被标记隔离。

**Tools / Skills 执行修复：**

- 统一工具注册、构造、参数校验及错误结果，修复 PPT 工具构造参数不兼容、内容生成工具同步调用异步模型等问题。
- 补齐技能步骤描述及执行轨迹类型；修复失败被计作成功的问题。步骤失败默认停止，仅显式配置 `on_error: continue` 时继续，备用工具按定义执行。
- 支持实际条件判断、`next_step_id` 跳转及执行次数限制；参数可通过 `${generate-outline.outline}`、`${match-template.templates.0.id}` 等完整值引用传递列表与对象。
- 修复数据分析和图表预设中的占位代码与缺失参数，接通 PPT 大纲、模板、内容、文件生成和真实文件质检流程。
- SKILL.md 保存完整结构化技能数据，保留 ID、元数据、参数类型、多行内容及步骤关系，兼容读取旧格式；编辑新格式时应修改 `Skill Data` JSON 块。
- 补齐技能更新、权限查询、持久化版本历史和回滚；参考文档限制在项目知识目录内，并增加读取大小限制。

**安全与服务修复：**

- API 操作者由服务端 API Key 用户映射确定，客户端传入的管理员身份不再生效；受保护操作需设置 `API_KEY_ENABLED=true` 和 `API_KEY_USERS`，例如 `{"your-secret-key":"alice"}`。认证开启但无有效 Key 时拒绝访问。
- 限制跨用户资料、记忆及草稿访问，适配器注册仅限管理员；工具授权统一要求管理员身份，权限撤销实际删除指定数据库记录。
- 文件访问按真实目录层级检查，拒绝同名前缀目录和符号链接越界；修复目录白名单被按字符遍历的问题，配置支持 JSON 数组或逗号分隔路径。
- Python 代码只在受限 Docker 容器中执行，禁用网络并限制资源，Docker 不可用时明确失败，不降级为宿主执行。镜像由 `SANDBOX_CONTAINER_IMAGE` 配置并需预先准备；默认镜像只含标准库，数据分析和图表需准备含 pandas、matplotlib 等依赖的镜像。
- MCP 代码与文件工具复用受控执行器，缺少服务端认证身份时拒绝执行。
- 补齐审计查询、导出、哈希链完整性校验及技能操作记录，日志持久化，导出路径限制在 `output` 目录。
- 修复角色查询返回类型和技能执行接口仅返回描述的问题；异步检查点连接延迟到服务事件循环创建，并在关闭时释放。
- 飞书回调切回服务事件循环；回复发送成功后才标记消息完成。失败待发回复持久化缓存，重新投递时复用回复，避免重复执行工具；用户限流通过延迟处理保留。

**验证与升级说明：**

- 测试使用项目内临时目录和隔离数据库，不写入运行数据；`python -m pytest tests/ -q`：**58 项通过**，语法检查及 `git diff --check` 通过。
- 覆盖审核绕过、权限拒绝、事务回滚、并发轨迹、跨连接去重、数据库迁移、统计与归档，以及真实工具类和 PPT 预设流程；新增默认记忆重开、用户隔离、部门变更、PPT 确认/取消/恢复、MCP HTTP 协议和关闭生命周期回归。模型和消息发送使用模拟实现，PPT 文件实际生成并读取，MCP 通过内存 ASGI 客户端验证。
- Docker 守护进程检查超时，尚未完成真实容器执行验证；未发送真实飞书消息，未完成真实模型与飞书的端到端验证。
- 重启服务后加载代码并执行数据库迁移；HTTP 401 表示正常的鉴权拒绝，不应通过关闭鉴权消除。

---

### v1.2.0 (2026-06-05)

**新功能：技能预匹配执行 + 执行披露 + 三层 Token 优化**

- **技能预匹配路由**：在意图识别前进行 Tier 1 轻量级技能匹配（使用 `SkillSummary`），高置信度（score ≥ 0.5）直接执行技能步骤链，跳过意图识别→路由→处理器流程
- **`SkillStepExecutor`** (`src/engine/skill_executor.py`)：按技能步骤链顺序执行工具调用（17 个已注册工具）和 LLM 语义动作（22 种），上下文在步骤间累积传递，捕获 `ExecutionTrace` 供自学习管道使用
- **三层执行披露**：预执行披露头（🔧 使用技能「xxx」）→ 逐步执行进度（✅/❌/⏱️）→ 归因页脚（⚡ 技能信息 + 用户控制提示）
- **接近匹配建议**：score 0.3-0.5 的技能不自动执行，仅提示用户 "💡 您的问题可能适合使用「xxx」技能..."
- **`SkillSummary` 模型** (`src/types.py`)：Tier 1 轻量级技能摘要（~500 chars），仅含匹配所需字段，内存为完整 Skill 的 1/5~1/10
- **`db.get_skills_summaries()`**：不反序列化完整 SkillStep 对象，仅提取 instruction 文本，12 技能场景减少 55% 数据量
- **Tier 2 按需加载**：`TriggerMatcher.load_full_skill()` 仅在确认匹配后加载完整 Skill
- **Tier 3 参考文档**：`_load_reference_docs()` 从 `skill.metadata.references` 按需加载领域知识文档，注入 LLM prompt
- **`TriggerMatcher` 重构**：`find_relevant_skill()` 返回 `SkillSummary`；新增 `find_relevant_skill_with_near_misses()` 返回 `(best, [near_misses])`；`_calculate_match_score()` 兼容两种类型
- **LangGraph 消息图更新**：新增 `skill_prematch` 节点（detect_file → recognize 之间）+ `handle_skill` 节点
- **`_handle_skill_request()` 修复**：从返回技能描述文本改为实际执行技能步骤链
- **12 个企业办公预设技能**：覆盖 6 大类别（文档处理、沟通协作、知识管理、数据分析、任务管理、演示展示），每个技能绑定真实工具链
- **触发模式优化**：174 个触发模式覆盖自然语言变体，匹配准确率 75%（9/12 高置信度），0 误匹配

### v1.1.0 (2026-06-05)

**新功能：技能自学习系统（参照 Nous Research Hermes Agent 设计）**

1. **技能自动生成器** (`src/engine/skill_generator.py`)
   - ReAct 引擎完成复杂任务（5+ 次工具调用）后自动生成技能
   - LLM 分析执行轨迹，生成结构化技能定义 + SKILL.md
   - 置信度 >= 0.6 自动提升为待审核状态
2. **技能自动修补器** (`src/engine/skill_patcher.py`)
   - 用户纠正时检测是否关联到已有 learned 技能
   - LLM diff 分析后自动修补技能步骤，版本号递增
3. **技能库维护器** (`src/engine/skill_curator.py`)
   - 7天周期自动评分、合并检测、归档低质量技能
   - 评分公式: `0.4*使用频率 + 0.3*成功率 + 0.3*活跃度`
   - 生成维护报告 `skills/curator_report.md`
4. **SKILL.md 文件管理器** (`src/skills/skill_md.py`)
   - agentskills.io 兼容的 Markdown 技能文件读写
   - YAML frontmatter + Markdown body 格式
   - 启动时自动同步文件系统 → 数据库
5. **执行轨迹系统** (`src/engine/react_engine.py`)
   - ReAct 引擎新增 `ExecutionTrace` 捕获（LangGraph + 手动循环两路径）
   - 完整记录工具调用序列（工具名、参数、结果、耗时）
   - 新增 `execution_traces` + `skill_usage` 数据库表
6. **后台调度器** (`src/engine/scheduler.py`)
   - 纯 asyncio 实现，零外部依赖
   - 支持周期性任务和一次性延迟任务

**功能改进：**

1. **三闸门学习循环完善** (`src/engine/learning_cycle.py`)
   - Gate 1 (捕获): 隐式纠正检测（6 个中文关键词）+ 显式 API 反馈
   - Gate 2 (学习): 差异分析 → 技能草稿生成 → DB 持久化
   - Gate 3 (应用): 人工审核 → 创建 learned 技能 → 写入 SKILL.md
2. **MCP Server 生产化** (`src/engine/mcp_server.py`)
   - 新增 `start_http_server()` / `stop_http_server()` 非阻塞实现
   - 新增 `MCP_SERVER_ENABLED` / `MCP_SERVER_PORT` 配置项
   - FastAPI startup/shutdown 事件自动启停
3. **VectorStore + RAG 集成** (`src/data/vector_store.py`, `src/data/reranker.py`)
   - VectorStore 从空占位符升级为可用搜索引擎（关键词 + BM25 评分）
   - 纯 Python BM25Reranker 实现
   - 高级检索管道：BM25 → CrossEncoder → RecencyBoost
4. **安全加固**
   - 8 处 `eval()` 替换为 `ast.literal_eval()` + `json.loads()` 安全反序列化
   - FileOperationsTool 添加路径白名单检查
5. **认证与限流** (`src/middleware/`)
   - API Key 认证中间件
   - 滑动窗口速率限制中间件
6. **权限系统持久化** (`src/services/permission_service.py`, `src/data/database.py`)
   - 新增 `user_roles`、`permissions` 数据库表
   - 完整的 RBAC 实现（admin/developer/user/guest）
7. **会话持久化** (`src/gateway/message_router.py`)
   - 会话从内存迁移到 SQLite，重启不丢失

**架构优化：**

1. **LangGraph 集成**
   - ReAct 引擎: `create_agent()` 替代手写循环
   - PPT 工作流: `StateGraph` 替代手动状态机
   - 消息路由: LangGraph 管道图 + 手写管道回退
   - 检查点: `AsyncSqliteSaver` 替代 `MemorySaver`
2. **DeepSeek 模型支持** — 新增 `DeepSeekRouter`（OpenAI API 兼容）
3. **LangChain 工具包装层** (`src/engine/langchain_tools.py`)
4. **表情符号映射分离** — `EMOJI_MAP` 从 utils.py 提取到独立文件
5. **配置优化** — `MEMORY_STORE_TYPE` 默认值改为 `simple`

---

### v1.0.3 (2026-05-24)

**Bug修复：**

1. **异步方法声明缺失**：修复了多个方法缺少 `async` 声明导致的协程调用错误

   - `ReActEngine.run()` 方法添加 `async` 声明
   - `_handle_with_react()` 方法添加 `async` 声明
   - 所有 handler 方法（`_handle_summarization`、`_handle_question_answering` 等）添加 `async` 声明
2. **start_time 变量未定义**：修复了 `elapsed_ms` 计算始终为0的问题

   - 在 `run()` 方法开始处定义 `start_time = datetime.now()`
3. **API 不兼容**：修复了 `call_model()` 方法不存在的问题

   - 在 `ModelRouterBase` 基类中添加了 `call_model()` 方法定义
4. **缺少 await 调用**：修复了所有异步调用缺少 `await` 的问题

   - 为 `react_engine.run()` 调用添加 `await`
   - 为 `model_router.call_model()` 调用添加 `await`
5. **工具执行阻塞事件循环**：优化了 `_execute_tool()` 方法

   - 将方法改为异步（`async def`）
   - 使用 `loop.run_in_executor()` 将同步工具执行转移到线程池
6. **导入路径错误**：修复了 PPT 工具无法加载的问题

   - 确保使用正确的导入路径 `from src.tools.ppt_tools import ...`

**功能改进：**

1. **异步架构优化**：全面优化了系统的异步处理能力

   - 所有模型调用、工具执行、消息路由均改为异步
   - 使用线程池避免阻塞事件循环
2. **Ollama 配置增强**：完善了 Ollama 模型配置支持

   - 添加完整的 Ollama 配置参数（模型名称、最大token、温度、重试次数、超时时间）
   - 支持通过 `.env` 文件配置

---

### v1.0.2 (2026-05-03)

**新功能：**

1. **MCP Server（基于官方 Python MCP SDK）**：实现了标准的工具服务器

   - 使用官方 MCP SDK (`mcp`) 实现
   - 装饰器模式声明式定义工具
   - 支持 10+ 工具：文档搜索、记忆搜索、网页搜索、代码执行、文件操作等
   - 支持 Stdio 和 HTTP 传输方式
   - 完全符合 MCP 协议规范
2. **RAG 增强系统**：实现了高级检索系统

   - BM25 关键词索引（SQLite 持久化）
   - 高级检索管道（过滤器 + 重排序）
   - 多种重排序策略：Linear、BM25、CrossEncoder、Hybrid
   - 查询扩展支持
   - 文档加载、版本管理、多模态处理

**功能改进：**

1. **测试覆盖**：新增 MCP Server 测试用例

   - MCP Server 实例测试
   - 工具注册测试
   - 工具调用测试
2. **测试脚本**：新增 MCP Server 测试脚本

   - `test_mcp_server.py` 提供完整的功能演示
3. **错误处理**：增强 MCP Server 错误处理

   - 依赖模块缺失时的优雅降级
   - 工具调用异常捕获和日志记录
   - MCP SDK 未安装时的友好提示

**Bug修复：**

---

### v1.0.1 (2026-04-28)

**Bug修复：**

1. **文件上传内容解析错误**：修复了飞书文件上传后返回内容与文件不符的问题

   - 问题原因：`feishu_file_read` 工具返回的嵌套结构未正确解析（`result["result"]["content"]` 而非 `result["content"]`）
   - 修复位置：`src/gateway/message_router.py` 中的 `_handle_document_analysis` 和 `_handle_ppt_generation` 方法
2. **file_v3格式文件读取失败**：修复了飞书新版 file_v3 格式文件无法读取的问题

   - 问题原因：缺少 `message_id` 参数，新版飞书API要求必须提供消息ID才能下载文件
   - 修复位置：在调用 `feishu_file_read` 工具时添加了完整的参数（`file_key`、`message_id`、`user_id`）
3. **ReAct引擎崩溃**：修复了 `action_type` 变量未定义导致的 UnboundLocalError

   - 问题原因：`action_type` 在异常处理前未定义，导致异常发生时无法访问该变量
   - 修复位置：`src/engine/react_engine.py`，将变量定义提前到动作执行之前
4. **元数据传递缺失**：修复了文档分析时无法获取当前消息元数据的问题

   - 问题原因：`_handle_intent` 方法未传递 `metadata` 参数给处理器
   - 修复位置：修改了所有 handler 方法签名，添加 `metadata` 参数支持

**功能改进：**

1. **文档分析流程优化**：优化了文件上传后的处理流程

   - 优先从当前消息元数据获取文件信息
   - 直接调用工具读取文件内容而非依赖历史消息
   - 支持 PDF、DOCX 等多种文件格式的内容提取
2. **日志系统增强**：增强了各模块的日志记录

   - 按模块拆分日志文件（api.log、engine.log、gateway.log、tool.log）
   - 添加了详细的请求上下文追踪
3. **错误处理增强**：改进了工具调用失败时的错误处理

   - 添加了更详细的错误日志
   - 增强了异常捕获和恢复机制

---
