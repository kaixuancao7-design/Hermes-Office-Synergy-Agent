# Hermes Office Synergy Agent

基于 Hermes Agent 架构的智能办公协同助手，具备长期记忆、技能自动沉淀与跨端执行能力，支持插件化扩展和企业级权限管理。

> **项目遵循 HERMES.md 四大核心原则**：
>
> - **Think Before Coding**：执行前先验证理解，生成假设澄清清单
> - **Simplicity First**：技能复杂度控制，拒绝过度设计
> - **Surgical Changes**：最小diff原则，精准修改
> - **Goal-Driven Execution**：测试闭环，自我验证

## 核心特性

- **多模态交互**：支持飞书、钉钉、企业微信等主流 IM 平台
- **自我进化闭环**：双引擎学习架构（主动生成 + 被动反馈），三闸门验证机制，7天周期性技能库维护
- **技能预匹配与自动执行**：在意图识别前进行轻量级技能匹配（Tier 1摘要），高置信度直接执行完整步骤链（工具调用 + LLM语义动作），无需用户手动选择
- **渐进式披露**：三层用户可见的技能执行透明度 — 预执行披露头 → 逐步执行进度 → 归因页脚，支持接近匹配技能建议
- **三层 Token 优化**：Tier 1 SkillSummary 常驻匹配（~500 chars/skill），Tier 2 完整 Skill 按需加载，Tier 3 参考文档延迟读取。无关技能全程不占用 LLM 上下文
- **技能自动学习**：执行轨迹追踪 + LLM 驱动技能生成（5+次工具调用自动触发），运行时技能自动修补，SKILL.md 格式（agentskills.io 兼容）
- **记忆分层存储**：短期记忆（会话）、长期记忆（向量库）、程序性记忆（技能库）
- **多模型支持**：兼容 OpenAI、Claude、Ollama、智谱、Kimi、DeepSeek 等模型
- **安全沙箱**：代码执行隔离，插件白名单机制，危险工具权限管控
- **插件化架构**：IM适配器、模型路由、记忆存储、技能管理、工具执行均为独立插件
- **技能版本管理**：支持版本回滚、修改日志记录、变更diff检查
- **细粒度权限控制**：基于角色的访问控制（RBAC），支持按部门划分权限范围
- **操作审计日志**：SHA-256哈希链防篡改，满足企业合规要求
- **12 个企业办公预设技能**：覆盖文档处理、沟通协作、知识管理、数据分析、任务管理、演示展示 6 大类别，每个技能绑定真实工具链
- **IM→演示稿全流程智能协同**：支持从IM消息触发PPT生成，自动发送到IM
- **文件服务支持**：支持文件上传、读取和内容解析，可基于上传文件生成PPT
- **任务执行反思**：工具调用失败时自动分析原因并尝试修复（切换备用工具、重新生成参数）
- **细粒度意图识别**：通用办公意图优先匹配，PPT意图次之，关键词+AI双重分类
- **上下文感知意图分析**：支持指代性词汇解析（如"这个文件"、"那个文档"），结合上下文理解用户真实需求
- **文档分析功能**：支持飞书文件（包括PDF、DOCX等格式）的内容提取和智能分析
- **MCP（Model Context Protocol）**：标准的上下文管理协议，提供统一的上下文创建、更新、查询、序列化接口
- **RAG增强**：高级检索系统，支持BM25关键词搜索、向量语义搜索、重排序、查询扩展、混合检索策略

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
│  ReActEngine / SkillStepExecutor / SkillSummary (Tier 1 摘要)           │
│  SkillAutoGenerator / SkillAutoPatcher / SkillCurator                   │
│  自我进化闭环 / 需求解析器 / IM触发器 / ContextualAnalyzer              │
│  PPTWorkflow / TemplateMatcher / SpecLock / QualityGate / Strategist   │
│  BackgroundScheduler / MCPManager / MCPAdapter (Model Context Protocol) │
├─────────────────────────────────────────────────────────────────────────┤
│  数据与记忆层 (Data & Memory)                                            │
│  SQLite数据库 / MemoryBase (Chroma/Milvus/FAISS) / 程序性记忆             │
│  VectorStore / BM25Index / AdvancedRetrieval / Reranker (RAG增强)        │
│  DocumentLoader / VersionManager / MultimodalProcessor                  │
├─────────────────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                             │
│  ModelRouterBase / 安全沙箱 / 配置管理 / 权限服务 / 审计服务               │
├─────────────────────────────────────────────────────────────────────────┤
│  服务层 (Services)                                                       │
│  PPT服务 / 技能验证服务 / 技能管理服务                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 核心引擎工作流程

