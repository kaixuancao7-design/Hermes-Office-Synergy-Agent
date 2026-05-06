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
- **PPT大纲生成与确认**：支持先生成大纲、用户确认后再生成PPT的完整工作流
- **飞书文件发送**：PPT生成完成后自动通过飞书API发送给用户
- **任务执行反思**：工具调用失败时自动分析原因并尝试修复（切换备用工具、重新生成参数）
- **细粒度意图识别**：支持PPT相关意图的精确区分（生成大纲、从大纲生成PPT、从内容生成PPT、自定义生成），实现意图到工具的精准映射
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
│  ReActEngine / 自我进化闭环 / 需求解析器 / IM触发器 / ContextualAnalyzer│
│  PPTWorkflow / TemplateMatcher / SpecLock / QualityGate / Strategist   │
│  MCPManager / ContextRegistry / MCPAdapter (Model Context Protocol)     │
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

### 消息路由流程

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
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  @机器人触发 │ │ 关键词触发  │ │ 附件触发    │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────┬───────┴───────┬───────┘
               │               │
               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐
    │   意图识别      │ │  文件解析       │
    │ (IntentRecog)   │ │ (FileParser)    │
    └───────┬─────────┘ └───────┬─────────┘
            │                   │
            └─────────┬─────────┘
                      │
                      ▼
            ┌─────────────────┐
            │   核心引擎处理  │
            │   (ReActEngine) │
            └─────────────────┘
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
| 上下文触发 | 基于历史对话理解 | `读取这个文件`、`根据刚才的内容生成PPT` |

### PPT生成工具

系统提供多种PPT生成工具：

- `generate_ppt`：直接生成PPT（不发送）
- `generate_and_send_ppt`：生成PPT并通过IM发送给用户
- `generate_ppt_outline`：仅生成PPT大纲
- `feishu_file_read`：读取飞书文件内容

### PPT Master工作流

系统引入**PPT Master**设计理念，实现规划-执行分离的PPT生成流程，包含大纲生成和确认环节：

```
用户请求 → 意图识别 → PPT工作流
                         │
                         ▼
                ┌───────────────┐
                │   模板匹配    │
                │ (Template)    │
                └───────┬───────┘
                        │ 用户确认设置
                        ▼
                ┌───────────────┐
                │   大纲生成    │
                │ (Outline)     │
                └───────┬───────┘
                        │ 用户确认/修改大纲
                        ▼
                ┌───────────────┐
                │   PPT生成    │
                │(Generator)   │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │  质量门控    │
                │(QualityGate) │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │  IM文件发送   │
                │(FileSender)  │
                └───────────────┘
```

#### 工作流状态机

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| `IDLE` | 空闲状态 | 初始状态 |
| `PLANNING` | 规划阶段 | 开始工作流 |
| `AWAITING_CONFIRMATION` | 等待设置确认 | 模板匹配完成 |
| `OUTLINE_BUILDING` | 大纲生成中 | 用户确认设置 |
| `OUTLINE_CONFIRMING` | 等待大纲确认 | 大纲生成完成 |
| `GENERATING` | PPT生成中 | 用户确认大纲 |
| `QUALITY_CHECKING` | 质量检查 | PPT生成完成 |
| `COMPLETED` | 完成 | 质量检查通过 |
| `FAILED` | 失败 | 任意步骤失败 |

#### 用户交互流程

1. **请求生成PPT** → 系统分析需求，匹配模板
2. **确认设置** → 用户回复"是"确认，或"详细"自定义
3. **预览大纲** → 系统生成大纲，用户预览
4. **确认大纲** → 用户回复"是"继续，或"修改+序号+内容"修改，或"重新生成"
5. **生成PPT** → 系统生成PPT并进行质量检查
6. **自动发送** → PPT生成完成后自动发送到IM

#### 支持的用户指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `是` / `确认` | 确认当前设置/大纲 | `是` |
| `详细` | 进入详细设置 | `详细` |
| `修改 N 内容` | 修改大纲第N项 | `修改 2 新标题` |
| `重新生成` | 重新生成大纲 | `重新生成` |

#### 核心组件

