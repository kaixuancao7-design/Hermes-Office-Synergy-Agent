# Hermes Office Synergy Agent

基于 Hermes Agent 架构的智能办公协同助手，具备长期记忆、技能自动沉淀与跨端执行能力，支持插件化扩展和企业级权限管理。

> **项目遵循 HERMES.md 四大核心原则**：
> - **Think Before Coding**：执行前先验证理解，生成假设澄清清单
> - **Simplicity First**：技能复杂度控制，拒绝过度设计
> - **Surgical Changes**：最小diff原则，精准修改
> - **Goal-Driven Execution**：测试闭环，自我验证

## 核心特性

- **多模态交互**：支持飞书、钉钉、企业微信等主流 IM 平台
- **自我进化闭环**：通过用户反馈自动学习并沉淀技能，包含三闸门验证机制（假设澄清→复杂度检查→测试验证）
- **记忆分层存储**：短期记忆（会话）、长期记忆（向量库）、程序性记忆（技能库）
- **多模型支持**：兼容 OpenAI、Claude、Ollama、智谱、Kimi 等模型
- **安全沙箱**：代码执行隔离，插件白名单机制，危险工具权限管控
- **插件化架构**：IM适配器、模型路由、记忆存储、技能管理、工具执行均为独立插件
- **技能版本管理**：支持版本回滚、修改日志记录、变更diff检查
- **细粒度权限控制**：基于角色的访问控制（RBAC），支持按部门划分权限范围
- **操作审计日志**：SHA-256哈希链防篡改，满足企业合规要求
- **IM→演示稿全流程智能协同**：支持从IM消息触发PPT生成，自动发送到IM
- **文件服务支持**：支持文件上传、读取和内容解析，可基于上传文件生成PPT
- **任务执行反思**：工具调用失败时自动分析原因并尝试修复（切换备用工具、重新生成参数）
- **细粒度意图识别**：支持PPT相关意图的精确区分（生成大纲、从大纲生成PPT、从内容生成PPT、自定义生成），实现意图到工具的精准映射

## 架构设计

系统采用插件化架构设计，各模块独立封装，通过抽象基类定义统一接口：

```
┌─────────────────────────────────────────────────────────────────────────┐
│  交互网关层 (Gateway)                                                   │
│  IMAdapterBase / MessageRouter / WebSocket服务                           │
├─────────────────────────────────────────────────────────────────────────┤
│  技能与工具层 (Skills & Tools)                                           │
│  SkillManagerBase / ToolExecutorBase / 技能库 / 工具箱                    │
├─────────────────────────────────────────────────────────────────────────┤
│  核心引擎层 (Engine)                                                     │
│  IntentRecognition / TaskPlanner / MemoryManager / LearningCycle         │
│  ReActEngine / 自我进化闭环 / 需求解析器 / IM触发器                        │
├─────────────────────────────────────────────────────────────────────────┤
│  数据与记忆层 (Data & Memory)                                            │
│  SQLite数据库 / MemoryBase (Chroma/Milvus/FAISS) / 程序性记忆             │
├─────────────────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                             │
│  ModelRouterBase / 安全沙箱 / 配置管理 / 权限服务 / 审计服务               │
├─────────────────────────────────────────────────────────────────────────┤
│  服务层 (Services)                                                       │
│  PPT服务 / 技能验证服务 / 技能管理服务                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.10+
- pip 20.0+
- Ollama（推荐，用于本地模型，避免API密钥依赖）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

创建 `.env` 文件：

```env
# 模型配置（任选其一或多个）
# OPENAI_API_KEY=your-openai-api-key  # 如果使用OpenAI模型
# ANTHROPIC_API_KEY=your-anthropic-api-key
OLLAMA_HOST=http://localhost:11434  # 推荐使用Ollama，无需API密钥

# 数据库配置
DATABASE_PATH=./data/agent.db
VECTOR_DB_PATH=./data/vectors

# 服务配置
PORT=3000
HOST=0.0.0.0
LOG_LEVEL=DEBUG