```
用户输入
    │
    ▼
┌───────────────────────┐
│  意图识别             │
│  (IntentRecognition)  │
└───────────┬───────────┘
            │ 意图分类
            ▼
┌───────────────────────┐
│  需求解析             │
│  (DemandParser)       │
└───────────┬───────────┘
            │ 解析需求要素
            ▼
┌───────────────────────┐
│  任务规划             │
│  (TaskPlanner)        │
└───────────┬───────────┘
            │ 生成执行计划
            ▼
┌───────────────────────┐     失败
│  ReAct推理引擎        │────────────┐
│  (ReActEngine)        │            │
└───────────┬───────────┘            │
            │ 成功                   │
            ▼                        │
┌───────────────────────┐            │
│  工具执行器           │◄───────────┤
│  (ToolExecutor)       │  重试/修复 │
└───────────┬───────────┘            │
            │                        │
            ▼                        │
┌───────────────────────┐            │
│  结果总结             │            │
│  (Summarizer)         │            │
└───────────┬───────────┘            │
            │                        │
            ▼                        │
   用户响应 ◄─────────────────────────┘
```

### 自我进化闭环流程

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   用户反馈       │────▶│   差异分析       │────▶│   技能草稿生成   │
│   (Feedback)     │     │   (DiffAnalysis) │     │   (SkillDraft)   │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                                                           ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   技能验证       │◀────│   自动/人工审核  │◀────│   意图提取       │
│   (Verification) │     │   (Review)       │     │   (IntentExtrac) │
└────────┬─────────┘     └──────────────────┘     └──────────────────┘
         │ 通过
         ▼
┌──────────────────┐     ┌──────────────────┐
│   技能存储       │────▶│   自动应用       │
│   (SkillStore)   │     │   (AutoApply)    │
└──────────────────┘     └──────────────────┘
```

### 消息路由流程（含技能预匹配）

```
            ┌─────────────────┐
            │   IM消息入口    │
            │ (Feishu/钉钉/企微)│
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │   消息路由      │
            │ (MessageRouter) │
            └────────┬────────┘
                     │
                     ▼
            ┌──────────────────────┐
            │  ★ 技能预匹配 (T1)   │
            │  TriggerMatcher       │
            │  使用 SkillSummary    │
            │  轻量级评分 (~7KB)    │
            └──────┬───────┬───────┘
                   │       │
          score≥0.5│       │score<0.5
                   │       │
                   ▼       ▼
        ┌──────────────┐ ┌──────────────┐
        │ T2 按需加载  │ │  意图识别    │
        │ load_full()  │ │ (IntentRecog)│
        └──────┬───────┘ └──────┬───────┘
               │                │
               ▼                ▼
        ┌──────────────┐ ┌──────────────┐
        │ 技能步骤执行 │ │ 核心引擎处理 │
        │ SkillStep    │ │ ReAct/Direct │
        │ Executor     │ │              │
        └──────┬───────┘ └──────┬───────┘
               │                │
               ▼                ▼
        ┌──────────────────────────────────┐
        │         渐进式披露 + 响应         │
        │  🔧 披露头 → ✅ 步骤进度          │
        │  → LLM回复 → ⚡ 归因页脚          │
        └──────────────────────────────────┘
```

### 记忆分层存储架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                        记忆存储体系                                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │
│  │  短期记忆     │    │  长期记忆     │    │  程序性记忆   │        │
│  │ (Short-term)  │    │ (Long-term)   │    │ (Procedural)  │        │
│  ├───────────────┤    ├───────────────┤    ├───────────────┤        │
│  │ 会话上下文    │    │ 向量数据库    │    │ 技能库        │        │
│  │ 对话历史      │    │ Chroma/Milvus │    │ 工作流        │        │
│  │ 临时状态      │    │ FAISS/Redis   │    │ 触发器        │        │
│  └───────────────┘    └───────────────┘    └───────────────┘        │
│         │                   │                   │                    │
│         └───────────────────┼───────────────────┘                    │
│                             ▼                                        │
│                   ┌───────────────┐                                  │
│                   │  MemoryManager│                                  │
│                   │  (记忆管理器)   │                                  │
│                   └───────────────┘                                  │
└────────────────────────────────────────────────────────────────────────┘
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
MODEL_ROUTER_TYPE=ollama  # ollama, openai, anthropic, zhipu, moonshot, deepseek, multi
TOOL_EXECUTOR_TYPE=sandboxed
MEMORY_STORE_TYPE=simple  # chroma, simple, milvus, faiss, hybrid, redis_hybrid

# DeepSeek 配置（当 MODEL_ROUTER_TYPE=deepseek 时）
# DEEPSEEK_API_KEY=your-deepseek-api-key
# DEEPSEEK_DEFAULT_MODEL=deepseek-v4-pro  # deepseek-v4-pro / deepseek-v4-flash

# 认证与安全
# API_KEY_ENABLED=false  # 设为 true 启用 API Key 认证
# API_KEYS=your-api-key-1,your-api-key-2  # 逗号分隔的有效 API Key
# RATE_LIMIT_ENABLED=true
# RATE_LIMIT_MAX_REQUESTS=60
# RATE_LIMIT_WINDOW_SECONDS=60

# MCP Server 配置
# MCP_SERVER_ENABLED=false  # 设为 true 启用 MCP HTTP 子服务
# MCP_SERVER_PORT=8000      # MCP Server HTTP 端口

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

| 触发类型   | 说明               | 示例                                                     |
| ---------- | ------------------ | -------------------------------------------------------- |
| @机器人    | 直接@机器人触发    | `@Hermes-Office-Synergy-Agent 帮我生成一份产品介绍PPT` |
| 关键词触发 | 包含关键词自动触发 | `生成周报PPT`                                          |
| 附件触发   | 上传文件自动分析   | 上传需求文档                                             |
| 上下文触发 | 基于历史对话理解   | `读取这个文件`、`根据刚才的内容生成PPT`              |

### PPT生成工具

系统提供多种PPT生成工具：

- `generate_ppt`：直接生成PPT（不发送）
- `generate_and_send_ppt`：生成PPT并通过IM发送给用户
- `feishu_file_read`：读取飞书文件内容

### PPT Master工作流

系统引入**PPT Master**设计理念，实现规划-执行分离的PPT生成流程：

```
用户请求 → 意图识别 → PPT工作流
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌───────────┐ ┌───────────┐ ┌───────────┐
    │ 模板匹配  │ │ 规格锁定  │ │ 策略规划  │
    │(Template) │ │(SpecLock) │ │(Strategist)│
    └───────────┘ └───────────┘ └───────────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                ┌───────────────┐
                │  PPT生成器   │
                │(PPTGenerator)│
                └───────────────┘
                         │
                         ▼
                ┌───────────────┐
                │  质量门控    │
                │(QualityGate) │
                └───────────────┘
