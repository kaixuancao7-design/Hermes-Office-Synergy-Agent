# Hermes Office Synergy Agent

基于 Hermes Agent 架构的智能办公协同助手，具备长期记忆、技能自动沉淀与跨端执行能力。

## 核心特性

- **多模态交互**：支持飞书、钉钉、企业微信等主流 IM 平台
- **自我进化闭环**：通过用户反馈自动学习并沉淀技能
- **记忆持久化**：支持短期、长期、程序性记忆的分层存储
- **多模型支持**：兼容 OpenAI、Claude、Ollama、智谱、Kimi 等模型
- **安全沙箱**：代码执行隔离，确保运行安全

## 架构设计

系统采用五层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│  交互网关层 (Gateway)                                       │
│  IM适配器 / 消息路由 / WebSocket服务                          │
├─────────────────────────────────────────────────────────────┤
│  技能与工具层 (Skills & Tools)                               │
│  技能库 / 工具箱 / 工具执行器                                  │
├─────────────────────────────────────────────────────────────┤
│  核心引擎层 (Engine)                                         │
│  意图识别 / 任务规划 / 记忆管理 / 学习循环 / ReAct引擎          │
├─────────────────────────────────────────────────────────────┤
│  数据与记忆层 (Data & Memory)                                │
│  SQLite数据库 / Chroma向量库 / 记忆架构                        │
├─────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                 │
│  模型路由 / 安全沙箱 / 配置管理                                │
└─────────────────────────────────────────────────────────────┘
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

### 获取技能列表

```bash
GET /api/v1/skills
```

### 创建技能

```bash
POST /api/v1/skills
{
    "user_id": "user123",
    "name": "自定义技能",
    "description": "描述",
    "steps": [
        {"action": "execute", "parameters": {"instruction": "步骤1"}}
    ]
}
```

### 执行技能

```bash
POST /api/v1/skills/{skill_id}/execute?user_id=user123
```

### 搜索记忆

```bash
GET /api/v1/memory/search?user_id=user123&query=关键词
```

### 提交反馈（用于自我进化）

```bash
POST /api/v1/feedback
{
    "user_id": "user123",
    "original": "原始回复",
    "corrected": "修正后的回复",
    "context": "对话上下文"
}
```

## 自我进化闭环

系统通过学习循环实现自我进化：

1. **反馈捕获**：用户提交修正反馈
2. **差异分析**：对比原始输出与修正输出
3. **技能提炼**：通过 LLM 分析差异，提取可复用技能
4. **技能存储**：将学习到的技能保存到技能库
5. **自动应用**：后续任务自动匹配并使用学习到的技能

```
用户提问 → 生成响应 → 用户反馈修正 → 技能提炼 → 保存技能 → 下次自动匹配
```

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

## 项目结构

```
.
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py      # API端点定义
│   ├── config.py                 # 配置管理
│   ├── data/
│   │   ├── database.py           # SQLite数据库
│   │   └── vector_store.py       # Chroma向量库
│   ├── engine/
│   │   ├── intent_recognition.py # 意图识别
│   │   ├── learning_cycle.py     # 学习循环（自我进化）
│   │   ├── memory_manager.py     # 记忆管理
│   │   ├── react_engine.py       # ReAct推理引擎
│   │   └── task_planner.py       # 任务规划
│   ├── gateway/
│   │   ├── feishu_websocket.py   # 飞书WebSocket服务
│   │   ├── im_adapter.py         # IM适配器管理
│   │   └── message_router.py     # 消息路由
│   ├── infrastructure/
│   │   ├── model_router.py       # 模型路由
│   │   └── sandbox.py            # 安全沙箱
│   ├── main.py                   # FastAPI入口
│   ├── skills/
│   │   └── skill_manager.py      # 技能管理
│   ├── tools/
│   │   ├── office_tools.py       # 办公工具
│   │   └── tool_executor.py      # 工具执行器
│   ├── types.py                  # 类型定义
│   └── utils.py                  # 工具函数
├── tests/                        # 测试文件
│   ├── conftest.py               # 测试配置
│   ├── test_api.py               # API测试
│   ├── test_database.py          # 数据库测试
│   └── test_utils.py             # 工具函数测试
├── logs/                         # 日志目录
├── data/                         # 数据目录
├── .gitignore
├── requirements.txt
├── start.py                      # 启动脚本
└── README.md
```

## 技能架构

系统采用 **流程编排型技能架构**，支持三种技能类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `preset` | 预置技能 | 会议纪要、周报生成 |
| `custom` | 用户自定义 | 用户创建的工作流 |
| `learned` | 自动习得 | 通过学习循环获得 |

技能结构包含触发模式、步骤链、条件分支等完整流程定义。

## 运行测试

```bash
# 安装测试依赖
pip install pytest httpx

# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_database.py -v
```

## 日志

日志文件位于 `logs/combined.log`，包含：
- 服务启动信息
- 消息处理日志
- 模型调用记录
- 错误堆栈信息

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

A: 学习循环默认启用，当累计 5 条用户反馈后自动触发技能提炼。

## 许可证

MIT License