# 记忆存储配置（使用simple避免嵌入问题）
MEMORY_STORE_TYPE=simple  # chroma, milvus, faiss, hybrid, simple, redis_hybrid

# Milvus配置（当MEMORY_STORE_TYPE=milvus时）
# MILVUS_URI=http://localhost:19530
# MILVUS_TOKEN=your-milvus-token

# 插件配置
MODEL_ROUTER_TYPE=ollama  # ollama, openai, anthropic, zhipu, moonshot, multi
TOOL_EXECUTOR_TYPE=sandboxed

# 飞书配置（可选）
# FEISHU_APP_ID=your-feishu-app-id
# FEISHU_APP_SECRET=your-feishu-app-secret
# FEISHU_BOT_NAME=Hermes-Office-Synergy-Agent

# Redis配置（当MEMORY_STORE_TYPE=redis_hybrid时）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 启动 Ollama（推荐）

```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型（推荐 qwen3.5:9b）
ollama pull qwen3.5:9b
```

### 启动服务

```bash
python start.py
```

服务将在 http://localhost:3000 启动。

## 核心功能：IM→演示稿全流程智能协同

### 功能概述

从IM消息触发到PPT生成并自动发送的完整闭环：

1. **IM端触发**：支持@机器人、关键词、文件附件等多种触发方式
2. **需求智能解析**：自动提取PPT主题、页数、受众、风格等需求要素
3. **智能大纲生成**：基于需求生成结构化大纲
4. **内容创作**：自动填充内容，支持多种幻灯片类型
5. **演示稿生成**：基于python-pptx库自动生成PPT文件
6. **IM发送**：生成后自动上传并发送给用户

### 触发方式

| 触发类型 | 说明 | 示例 |
|----------|------|------|
| @机器人 | 直接@机器人触发 | `@Hermes-Office-Synergy-Agent 帮我生成一份产品介绍PPT` |
| 关键词触发 | 包含关键词自动触发 | `生成周报PPT` |
| 附件触发 | 上传文件自动分析 | 上传需求文档 |

### PPT生成工具

系统提供多种PPT生成工具：

- `generate_ppt`：直接生成PPT（不发送）
- `generate_ppt_from_outline`：从大纲生成PPT
- `generate_and_send_ppt`：生成PPT并通过IM发送给用户

### 支持的幻灯片类型

| 类型 | 说明 | 示例 |
|------|------|------|
| title | 标题页 | 演示稿封面 |
| bullet | 项目符号页 | 要点列表 |
| chart | 图表页 | 数据可视化 |
| content | 内容页 | 详细内容展示 |

## 飞书配置

### 飞书开放平台配置

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `APP_ID` 和 `APP_SECRET`
4. 在「事件订阅」中添加 `im.message.receive_v1` 事件

### WebSocket 连接

系统默认使用 **WebSocket 长连接** 方式接收飞书事件，具有以下优势：
- 无需配置公网域名
- 实时消息推送
- 更低的延迟

### 环境变量配置

```env
FEISHU_APP_ID=your-feishu-app-id
FEISHU_APP_SECRET=your-feishu-app-secret
FEISHU_BOT_NAME=Hermes
FEISHU_CONNECTION_MODE=websocket
```

## API 接口

### 健康检查

```bash
GET /health
# 返回: {"status": "healthy"}
```

### 发送消息

```bash
POST /api/v1/message
{
    "user_id": "user123",
    "content": "帮我生成周报",
    "metadata": {"source": "api"}
}
```

### 技能管理

```bash
# 获取技能列表
GET /api/v1/skills?user_id=user123

# 创建技能
POST /api/v1/skills
{
    "user_id": "user123",
    "name": "自定义技能",
    "description": "描述",
    "steps": [
        {"action": "execute", "parameters": {"instruction": "步骤1"}}
    ]
}

# 更新技能
PUT /api/v1/skills/{skill_id}?user_id=admin
{
    "name": "新名称",
    "description": "新描述",
    "change_note": "修改说明"
}

# 删除技能
DELETE /api/v1/skills/{skill_id}?user_id=admin

# 执行技能
POST /api/v1/skills/{skill_id}/execute?user_id=user123
```