```

#### 核心组件

| 组件                        | 功能     | 说明                                                   |
| --------------------------- | -------- | ------------------------------------------------------ |
| **TemplateMatcher**   | 模板匹配 | 根据内容分析推荐最优模板（麦肯锡、学术、创意、简约等） |
| **SpecLock**          | 规格锁定 | 锁定设计参数（颜色、字体、布局），防止上下文漂移       |
| **StrategistPlanner** | 策略规划 | 八项确认机制，确保用户需求准确理解                     |
| **QualityGate**       | 质量门控 | 自动检查PPT质量（结构、格式、字体安全）                |

#### 设计原则

- **规划-执行分离**：需求分析输出design_spec，执行器严格按spec生成
- **多阶段确认**：复杂任务前增加用户确认环节（八项确认模板）
- **模板索引系统**：建立模板分类索引，支持内容匹配推荐
- **规格锁定机制**：生成过程中锁定设计参数，防止不一致
- **质量门控**：输出自动检查，错误必须修复才能继续

### 支持的幻灯片类型

| 类型    | 说明       | 示例         |
| ------- | ---------- | ------------ |
| title   | 标题页     | 演示稿封面   |
| bullet  | 项目符号页 | 要点列表     |
| chart   | 图表页     | 数据可视化   |
| content | 内容页     | 详细内容展示 |

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

### 文档搜索

```bash
# 搜索文档知识库
GET /api/v1/document/search?query=关键词&limit=5&user_id=user123
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

系统通过**三层自学习 + 三层 Token 优化 + 三层执行披露**实现完整的自我进化闭环。

### 技能预匹配与执行（Skill Pre-Match & Execution）

每次用户消息在意图识别之前，先进行轻量级技能匹配：

```
用户消息 → [T1 SkillSummary 匹配] → score≥0.5? → [T2 load_full_skill()] → [SkillStepExecutor 执行]
                                         ↓ score<0.5
                                    [意图识别 → 路由 → ReAct/Direct]
```

- **Tier 1 匹配**：使用 `SkillSummary`（~500 chars/skill）进行轻量级评分，仅加载触发词/名称/描述/步骤指令
- **Tier 2 按需加载**：确认匹配后通过 `load_full_skill()` 加载完整 Skill（含 SkillStep 对象）
- **Tier 3 参考文档**：`metadata.references` 中指定的领域文档按需读取，注入 LLM prompt
- **匹配阈值**：score ≥ 0.5 自动执行，0.3-0.5 接近匹配建议但不自动执行
- **工具链执行**：`SkillStepExecutor` 按步骤链顺序执行 — 工具调用（15 个注册工具）→ LLM 语义动作（22 种）

### 执行披露（Progressive Disclosure）

技能执行全程对用户透明，三层信息渐进展示：

```
🔧 使用技能「文档摘要」(预设) — 共 2 步          ← Layer 1: 预执行披露
   置信度: 90% | 版本: 1.0.0

✅ 步骤 1/2: 读取源文档内容 — 完成 (1,234 字符)  ← Layer 2: 步骤进度
✅ 步骤 2/2: 提取核心观点 — 完成 (856 字符)

[LLM 生成的结构化文档总结...]                     ← 技能实际输出

────────────────────                              ← Layer 3: 归因页脚
⚡ 技能: 文档摘要 | 类型: 预设 | 置信度: 90%
💡 回复「不用技能」可直接对话 | 回复「技能列表」查看所有可用技能
```

- **接近匹配建议**：score 0.3-0.5 时提示 "💡 您的问题可能适合使用「xxx」技能..."
- **用户控制**：回复「不用技能」绕过技能直接对话，「技能列表」查看全部技能

### 1. 自动技能生成（Skill Auto-Generator）

当 ReAct 引擎完成复杂任务（5+ 次工具调用）后，自动触发技能生成：

```
复杂任务执行 → 执行轨迹捕获 → LLM 分析提炼 → 生成 SkillDraft → 写入 SKILL.md → 待审核
```

