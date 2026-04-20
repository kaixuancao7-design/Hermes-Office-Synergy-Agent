# Hermes Office Synergy Agent

基于 Hermes Agent 架构的智能办公协同助手，具备长期记忆、技能自动沉淀与跨端执行能力，支持插件化扩展和企业级权限管理。

## 核心特性

- **多模态交互**：支持飞书、钉钉、企业微信等主流 IM 平台
- **自我进化闭环**：通过用户反馈自动学习并沉淀技能，支持技能验证环节
- **记忆分层存储**：短期记忆（会话）、长期记忆（向量库）、程序性记忆（技能库）
- **多模型支持**：兼容 OpenAI、Claude、Ollama、智谱、Kimi 等模型
- **安全沙箱**：代码执行隔离，确保运行安全
- **插件化架构**：IM适配器、模型路由、记忆存储、技能管理、工具执行均为独立插件
- **技能版本管理**：支持版本回滚、修改日志记录
- **细粒度权限控制**：基于角色的访问控制（RBAC），支持按部门划分权限
- **操作审计日志**：不可篡改的操作记录，满足企业合规要求

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
│  ReActEngine / 自我进化闭环                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  数据与记忆层 (Data & Memory)                                            │
│  SQLite数据库 / MemoryBase (Chroma/Milvus/FAISS) / 程序性记忆             │
├─────────────────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                             │
│  ModelRouterBase / 安全沙箱 / 配置管理 / 权限服务 / 审计服务               │
└─────────────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.10+
- pip 20.0+
- Ollama（可选，用于本地模型）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

创建 `.env` 文件：

```env
# 模型配置（任选其一或多个）
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OLLAMA_HOST=http://localhost:11434

# 数据库配置
DATABASE_PATH=./data/agent.db
VECTOR_DB_PATH=./data/vectors

# 服务配置
PORT=3000
HOST=0.0.0.0
LOG_LEVEL=INFO

# 记忆存储配置
MEMORY_STORE_TYPE=chroma  # chroma, milvus, faiss, hybrid

# Milvus配置（当MEMORY_STORE_TYPE=milvus时）
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=your-milvus-token

# 飞书配置（可选）
FEISHU_APP_ID=your-feishu-app-id
FEISHU_APP_SECRET=your-feishu-app-secret
FEISHU_BOT_NAME=Hermes-Office-Synergy-Agent
```

### 启动 Ollama（可选）

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
│   │   ├── intent_recognition.py     # 意图识别
│   │   ├── learning_cycle.py         # 学习循环（自我进化）
│   │   ├── memory_manager.py         # 记忆管理
│   │   ├── react_engine.py           # ReAct推理引擎
│   │   └── task_planner.py           # 任务规划
│   ├── gateway/
│   │   ├── feishu_websocket.py       # 飞书WebSocket服务
│   │   ├── im_adapter.py             # IM适配器管理
│   │   └── message_router.py         # 消息路由
│   ├── logging_config.py             # 日志配置（按模块拆分）
│   ├── exceptions.py                 # 统一异常处理
│   ├── main.py                       # FastAPI入口
│   ├── plugins/
│   │   ├── base.py                   # 抽象基类定义
│   │   ├── skill_managers.py         # 技能管理插件
│   │   ├── memory_stores.py          # 记忆存储插件
│   │   ├── model_routers.py          # 模型路由插件
│   │   └── im_adapters.py            # IM适配器插件
│   ├── services/
│   │   ├── skill_verification.py     # 技能验证服务
│   │   ├── skill_management.py       # 技能版本管理
│   │   ├── permission_service.py     # 细粒度权限服务
│   │   └── audit_log_service.py      # 审计日志服务
│   ├── skills/
│   │   └── skill_manager.py          # 技能管理
│   ├── tools/
│   │   ├── office_tools.py           # 办公工具
│   │   └── tool_executor.py          # 工具执行器
│   ├── types.py                      # 类型定义
│   └── utils.py                      # 工具函数
├── tests/                            # 测试文件
│   ├── conftest.py                   # 测试配置
│   ├── test_api.py                   # API测试
│   ├── test_database.py              # 数据库测试
│   └── test_utils.py                 # 工具函数测试
├── logs/                             # 日志目录（按模块拆分）
│   ├── api.log
│   ├── model.log
│   ├── im.log
│   └── engine.log
├── data/                             # 数据目录
├── .gitignore
├── requirements.txt
├── start.py                          # 启动脚本
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

### 2. 技能与工具层 (Skills & Tools)

#### 2.1 技能管理器 (`src/skills/skill_manager.py`)