### 技能版本管理

```bash
# 获取技能版本列表
GET /api/v1/skills/{skill_id}/versions

# 获取指定版本
GET /api/v1/skills/{skill_id}/versions/{version}

# 回滚到指定版本
POST /api/v1/skills/{skill_id}/rollback/{version}?user_id=admin

# 获取修改日志
GET /api/v1/skills/{skill_id}/change-logs
```

### 权限管理

```bash
# 设置用户角色
POST /api/v1/users/{user_id}/role?role=user&admin_id=admin

# 获取用户角色
GET /api/v1/users/{user_id}/role

# 授予技能权限
POST /api/v1/permissions/skill
{
    "grantor_id": "admin",
    "skill_id": "skill-001",
    "user_id": "user123",
    "permission": "execute"
}

# 检查权限
POST /api/v1/permissions/check/skill?skill_id=skill-001&user_id=user123&permission=execute
```

### 记忆管理

```bash
# 搜索记忆
GET /api/v1/memory/search?user_id=user123&query=关键词

# 获取用户资料
GET /api/v1/user/{user_id}

# 更新用户资料
PUT /api/v1/user/{user_id}
{
    "writing_style": "正式",
    "preferences": {"theme": "dark"}
}
```

### 学习与反馈

```bash
# 提交反馈（用于自我进化）
POST /api/v1/feedback
{
    "user_id": "user123",
    "original": "原始回复",
    "corrected": "修正后的回复",
    "context": "对话上下文",
    "intent": "用户意图"
}

# 获取学习统计
GET /api/v1/learning/stats

# 建议创建技能
POST /api/v1/learning/suggest-skill?user_id=user123
{"task_description": "每周一生成周报"}
```

### 技能草稿与验证

```bash
# 获取待审核的技能草稿
GET /api/v1/skill-drafts?status=pending

# 获取草稿详情
GET /api/v1/skill-drafts/{draft_id}

# 人工审核
POST /api/v1/skill-drafts/{draft_id}/review
{
    "approved": true,
    "reviewer_id": "admin",
    "comments": "技能定义完整，可以使用"
}
```

### 审计日志

```bash
# 查询审计日志
GET /api/v1/audit/logs?operator_id=user123&operation_type=skill_create&page=1&page_size=20

# 获取日志详情
GET /api/v1/audit/logs/{log_id}

# 获取用户操作日志
GET /api/v1/audit/logs/operator/{user_id}

# 验证日志完整性
POST /api/v1/audit/verify

# 导出日志
POST /api/v1/audit/export?file_path=./audit_logs.json
```

### PPT服务接口

```bash
# 生成PPT并发送
POST /api/v1/ppt/generate-and-send
{
    "user_id": "user123",
    "title": "产品介绍",
    "slides": [
        {"type": "title", "content": {"title": "产品介绍", "subtitle": "2024年Q4"}},
        {"type": "bullet", "content": {"title": "核心功能", "items": ["功能1", "功能2", "功能3"]}}
    ],
    "im_adapter_type": "feishu"
}

# 仅生成PPT
POST /api/v1/ppt/generate
{
    "title": "产品介绍",
    "slides": [...]
}
```

## 自我进化闭环

系统通过学习循环实现自我进化，包含完整的技能提炼与验证流程：

1. **反馈捕获**：用户提交修正反馈
2. **意图提取**：分析用户真实意图
3. **差异分析**：对比原始输出与修正输出，结合上下文提炼可复用模式
4. **技能草稿生成**：LLM 生成技能草稿
5. **技能验证**：自动验证（对比历史任务效果）或人工审核
6. **技能存储**：验证通过的技能存入技能库
7. **自动应用**：后续任务自动匹配并使用学习到的技能