- **触发条件**：工具调用次数 >= 5 且任务成功完成
- **执行轨迹**：完整记录每次工具调用（工具名、参数、结果、耗时）
- **LLM 提炼**：调用 LLM 将工具调用序列泛化为可复用技能步骤
- **置信度评分**：LLM 自评技能质量，>= 0.6 自动提升为待审核状态

### 2. 运行时技能修补（Skill Auto-Patcher）

当用户纠正结果与已有 learned 技能相关时，自动修补该技能：

```
用户纠正 → [T1 摘要匹配关联技能] → [T2 加载完整技能] → LLM diff 分析 → 更新步骤 → 版本递增 → 重写 SKILL.md
```

- **关联检测**：使用 SkillSummary 轻量级匹配，基于触发模式子字符串匹配
- **LLM diff**：对比原始输出 vs 纠正输出，判断是否需要修补
- **版本管理**：修补后自动递增补丁版本号

### 3. 技能库维护（Skill Curator）

后台 7 天周期性自动维护技能库：

```
评分（使用频率+成功率+活跃度） → 相似技能合并检测 → 低质量技能归档 → 生成维护报告
```

- **评分公式**：`score = 0.4 * usage_freq + 0.3 * success_rate + 0.3 * recency`
- **合并检测**：LLM 两两比较功能相似的技能，建议合并
- **自动归档**：score < 0.2 且 30 天未使用的技能自动归档
- **维护报告**：生成 `skills/curator_report.md`

### 4. 用户反馈学习（Feedback Learning）

用户显式提交纠正反馈（API 或 IM 关键词检测）：

1. **反馈捕获**：用户提交修正反馈（显式 API 或隐式关键词检测："不对"、"应该是"、"错了"）
2. **意图提取**：分析用户真实意图
3. **差异分析**：逐行对比原始输出与修正输出，提取可复用模式
4. **技能草稿生成**：生成 SkillDraft（状态=draft 或 pending_review）
5. **人工审核**：管理员审核通过后创建 learned 技能
6. **SKILL.md 持久化**：审核通过后写入 `skills/learned/{name}.md`
7. **自动应用**：后续任务通过触发模式自动匹配

### 学习流水线总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                      自我进化完整闭环                                  │
│                                                                      │
│  执行层                                                              │
│  ─────────────────────────────────────                               │
│  用户消息 → [T1 摘要匹配] → [T2 按需加载] → [SkillStepExecutor]       │
│                  │                              │                     │
│                  ▼                              ▼                     │
│             执行披露                      ExecutionTrace              │
│           (头/进度/尾)                          │                     │
│                                                ▼                     │
│  学习层                                    SkillAutoGenerator         │
│  ─────────────────────────────────────     SkillAutoPatcher           │
│  引擎 A: 主动学习 (Auto-Generator)                                    │
│  ReAct 完成(5+工具) → 执行轨迹 → LLM分析 → SkillDraft → SKILL.md     │
│                                                                      │
│  引擎 B: 被动学习 (Feedback Learning)                                 │
│  用户纠正 → [T1 关联检测] → [T2 加载] → Auto-Patch / Draft → Review  │
│                                                                      │
│  维护层                                                              │
│  ─────────────────────────────────────                               │
│  Skill Curator (7天周期): 评分 → 合并 → 归档 → 报告                  │
└──────────────────────────────────────────────────────────────────────┘
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

## 上下文感知意图分析

系统具备上下文感知能力，能够理解用户的指代性表达：

**支持的指代性词汇：**

- "这个文件"、"那个文件"、"刚才的文件"、"上传的文件"
- "这份文档"、"那个文档"、"刚刚的文档"

**工作流程：**

1. 检测用户输入中的指代性词汇
2. 从上下文中提取相关信息（如最近上传的文件）
3. 根据上下文和意图给出下一步操作建议

## 角色与权限体系

### 角色定义

| 角色          | 权限范围                                            |
| ------------- | --------------------------------------------------- |
| `admin`     | 全权限（技能、工具、记忆、API、配置）               |
| `developer` | 技能全权限、工具全权限、记忆读写、API访问、配置查看 |
| `user`      | 技能读写执行、工具执行、记忆读取、API访问           |
| `guest`     | 仅技能读取权限                                      |

### 权限类型

| 资源类型 | 权限                               |
| -------- | ---------------------------------- |
| 技能     | read, execute, edit, delete, grant |
| 工具     | execute, configure                 |
| 记忆     | read, write, delete, search        |
| API      | access                             |
| 配置     | view, modify                       |

## 支持的 IM 平台

| 平台     | 连接方式         | 状态    |
| -------- | ---------------- | ------- |
| 飞书     | WebSocket 长连接 | ✅ 支持 |
| 钉钉     | Webhook          | ✅ 支持 |
| 企业微信 | API              | ✅ 支持 |
| 微信     | API              | ✅ 支持 |
| Slack    | WebSocket        | ✅ 支持 |
| Discord  | WebSocket        | ✅ 支持 |

## 支持的模型