管理技能的完整生命周期：

**核心功能：**
- 技能创建/编辑/删除
- 技能版本管理
- 技能执行与调度
- 权限检查集成

**技能结构：**
```python
{
    "id": "skill-001",
    "name": "周报生成",
    "description": "自动生成周报",
    "type": "preset",
    "version": "1.0.0",
    "created_by": "admin",
    "steps": [
        {"action": "execute", "parameters": {"instruction": "分析本周工作内容"}}
    ],
    "trigger_patterns": ["周报", "总结"],
    "metadata": {...}
}
```

**版本管理特性：**
- 自动版本号递增（语义化版本）
- 支持回滚到历史版本
- 完整的修改日志记录

#### 2.2 工具执行器 (`src/tools/tool_executor.py`)

安全执行各类工具：

**核心功能：**
- 工具注册与发现
- 参数校验
- 沙箱隔离执行
- 执行结果处理

**内置工具：**
| 工具类型 | 说明 | 危险级别 |
|----------|------|----------|
| `file_read` | 读取文件 | 低 |
| `file_write` | 写入文件 | 中 |
| `file_delete` | 删除文件 | 高 |
| `system_command` | 执行系统命令 | 高 |
| `web_search` | 网络搜索 | 低 |

**危险工具控制：**
- 需要管理员授权才能执行
- 执行前进行权限检查
- 详细记录审计日志

---

### 3. 核心引擎层 (Engine)

#### 3.1 ReAct引擎 (`src/engine/react_engine.py`)

实现推理-行动循环：

**核心流程：**
1. **思考**：分析当前状态，决定下一步行动
2. **行动**：调用工具或技能
3. **观察**：获取执行结果
4. **总结**：生成最终回复

**状态管理：**
- 维护对话状态
- 追踪已执行步骤
- 管理上下文信息

#### 3.2 意图识别 (`src/engine/intent_recognition.py`)

识别用户意图：

**核心功能：**
- 关键词匹配
- LLM意图分类
- 技能匹配
- 上下文理解

**意图类型：**
- `skill_execution`: 执行技能
- `question_answering`: 问答
- `task_planning`: 任务规划
- `feedback`: 反馈提交

#### 3.3 任务规划 (`src/engine/task_planner.py`)

将复杂任务分解为子任务：

**核心功能：**
- 任务分解
- 步骤排序
- 依赖分析
- 执行调度

#### 3.4 记忆管理 (`src/engine/memory_manager.py`)

管理三层记忆体系：

**记忆层次：**
| 层次 | 存储位置 | 生命周期 | 用途 |
|------|----------|----------|------|
| 短期记忆 | 内存 | 会话级别 | 当前对话上下文 |
| 长期记忆 | 向量库 | 持久化 | 知识检索、历史对话 |
| 程序性记忆 | 技能库 | 持久化 | 可复用的工作流程 |

**记忆操作：**
- `search`: 搜索相关记忆
- `save`: 保存新记忆
- `update`: 更新记忆
- `delete`: 删除记忆

#### 3.5 学习循环 (`src/engine/learning_cycle.py`)

实现自我进化闭环：

**学习流程：**
```
用户反馈 → 差异分析 → 技能提炼 → 技能验证 → 技能存储 → 自动应用
```

**核心功能：**
- 反馈收集与分析
- 技能自动生成
- 技能验证（自动+人工）
- 技能优化迭代

---

### 4. 数据与记忆层 (Data & Memory)

#### 4.1 SQLite数据库 (`src/data/database.py`)

存储结构化数据：

**数据表：**
| 表名 | 用途 |
|------|------|
| `skills` | 技能定义 |
| `skill_versions` | 技能版本历史 |
| `users` | 用户信息 |
| `roles` | 用户角色 |
| `permissions` | 权限配置 |
| `audit_logs` | 审计日志 |

**数据库操作：**
- 连接池管理
- 事务支持
- 数据迁移

#### 4.2 向量库 (`src/data/vector_store.py`)

存储非结构化数据的向量表示：

**支持的向量数据库：**
| 数据库 | 配置方式 | 适用场景 |
|--------|----------|----------|
| Chroma | 内置 | 开发测试 |
| Milvus | 独立部署 | 大规模生产 |
| FAISS | 内置 | 单机高性能 |

**向量操作：**
- 向量化文本
- 相似性搜索
- 向量存储与更新

---

### 5. 基础设施层 (Infrastructure)

#### 5.1 模型路由 (`src/infrastructure/model_router.py`)

管理多个AI模型的调用：