```
用户提问 → 生成响应 → 用户反馈修正 → 差异分析 → 生成草稿 → 自动/人工验证 → 存入技能库 → 下次自动匹配
```

## 任务执行反思环节

系统具备任务执行反思能力，当工具调用失败时会自动分析并尝试修复，避免断链：

1. **失败分析**：识别失败原因（参数错误、工具不可用、连接失败、超时、权限不足、Pydantic验证错误等）
2. **恢复策略**：
   - **切换备用工具**：当当前工具不可用时，自动切换到备用工具
   - **重新生成参数**：分析参数错误原因，重新生成正确的参数
   - **简化参数**：移除不必要的复杂参数，使用默认值
3. **最大恢复尝试**：可配置最大重试次数，避免无限循环
4. **错误日志记录**：详细记录失败原因、恢复尝试次数和最终结果，便于问题排查

## 角色与权限体系

### 角色定义

| 角色 | 权限范围 |
|------|----------|
| `admin` | 全权限（技能、工具、记忆、API、配置） |
| `developer` | 技能全权限、工具全权限、记忆读写、API访问、配置查看 |
| `user` | 技能读写执行、工具执行、记忆读取、API访问 |
| `guest` | 仅技能读取权限 |

### 权限类型

| 资源类型 | 权限 |
|----------|------|
| 技能 | read, execute, edit, delete, grant |
| 工具 | execute, configure |
| 记忆 | read, write, delete, search |
| API | access |
| 配置 | view, modify |

## 支持的 IM 平台

| 平台 | 连接方式 | 状态 |
|------|---------|------|
| 飞书 | WebSocket 长连接 | ✅ 支持 |
| 钉钉 | Webhook | ✅ 支持 |
| 企业微信 | API | ✅ 支持 |
| 微信 | API | ✅ 支持 |
| Slack | WebSocket | ✅ 支持 |
| Discord | WebSocket | ✅ 支持 |

## 支持的模型

| 模型 | 提供商 | 配置方式 |
|------|--------|---------|
| GPT-4o / GPT-4 | OpenAI | API Key |
| Claude 3.5 Sonnet | Anthropic | API Key |
| Qwen / Llama / Mistral | Ollama | 本地部署 |
| GLM-4 | 智谱 | API Key |
| Kimi | Moonshot | API Key |

## 记忆存储方案

系统支持多种向量数据库，通过配置文件切换：

| 存储类型 | 配置值 | 适用场景 |
|----------|--------|----------|
| Chroma | `chroma` | 开发测试、轻量级部署 |
| Milvus | `milvus` | 大规模生产环境 |
| FAISS | `faiss` | 单机高性能场景 |
| Hybrid | `hybrid` | 混合存储策略 |
| Simple | `simple` | 开发测试，无需嵌入 |
| Redis Hybrid | `redis_hybrid` | Redis + 向量库混合 |

## 项目结构