| 组件 | 功能 | 说明 |
|------|------|------|
| **TemplateMatcher** | 模板匹配 | 根据内容分析推荐最优模板（麦肯锡、学术、创意、简约等） |
| **SpecLock** | 规格锁定 | 锁定设计参数（颜色、字体、布局），防止上下文漂移 |
| **StrategistPlanner** | 策略规划 | 八项确认机制，确保用户需求准确理解 |
| **QualityGate** | 质量门控 | 自动检查PPT质量（结构、格式、字体安全） |

#### 设计原则

- **规划-执行分离**：需求分析输出design_spec，执行器严格按spec生成
- **多阶段确认**：复杂任务前增加用户确认环节（八项确认模板）
- **模板索引系统**：建立模板分类索引，支持内容匹配推荐
- **规格锁定机制**：生成过程中锁定设计参数，防止不一致
- **质量门控**：输出自动检查，错误必须修复才能继续

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
│   │   ├── vector_store.py           # 向量库（文档搜索核心）
│   │   ├── document_loader.py        # 文档加载与预处理
│   │   ├── version_manager.py        # 文档版本管理
│   │   ├── multimodal_processor.py  # 多模态处理（图片/音频/视频）
│   │   ├── advanced_retrieval.py     # 高级检索策略
│   │   ├── bm25_index.py            # BM25索引实现
│   │   └── reranker.py              # 重排序器实现
│   ├── engine/
│   │   ├── intent_recognition.py     # 意图识别（细粒度分类、上下文感知分析）
│   │   ├── learning_cycle.py         # 学习循环（三闸门验证）
│   │   ├── memory_manager.py         # 记忆管理
│   │   ├── react_engine.py           # ReAct推理引擎
│   │   ├── task_planner.py           # 任务规划
│   │   ├── demand_parser.py          # 需求解析器（PPT需求提取）
│   │   ├── im_trigger.py             # IM触发器（多模态触发）
│   │   ├── ppt_workflow.py          # PPT工作流（集成MCP）
│   │   └── mcp.py                   # MCP（Model Context Protocol）实现
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
│   │   ├── triggers.py               # 触发匹配器
│   │   └── adapters/                 # 外部技能适配器
│   ├── tools/
│   │   ├── base.py                   # 工具基类和接口
│   │   ├── registry.py               # 工具注册器
│   │   ├── ppt_generator.py          # PPT生成工具
│   │   ├── file_reader.py            # 文件读取工具
│   │   └── content_tools.py          # 内容处理工具
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
│   ├── test_react_engine_recovery.py # ReAct引擎恢复测试
│   └── test_mcp.py                   # MCP测试
├── verify_mcp.py                     # MCP验证脚本
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
| 意图 | 说明 | 示例 |
|------|------|------|
| `ppt_generate_outline` | 生成PPT大纲 | "帮我生成产品介绍大纲" |
| `ppt_generate` | 生成完整PPT | "生成产品介绍PPT" |
| `ppt_from_outline` | 从大纲生成PPT | "根据这个大纲生成PPT" |
| `ppt_from_content` | 从内容生成PPT | "根据文档内容生成PPT" |
| `summarization` | 文档总结 | "总结这份文档" |
| `read_file` | 文件读取 | "读取这个文件" |
| `document_search` | 文档搜索 | "搜索相关文档" |
| `memory_query` | 记忆查询 | "我之前说了什么" |
| `question_answering` | 问答 | "什么是人工智能" |
| `code_generation` | 代码生成 | "写一段Python代码" |

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

## Model Context Protocol (MCP)

### 核心概念

MCP 是标准的上下文管理协议，提供统一的上下文创建、更新、查询、序列化接口。

| 组件 | 说明 |
|------|------|
| `BaseMCPContext` | 基础上下文类，支持序列化/反序列化 |
| `MCPManager` | 上下文管理器，提供创建、查询、删除等操作 |
| `ContextRegistry` | 外部上下文注册表，统一管理不同类型上下文 |
| `ContextScope` | 作用域：GLOBAL、USER、SESSION、REQUEST |
| `ContextType` | 类型：REACT、PPT_WORKFLOW、IM、TOOL、MEMORY、CUSTOM |
| `ContextState` | 状态：ACTIVE、PAUSED、COMPLETED、FAILED、ARCHIVED |