**核心功能：**
- 模型选择策略
- 负载均衡
- 故障切换
- 成本控制

**支持的模型：**
| 模型 | 提供商 | API类型 |
|------|--------|----------|
| GPT-4o | OpenAI | REST |
| Claude 3.5 | Anthropic | REST |
| Qwen | Ollama | 本地 |
| GLM-4 | 智谱 | REST |

**模型选择策略：**
- `auto`: 根据任务类型自动选择
- `fallback`: 主模型失败时切换备用模型
- `round-robin`: 轮询调度

#### 5.2 安全沙箱 (`src/infrastructure/sandbox.py`)

隔离危险操作：

**核心功能：**
- 代码执行隔离
- 文件系统访问控制
- 网络访问限制
- 资源使用限制

**安全策略：**
- 限制执行时间
- 限制内存使用
- 白名单机制

---

### 6. 权限与审计服务

#### 6.1 细粒度权限服务 (`src/services/permission_service.py`)

实现企业级权限管理：

**角色体系：**
| 角色 | 权限范围 |
|------|----------|
| `admin` | 全权限 |
| `developer` | 技能开发、工具配置 |
| `user` | 技能使用、反馈提交 |
| `guest` | 只读访问 |

**权限类型：**
| 资源 | 权限 |
|------|------|
| 技能 | read, execute, edit, delete, grant |
| 工具 | execute, configure |
| 记忆 | read, write, delete, search |
| 配置 | view, modify |

**权限范围：**
- `user`: 针对特定用户
- `department`: 针对部门所有用户
- `all`: 全局权限

**使用示例：**
```python
from src.services.permission_service import permission_service

# 设置用户角色
permission_service.set_user_role("admin", "user123", "user", "研发部")

# 授予权限
permission_service.grant_skill_permission("admin", "skill-001", "user123", "execute")

# 检查权限
result = permission_service.check_skill_permission("user123", "skill-001", "execute")
```

#### 6.2 审计日志服务 (`src/services/audit_log_service.py`)

记录所有关键操作：

**记录的操作类型：**
| 类别 | 操作类型 |
|------|----------|
| 用户管理 | login, logout, user_create, role_change |
| 技能管理 | skill_create, skill_edit, skill_delete, skill_execute |
| 工具操作 | tool_execute, tool_configure |
| 权限管理 | permission_grant, permission_revoke |
| 系统配置 | config_modify |

**防篡改机制：**
- SHA-256哈希链
- 每条日志包含前一条日志的校验和
- 支持完整日志链验证

**日志查询：**
- 按操作人查询
- 按操作类型查询
- 按时间范围查询
- 支持分页

---

### 7. API接口层 (`src/api/v1/endpoints.py`)

提供RESTful API接口：

**接口分类：**
| 类别 | 接口数量 | 说明 |
|------|----------|------|
| 消息处理 | 2 | 发送消息、接收消息 |
| 技能管理 | 5 | CRUD操作、版本管理 |
| 记忆管理 | 3 | 搜索、存储、删除 |
| 学习反馈 | 3 | 提交反馈、学习统计 |
| 权限管理 | 8 | 角色管理、权限授予 |
| 审计日志 | 5 | 查询、验证、导出 |

**API安全：**
- 请求ID追踪
- 用户身份验证
- 权限检查
- 速率限制

---

## 技能架构

系统采用 **流程编排型技能架构**，支持三种技能类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `preset` | 预置技能 | 会议纪要、周报生成、竞品分析 |
| `custom` | 用户自定义 | 用户创建的工作流 |
| `learned` | 自动习得 | 通过学习循环获得 |

技能结构包含：
- **触发模式**：匹配用户意图的关键词列表
- **步骤链**：有序的工具调用步骤
- **条件分支**：根据执行结果选择不同路径
- **版本号**：技能版本管理
- **元数据**：创建者、来源等信息

## 日志系统

日志按模块和级别拆分：

| 日志文件 | 内容 |
|----------|------|
| `api.log` | API请求日志，包含请求ID、用户ID |
| `model.log` | 模型调用日志，包含耗时、令牌数 |
| `im.log` | IM消息日志，包含消息路由、推送 |
| `engine.log` | 引擎日志，包含技能执行、学习循环 |

日志格式包含：请求ID、用户ID、时间戳、模块、级别、消息、堆栈信息。

## 运行测试

```bash
# 安装测试依赖
pip install pytest httpx

# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_database.py -v
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

### Q: 向量数据库初始化失败

A: 请确保配置了 OpenAI API Key 或使用支持嵌入模型的本地方案。

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