```
.
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py          # API端点定义
│   ├── config.py                     # 配置管理
│   ├── data/
│   │   ├── database.py               # SQLite数据库
│   │   └── vector_store.py           # 向量库
│   ├── engine/
│   │   ├── intent_recognition.py     # 意图识别（细粒度分类、意图-工具映射）
│   │   ├── learning_cycle.py         # 学习循环（三闸门验证）
│   │   ├── memory_manager.py         # 记忆管理
│   │   ├── react_engine.py           # ReAct推理引擎
│   │   ├── task_planner.py           # 任务规划
│   │   ├── demand_parser.py          # 需求解析器（PPT需求提取）
│   │   └── im_trigger.py             # IM触发器（多模态触发）
│   ├── gateway/
│   │   ├── feishu_websocket.py       # 飞书WebSocket服务
│   │   ├── im_adapter.py             # IM适配器管理
│   │   └── message_router.py         # 消息路由
│   ├── logging_config.py             # 日志配置（按模块拆分）
│   ├── exceptions.py                 # 统一异常处理
│   ├── main.py                       # FastAPI入口
│   ├── plugins/
│   │   ├── __init__.py               # 插件初始化与获取函数
│   │   ├── base.py                   # 抽象基类定义 + 插件安全管理器
│   │   ├── skill_managers.py         # 技能管理插件
│   │   ├── memory_stores.py          # 记忆存储插件
│   │   ├── model_routers.py          # 模型路由插件
│   │   └── im_adapters.py            # IM适配器插件
│   ├── services/
│   │   ├── skill_verification.py     # 技能验证服务
│   │   ├── skill_management.py       # 技能版本管理
│   │   ├── permission_service.py     # 细粒度权限服务
│   │   ├── audit_log_service.py      # 审计日志服务（SHA-256防篡改）
│   │   └── ppt_service.py            # PPT服务（生成与发送）
│   ├── skills/
│   │   └── skill_manager.py          # 技能管理（复杂度检查、变更验证）
│   ├── tools/
│   │   ├── office_tools.py           # 办公工具
│   │   └── tool_executor.py          # 工具执行器
│   ├── types.py                      # 类型定义（含AssumptionChecklist）
│   └── utils.py                      # 工具函数
├── prompts/
│   └── react_system_prompt.txt       # ReAct系统提示词（外部化管理）
├── tests/                            # 测试文件
│   ├── conftest.py                   # 测试配置
│   ├── test_api.py                   # API测试
│   ├── test_database.py              # 数据库测试
│   ├── test_utils.py                 # 工具函数测试
│   ├── test_agent_self_verification.py # Agent自验证用例库
│   ├── test_ppt_generator.py         # PPT生成测试
│   ├── test_demand_parser.py         # 需求解析测试
│   └── test_react_engine_recovery.py # ReAct引擎恢复测试
├── logs/                             # 日志目录（按模块拆分）
│   ├── api.log
│   ├── model.log
│   ├── im.log
│   ├── engine.log
│   ├── gateway.log
│   └── audit.log                     # 审计日志（不可篡改）
├── data/                             # 数据目录
├── .gitignore
├── requirements.txt
├── start.py                          # 启动脚本
├── HERMES.md                         # 项目编码铁律与规范
└── README.md
```

## 模块详解

### 1. 交互网关层 (Gateway)

#### 1.1 IM适配器管理 (`src/gateway/im_adapter.py`)

负责管理多个IM平台的适配器，支持动态切换和扩展：

**核心功能：**
- 统一消息格式转换：将不同IM平台的消息格式统一为内部格式
- 适配器生命周期管理：启动、停止、健康检查
- 消息路由分发：根据消息来源路由到相应的处理器

**支持的IM平台：**
| 平台 | 适配器类 | 连接方式 |
|------|----------|----------|
| 飞书 | `FeishuAdapter` | WebSocket长连接 |
| 钉钉 | `DingTalkAdapter` | Webhook |
| 企业微信 | `WeComAdapter` | API轮询 |

**使用示例：**
```python
from src.gateway.im_adapter import im_adapter_manager

# 初始化适配器
await im_adapter_manager.initialize_adapters()

# 发送消息
await im_adapter_manager.send_message(
    platform="feishu",
    user_id="user123",
    content="您好！"
)
```

#### 1.2 消息路由 (`src/gateway/message_router.py`)

负责消息的分发和处理：

**核心功能：**
- 消息分类：识别消息类型（文本、图片、文件、事件等）
- 意图识别：初步判断用户意图
- 路由策略：根据意图分发到不同的处理模块

---

### 2. 核心引擎层 (Engine)

#### 2.1 ReAct引擎 (`src/engine/react_engine.py`)

实现推理-行动循环，支持任务执行反思：

**核心流程：**
1. **思考**：分析当前状态，决定下一步行动
2. **行动**：调用工具或技能
3. **观察**：获取执行结果
4. **反思**：如果失败，分析原因并尝试修复
5. **总结**：生成最终回复