### 核心功能

```python
from src.engine.mcp import mcp_manager, ContextType, ContextScope, ContextState

# 创建上下文
context = mcp_manager.create_context(
    context_type=ContextType.REACT,
    scope=ContextScope.USER,
    scope_id="user123",
    data={"query": "用户查询"}
)

# 更新上下文数据
context.set_data({"step": 1, "status": "in_progress"})

# 更新状态
context.update_state(ContextState.COMPLETED)

# 查询上下文
context = mcp_manager.get_context("context_id")

# 按用户查询
contexts = mcp_manager.get_contexts_by_user("user123")

# 序列化/反序列化
serialized = context.serialize()
restored = BaseMCPContext.deserialize(serialized)
```

### MCP 集成模块

| 模块 | 集成位置 |
|------|----------|
| ReAct 引擎 | `src/engine/react_engine.py` - `_update_mcp_context()` |
| PPT 工作流 | `src/engine/ppt_workflow.py` - `_update_mcp_context()` |

---

## RAG 增强系统

### 概述

高级检索系统，支持混合检索策略、重排序、查询扩展等功能。

### 核心组件

| 组件 | 说明 |
|------|------|
| `VectorStore` | 向量存储（基于 Chroma + LangChain） |
| `BM25Index` | BM25 关键词索引（SQLite 持久化） |
| `AdvancedRetrieval` | 高级检索管道 |
| `Reranker` | 重排序器（Linear、BM25、CrossEncoder） |
| `DocumentLoader` | 文档加载与预处理 |
| `VersionManager` | 文档版本管理 |

### 检索策略

| 策略 | 说明 |
|------|------|
| 向量相似度搜索 | 基于语义相似度的检索 |
| BM25 关键词搜索 | 基于关键词匹配的检索 |
| 混合检索 | 向量 + BM25 加权融合 |
| 重排序 | CrossEncoder 等模型重新排序结果 |
| 查询扩展 | 扩展查询词提升召回率 |

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
python -m pytest tests/test_mcp.py -v

# 验证 MCP 功能
python verify_mcp.py
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

### v1.0.2 (2026-05-03)

**新功能：**

1. **MCP (Model Context Protocol)**：实现了标准的上下文管理协议
   - 核心组件：`BaseMCPContext`、`MCPManager`、`ContextRegistry`、`MCPAdapter`
   - 支持多种上下文类型：REACT、PPT_WORKFLOW、IM、TOOL、MEMORY、CUSTOM
   - 支持多种作用域：GLOBAL、USER、SESSION、REQUEST
   - 完整的序列化/反序列化支持
   - 完善的错误处理机制

2. **RAG 增强系统**：实现了高级检索系统
   - BM25 关键词索引（SQLite 持久化）
   - 高级检索管道（过滤器 + 重排序）
   - 多种重排序策略：Linear、BM25、CrossEncoder、Hybrid
   - 查询扩展支持
   - 文档加载、版本管理、多模态处理

3. **MCP 集成**：在现有模块中集成 MCP
   - ReAct 引擎：完整的 MCP 上下文管理和状态更新
   - PPT 工作流：完整的 MCP 上下文管理和状态更新

**Bug修复：**

1. **MCP 状态映射不完整**：修复了 PPT 工作流状态到 MCP 状态的映射问题
   - 添加了所有 WorkflowState 的显式映射
   - 优化了代码结构，减少重复
   - 位置：`src/engine/ppt_workflow.py`

2. **测试注释不准确**：修正了 RAG 测试注释的描述
   - 位置：`tests/test_mcp.py`

**功能改进：**

1. **测试覆盖**：新增 MCP 测试用例
   - 基础上下文操作测试
   - 序列化/反序列化测试
   - 管理器操作测试
   - 合并和克隆测试

2. **验证脚本**：新增 MCP 验证脚本
   - `verify_mcp.py` 提供完整的功能演示

3. **错误处理**：增强 MCP 反序列化错误处理
   - JSON 解析错误捕获
   - 元数据缺失错误捕获
   - 无效类型/状态回退机制