| 模型                   | 提供商    | 配置方式 |
| ---------------------- | --------- | -------- |
| GPT-4o / GPT-4         | OpenAI    | API Key  |
| Claude 3.5 Sonnet      | Anthropic | API Key  |
| Qwen / Llama / Mistral | Ollama    | 本地部署 |
| GLM-4                  | 智谱      | API Key  |
| Kimi                   | Moonshot  | API Key  |
| DeepSeek-V4            | DeepSeek  | API Key  |

## 记忆存储方案

系统支持多种向量数据库，通过配置文件切换：

| 存储类型     | 配置值           | 适用场景             |
| ------------ | ---------------- | -------------------- |
| Chroma       | `chroma`       | 开发测试、轻量级部署 |
| Milvus       | `milvus`       | 大规模生产环境       |
| FAISS        | `faiss`        | 单机高性能场景       |
| Hybrid       | `hybrid`       | 混合存储策略         |
| Simple       | `simple`       | 开发测试，无需嵌入   |
| Redis Hybrid | `redis_hybrid` | Redis + 向量库混合   |

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
│   │   ├── vector_store.py           # 向量库（文档搜索核心）
│   │   ├── document_loader.py        # 文档加载与预处理
│   │   ├── version_manager.py        # 文档版本管理
│   │   ├── multimodal_processor.py  # 多模态处理（图片/音频/视频）
│   │   ├── advanced_retrieval.py     # 高级检索策略
│   │   └── reranker.py              # BM25 + CrossEncoder 重排序器
│   ├── engine/
│   │   ├── intent_recognition.py     # 意图识别（细粒度分类、上下文感知分析）
│   │   ├── learning_cycle.py         # 学习循环（三闸门验证）
│   │   ├── memory_manager.py         # 记忆管理
│   │   ├── react_engine.py           # ReAct推理引擎（含执行轨迹捕获）
│   │   ├── skill_executor.py         # ★ 技能步骤执行器（工具+LLM分发、执行披露、T3参考文档）
│   │   ├── task_planner.py           # 任务规划
│   │   ├── skill_generator.py        # 技能自动生成器（执行轨迹→技能）
│   │   ├── skill_patcher.py          # 技能自动修补器（T1摘要匹配→T2按需加载）
│   │   ├── skill_curator.py          # 技能库维护器（7天周期）
│   │   ├── scheduler.py              # 后台周期性任务调度器
│   │   ├── demand_parser.py          # 需求解析器（PPT需求提取）
│   │   ├── im_trigger.py             # IM触发器（多模态触发）
│   │   ├── ppt_workflow.py          # PPT工作流（LangGraph StateGraph）
│   │   ├── langchain_tools.py        # LangChain工具包装层
│   │   ├── checkpointer.py           # AsyncSqliteSaver共享单例
│   │   └── mcp_server.py            # MCP Server（基于官方 SDK）
│   ├── gateway/
│   │   ├── feishu_websocket.py       # 飞书WebSocket服务
│   │   ├── im_adapter.py             # IM适配器管理
│   │   ├── message_router.py         # 消息路由
│   │   └── message_graph.py          # LangGraph消息路由图
│   ├── middleware/
│   │   ├── auth_middleware.py        # API Key认证中间件
│   │   ├── rate_limit_middleware.py  # 速率限制中间件
│   │   └── logging_middleware.py     # 请求/响应日志中间件
│   ├── logging_config.py             # 日志配置（按模块拆分）
│   ├── exceptions.py                 # 统一异常处理
│   ├── main.py                       # FastAPI入口
│   ├── plugins/
│   │   ├── __init__.py               # 插件初始化与获取函数
│   │   ├── base.py                   # 抽象基类定义 + 插件安全管理器
│   │   ├── skill_managers.py         # 技能管理插件
│   │   ├── memory_stores.py          # 记忆存储插件
│   │   ├── model_routers.py          # 模型路由插件（统一入口）
│   │   ├── im_adapters.py            # IM适配器插件
│   │   └── tool_executors.py         # 工具执行器插件（统一入口）
│   ├── services/
│   │   ├── skill_verification.py     # 技能验证服务
│   │   ├── skill_management.py       # 技能版本管理
│   │   ├── permission_service.py     # 细粒度权限服务
│   │   ├── audit_log_service.py      # 审计日志服务（SHA-256防篡改）
│   │   └── ppt_service.py            # PPT服务（生成与发送）
│   ├── skills/
│   │   ├── manager.py                # 技能管理器（延迟初始化、循环依赖解决）
│   │   ├── workflow.py               # 工作流引擎
│   │   ├── triggers.py               # 触发匹配器（T1摘要匹配 + T2按需加载 + 接近匹配）
│   │   ├── skill_md.py               # SKILL.md 文件管理器（agentskills.io兼容）
│   │   ├── learned_skills.py         # 学习型技能管理器
│   │   ├── preset_skills.py          # 预设技能
│   │   ├── custom_skills.py          # 自定义技能
│   │   └── adapters/                 # 外部技能适配器
│   ├── tools/
│   │   ├── base.py                   # 工具基类和接口
│   │   ├── registry.py               # 工具注册器
│   │   ├── ppt_generator.py          # PPT生成工具
│   │   ├── file_reader.py            # 文件读取工具
│   │   └── content_tools.py          # 内容处理工具
│   ├── types.py                      # 类型定义（Skill, SkillSummary, ExecutionTrace等）
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
│   ├── test_react_engine_recovery.py # ReAct引擎恢复测试
│   └── test_skill_autolearn.py       # 技能自学习集成测试
├── test_mcp_server.py                # MCP Server 测试
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