**支持的动作类型：**
- `tool_call`: 调用工具
- `finish`: 完成任务
- `summarize`: 总结内容
- `memory_search`: 搜索记忆
- `document_search`: 搜索文档
- `tool_executor`: 执行工具
- `generate_ppt`: 生成PPT
- `generate_ppt_from_outline`: 从大纲生成PPT
- `generate_and_send_ppt`: 生成并发送PPT

#### 2.2 需求解析器 (`src/engine/demand_parser.py`)

解析用户PPT生成需求：

**核心功能：**
- 从自然语言提取PPT需求（标题、页数、受众、风格等）
- 生成需求确认消息
- 聚合群聊需求

**支持的受众类型：**
- 内部团队
- 客户
- 公众/公开演讲
- 管理层

**支持的风格类型：**
- 正式/商务
- 简洁/极简
- 创意/活泼

#### 2.3 IM触发器 (`src/engine/im_trigger.py`)

处理IM多模态触发：

**触发类型：**
- **主动触发**：@机器人
- **被动触发**：关键词匹配
- **附件触发**：文件上传

---

### 3. 服务层 (Services)

#### 3.1 PPT服务 (`src/services/ppt_service.py`)

整合PPT生成与IM发送：

**核心方法：**
- `generate_and_send_ppt()`: 生成PPT并发送给用户
- `generate_from_outline_and_send()`: 从大纲生成PPT并发送
- `generate_ppt_only()`: 仅生成PPT（不发送）

---

### 4. 插件系统 (`src/plugins/`)

#### 4.1 插件初始化 (`src/plugins/__init__.py`)

提供插件获取函数：
- `get_im_adapter(im_type=None)`: 获取IM适配器
- `get_model_router()`: 获取模型路由
- `get_memory_store()`: 获取记忆存储
- `get_skill_manager()`: 获取技能管理器
- `get_tool_executor()`: 获取工具执行器

---

## 日志系统

日志按模块和级别拆分：

| 日志文件 | 内容 |
|----------|------|
| `api.log` | API请求日志，包含请求ID、用户ID |
| `model.log` | 模型调用日志，包含耗时、令牌数 |
| `im.log` | IM消息日志，包含消息路由、推送 |
| `engine.log` | 引擎日志，包含技能执行、学习循环 |
| `gateway.log` | 网关日志，包含WebSocket连接、事件处理 |

日志格式包含：请求ID、用户ID、时间戳、模块、级别、消息、堆栈信息。

## 运行测试

```bash
# 安装测试依赖
pip install pytest httpx

# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_ppt_generator.py -v
python -m pytest tests/test_react_engine_recovery.py -v
```

## 常见问题

### Q: 飞书消息发送后未收到回复

A: 请检查：
1. Ollama 服务是否运行：`ollama serve`
2. 飞书 APP_ID 和 APP_SECRET 是否正确配置
3. 飞书应用是否已添加 `im.message.receive_v1` 事件订阅

### Q: 模型调用失败（404 错误）

A: 请确保 Ollama 服务正在运行：
```bash
ollama serve
```

### Q: OpenAI API密钥无效（401 错误）

A: 推荐使用Ollama避免API密钥问题：
1. 在 `.env` 中设置 `MODEL_ROUTER_TYPE=ollama`
2. 确保 `OLLAMA_HOST=http://localhost:11434` 正确配置
3. 启动Ollama服务并拉取模型

### Q: PPT生成后未发送

A: 请检查：
1. IM适配器配置是否正确
2. `get_im_adapter()` 函数调用是否正确
3. 飞书API权限是否完整

### Q: 如何启用学习循环

A: 学习循环默认启用，用户提交反馈后立即触发技能提炼流程。

### Q: 如何设置用户角色

A: 使用管理员账号调用权限接口：
```bash
POST /api/v1/users/{user_id}/role?role=user&admin_id=admin
```

### Q: 如何验证审计日志完整性

A: 调用审计接口验证日志哈希链：
```bash
POST /api/v1/audit/verify
```

## 许可证

MIT License