| 平台     | 适配器类            | 连接方式        |
| -------- | ------------------- | --------------- |
| 飞书     | `FeishuAdapter`   | WebSocket长连接 |
| 钉钉     | `DingTalkAdapter` | Webhook         |
| 企业微信 | `WeComAdapter`    | API轮询         |

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
- `document_search`: 搜索文档（基于向量数据库）
- `tool_executor`: 执行工具
- `generate_ppt`: 生成PPT
- `generate_ppt_from_outline`: 从大纲生成PPT
- `generate_and_send_ppt`: 生成并发送PPT

#### 2.2 意图识别 (`src/engine/intent_recognition.py`)

实现细粒度意图识别和上下文感知分析：

**核心功能：**

- 细粒度意图分类：区分PPT生成、文件读取、总结等多种意图
- 上下文感知分析：解析指代性词汇，理解用户真实需求
- 意图-工具映射：将意图映射到相应的工具调用
- 下一步行动建议：根据分析结果和上下文给出操作建议

**支持的意图类型：**

| 意图                     | 说明          | 示例                   |
| ------------------------ | ------------- | ---------------------- |
| `ppt_generate_outline` | 生成PPT大纲   | "帮我生成产品介绍大纲" |
| `ppt_generate`         | 生成完整PPT   | "生成产品介绍PPT"      |
| `ppt_from_outline`     | 从大纲生成PPT | "根据这个大纲生成PPT"  |
| `ppt_from_content`     | 从内容生成PPT | "根据文档内容生成PPT"  |
| `summarization`        | 文档总结      | "总结这份文档"         |
| `read_file`            | 文件读取      | "读取这个文件"         |
| `document_search`      | 文档搜索      | "搜索相关文档"         |
| `memory_query`         | 记忆查询      | "我之前说了什么"       |
| `question_answering`   | 问答          | "什么是人工智能"       |
| `code_generation`      | 代码生成      | "写一段Python代码"     |

#### 2.3 需求解析器 (`src/engine/demand_parser.py`)

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

#### 2.4 IM触发器 (`src/engine/im_trigger.py`)

处理IM多模态触发：

**触发类型：**

- **主动触发**：@机器人
- **被动触发**：关键词匹配
- **附件触发**：文件上传
- **上下文触发**：指代性词汇理解

#### 2.5 技能自动生成器 (`src/engine/skill_generator.py`)

从 ReAct 执行轨迹自动生成技能（参照 Hermes Agent 设计）：

**触发条件：** 工具调用次数 >= 5 且任务成功完成

**生成流程：**

1. 总结执行轨迹 → LLM 结构化分析
2. 输出 JSON `{skill_name, description, trigger_patterns, steps, confidence}`
3. 置信度 >= 0.3 时创建 SkillDraft
4. 置信度 >= 0.6 时自动提升为 `pending_review`
5. 写入 `skills/learned/{name}.md`（agentskills.io 兼容格式）

#### 2.6 技能自动修补器 (`src/engine/skill_patcher.py`)

运行时检测用户纠正并修补已有 learned 技能：

- **关联检测**：触发模式子字符串匹配 → 分数 >= 0.5 视为关联
- **LLM diff**：分析原始输出 vs 纠正输出的差异
- **自动修补**：LLM 判断 `should_patch=true` 时更新技能步骤
- **版本递增**：修补后自动递增补丁版本号

#### 2.7 技能库维护器 (`src/engine/skill_curator.py`)

7 天周期自动维护技能库健康度：

| 阶段 | 操作                                       | 说明                         |
| ---- | ------------------------------------------ | ---------------------------- |
| 评分 | `0.4*使用频率 + 0.3*成功率 + 0.3*活跃度` | 使用 `skill_usage` 表数据  |
| 合并 | LLM 两两比较                               | similarity >= 0.7 建议合并   |
| 归档 | score < 0.2 且 30天未使用                  | 标记为 archived              |
| 报告 | 生成 Markdown 报告                         | `skills/curator_report.md` |

#### 2.8 后台调度器 (`src/engine/scheduler.py`)

纯 asyncio 实现的周期性任务调度器：

- `add_periodic()` — 注册周期性任务（如 7 天 Curator）
- `add_one_shot()` — 注册一次性延迟任务
- `start()` / `stop()` — 生命周期管理
- 启动时注册 Curator 7天周期任务 + 60秒后首次运行

#### 2.9 技能步骤执行器 (`src/engine/skill_executor.py`)

按技能定义的步骤链顺序执行工具调用和 LLM 语义动作的核心引擎：

- **`execute_skill()`** — 主入口，接收 Skill + query，逐步执行并返回 `SkillExecutionResult`
- **工具/LLM 自动分发**：`_is_tool_action()` 判断 action 是否在 17 个已注册工具中，工具调用走 `tool_executor.execute()`，语义动作走 `call_model()`
- **上下文累积**：每步结果追加到累积上下文中，后续步骤可引用之前的输出
- **Tier 3 参考文档**：`_load_reference_docs()` 从 `skill.metadata.references` 按需加载领域文档
- **执行披露**：`build_disclosure()` / `build_footer()` / `build_near_miss_suggestion()` 生成三层披露文本
- **执行轨迹**：捕获 `ExecutionTrace` 供自学习管道使用
- **容错**：工具执行器插件不可用时自动回退到硬编码的 17 个已知工具 ID 列表

#### 2.10 三层 Token 优化（Tiered Lazy-Loading）

```
Tier 1: SkillSummary          Tier 2: Full Skill           Tier 3: References
(常驻内存 ~500 chars/skill)   (按需加载 ~3KB/skill)        (延迟读取 可变)

id, name, description,        + steps (SkillStep[])         metadata.references:
type, trigger_patterns,       + metadata                    按需加载的领域文档
step_instructions[]

用于: TriggerMatcher 匹配      用于: SkillStepExecutor 执行  用于: LLM prompt 注入
     执行披露                       SkillCurator 归档
     SkillAutoPatcher 关联检测        SKILL.md 导出
```

**核心原则**：

- Tier 1 永不全量灌入 Prompt — 仅匹配所需字段
- Tier 2 仅在确认匹配后加载 — 99% 的技能不触发时不加载完整步骤
- Tier 3 仅在步骤执行中发现需要时才加载 — 领域知识不占用常驻内存
- 12 技能场景：15KB → 7KB（55% 缩减）；50 技能场景：60KB → 12KB（5x 缩减）

**关键类型**：`SkillSummary`（`src/types.py`）— 新增的 Tier 1 轻量级摘要模型，支持 `from_skill()` 从完整 Skill 提取。

**数据库层**：`db.get_skills_summaries()` — 不反序列化 SkillStep 对象，仅提取 instruction 文本。

**匹配器更新**：`TriggerMatcher` 使用 `get_skills_summaries()` 进行匹配评分，`load_full_skill()` 按需加载 Tier 2。

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
- `get_model_router()`: 获取模型路由（统一入口）
- `get_memory_store()`: 获取记忆存储
- `get_skill_manager()`: 获取技能管理器
- `get_tool_executor()`: 获取工具执行器（统一入口）

#### 4.2 模型路由 (`src/plugins/model_routers.py`)

统一模型路由入口，支持多模型切换：

**支持的模型类型：**

- Ollama（本地部署）
- OpenAI
- Anthropic
- 智谱
- Moonshot
- 多模型路由（自动选择）

#### 4.3 工具执行器 (`src/plugins/tool_executors.py`)

统一工具执行入口，支持沙箱模式：

**核心功能：**

- 工具注册与管理
- 安全沙箱执行环境
- 支持的工具：文件读取、PPT生成、文档搜索、记忆搜索等

---

### 5. 技能系统 (`src/skills/`)

#### 5.1 技能管理器 (`src/skills/manager.py`)

管理技能的注册、执行和权限控制：

**核心特性：**

- 延迟初始化：避免循环依赖
- 外部技能注册：按需注册外部适配器
- 技能版本管理：支持版本回滚和变更记录
- 权限控制：基于角色的访问控制

#### 5.2 SKILL.md 文件管理器 (`src/skills/skill_md.py`)

agentskills.io 兼容的 Markdown 技能文件管理器：

**文件格式：**

```markdown
---
name: skill-name
description: What this skill does
version: 1.0.0
type: learned
triggers:
  - trigger phrase 1
  - trigger phrase 2
created_by: system
created_at: 1717000000
updated_at: 1717000000
---

# skill-name

## Description
...

## Steps
### Step 1: action_name
- **Action**: ...
- **Parameters**: ...
```

**核心方法：**

| 方法                           | 说明                              |
| ------------------------------ | --------------------------------- |
| `skill_to_markdown(skill)`   | Skill 对象 → SKILL.md 字符串     |
| `markdown_to_skill(content)` | SKILL.md 字符串 → Skill 对象     |
| `write_skill_md(skill)`      | 写入 `skills/learned/{name}.md` |
| `read_skill_md(filepath)`    | 读取单个 SKILL.md                 |
| `sync_from_directory()`      | 启动时从文件系统导入技能          |
| `delete_skill_md(name)`      | 删除 SKILL.md 文件                |

**集成点：**

- 技能创建时自动写入 SKILL.md（`learned_skills.py`）
- 启动时同步文件系统中的 SKILL.md 到数据库（`main.py`）
- 自动修补时重写 SKILL.md（`skill_patcher.py`）

---

### 6. 工具系统 (`src/tools/`)

#### 6.1 工具基类 (`src/tools/base.py`)

定义工具接口规范：

- `ToolBase`: 工具基类
- `ToolRegistry`: 工具注册器

#### 6.2 PPT生成工具 (`src/tools/ppt_generator.py`)

PPT生成核心功能：

- `PPTGeneratorBase`: PPT生成基类
- `GeneratePPT`: 生成PPT
- `GeneratePPTFromOutline`: 从大纲生成PPT
- `GeneratePPTFromContent`: 从内容生成PPT

#### 6.3 文件读取工具 (`src/tools/file_reader.py`)

文件读取功能：

- `FeishuFileRead`: 飞书文件读取
- 支持多种文件格式：docx、xlsx、pptx、pdf等

#### 6.4 文档搜索工具 (`src/plugins/tool_executors.py`)

基于向量数据库的文档搜索：

- `DocumentSearchTool`: 文档搜索工具
- 支持语义相似度搜索
- 支持用户隔离搜索

---

## MCP Server (基于官方 Python MCP SDK)

### 概述

项目使用 Python 官方 MCP SDK (`mcp`) 实现工具服务器，提供统一的工具暴露和调用接口。

### 核心功能

MCP Server 通过装饰器模式声明式定义工具，支持以下功能：

| 功能     | 说明                                      |
| -------- | ----------------------------------------- |
| 工具定义 | 使用 `@mcp.tool()` 装饰器定义工具       |
| 资源管理 | 使用 `@mcp.resource()` 装饰器定义资源   |
| 提示模板 | 使用 `@mcp.prompt()` 装饰器定义提示模板 |
| 传输层   | 支持 Stdio 和 HTTP 两种传输方式           |
| 协议规范 | 完全符合 MCP 协议规范                     |

### 已注册工具

| 工具名称                 | 功能描述       |
| ------------------------ | -------------- |
| `document_search`      | 文档语义搜索   |
| `memory_search`        | 记忆搜索       |
| `web_search`           | 网页搜索       |
| `code_execution`       | 代码执行       |
| `file_operations`      | 文件操作       |
| `feishu_file_read`     | 飞书文件读取   |
| `generate_ppt`         | PPT生成        |
| `ppt_template_match`   | PPT模板匹配    |
| `add_to_vector_store`  | 添加到向量存储 |
| `get_user_preferences` | 获取用户偏好   |

### 使用示例

```python
from src.engine.mcp_server import mcp

# 工具已通过装饰器自动注册
# 可通过 MCP 客户端调用这些工具

# 启动 MCP Server (stdio 模式)
from src.engine.mcp_server import run_server
run_server(transport="stdio")

# 启动 MCP Server (HTTP 模式)
run_server(transport="http")
```

### 集成到插件系统

MCP Server 支持两种运行模式：

**1. 独立启动（Stdio/HTTP）：**

```python
from src.engine.mcp_server import run_server
run_server(transport="stdio")   # 或 transport="http"
```

**2. 作为后台子服务（生产环境）：**

在 `.env` 中启用：

```env
MCP_SERVER_ENABLED=true
MCP_SERVER_PORT=8000
```

FastAPI 启动时自动在后台启动 MCP HTTP Server（非阻塞）：

```python
# main.py startup_event 自动处理
if settings.MCP_SERVER_ENABLED:
    asyncio.create_task(start_http_server(port=settings.MCP_SERVER_PORT))
```

---

## RAG 增强系统

### 概述

高级检索系统，支持混合检索策略、重排序、查询扩展等功能。

### 核心组件

| 组件                  | 说明                                   |
| --------------------- | -------------------------------------- |
| `VectorStore`       | 向量存储（基于 Chroma + LangChain）    |
| `BM25Index`         | BM25 关键词索引（SQLite 持久化）       |
| `AdvancedRetrieval` | 高级检索管道                           |
| `Reranker`          | 重排序器（Linear、BM25、CrossEncoder） |
| `DocumentLoader`    | 文档加载与预处理                       |
| `VersionManager`    | 文档版本管理                           |

### 检索策略

| 策略            | 说明                            |
| --------------- | ------------------------------- |
| 向量相似度搜索  | 基于语义相似度的检索            |
| BM25 关键词搜索 | 基于关键词匹配的检索            |
| 混合检索        | 向量 + BM25 加权融合            |
| 重排序          | CrossEncoder 等模型重新排序结果 |
| 查询扩展        | 扩展查询词提升召回率            |

### 使用示例

```python
from src.data.vector_store import vector_store

# 添加文档
await vector_store.add_document(
    user_id="user123",
    content="文档内容",
    metadata={"source": "web", "title": "文档标题"}
)

# 搜索（可启用高级检索）
results = vector_store.search(
    query="搜索关键词",
    user_id="user123",
    k=5,
    use_advanced=True
)
```

---

## 日志系统

日志按模块和级别拆分：

| 日志文件        | 内容                                  |
| --------------- | ------------------------------------- |
| `api.log`     | API请求日志，包含请求ID、用户ID       |
| `model.log`   | 模型调用日志，包含耗时、令牌数        |
| `im.log`      | IM消息日志，包含消息路由、推送        |
| `engine.log`  | 引擎日志，包含技能执行、学习循环      |
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

# 测试 MCP Server
python test_mcp_server.py
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

### Q: 文档搜索功能如何使用

A: 文档搜索功能已实现，基于向量数据库进行语义搜索：

```bash
GET /api/v1/document/search?query=关键词&limit=5&user_id=user123
```

## 许可证

MIT License

## 更新日志

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
