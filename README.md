# Hermes Office Synergy Agent

基于 Hermes Agent 的智能办公协同助手，具备长期记忆、技能自动沉淀与跨端执行能力。

## 架构设计

系统采用五层架构设计：

1. **基础设施层**：模型路由、安全沙箱
2. **数据与记忆层**：向量库、SQLite存储、记忆架构
3. **核心引擎层**：意图识别、任务规划、记忆管理、学习循环
4. **技能与工具层**：技能库、工具箱
5. **交互网关层**：IM适配器、消息路由

## 快速开始

### 环境要求

- Python 3.10+
- pip 20.0+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 API 密钥等参数。

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

### 环境变量配置

```env
FEISHU_APP_ID=your-feishu-app-id
FEISHU_APP_SECRET=your-feishu-app-secret
FEISHU_BOT_NAME=Hermes
```

### 连接方式

系统使用 **WebSocket 长连接** 方式接收飞书事件，无需配置公网域名或加密策略。

## Ollama 配置

### 启动 Ollama 服务

```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型（例如 qwen3.5:9b）
ollama pull qwen3.5:9b
```

### 验证服务

```bash
curl http://localhost:11434/api/tags
```

## API 接口

### 发送消息

```bash
POST /api/v1/message
{
    "user_id": "user123",
    "content": "帮我生成周报",
    "metadata": {}
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

### IM Webhook（备用）

```bash
POST /api/v1/im/webhook/feishu
```

## 核心功能

### 记忆持久化

- 短期记忆：当前会话上下文
- 长期记忆：历史交互全文检索
- 程序性记忆：技能库

### 技能自动化

- 预置技能：会议纪要、数据图表、竞品分析等
- 用户自定义技能
- 自动习得技能（学习循环）

### 执行安全化

- Docker 沙箱执行
- 权限管控
- 路径白名单

## 支持的 IM 平台

- 飞书（WebSocket 长连接）
- 钉钉
- 企业微信
- 微信
- Slack
- Discord

## 支持的模型

- OpenAI (GPT-4o)
- Claude (3.5 Sonnet)
- Ollama (本地部署)
- 智谱 (GLM-4)
- Kimi

## 项目结构

```
.
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py
│   ├── config.py
│   ├── data/
│   │   ├── database.py
│   │   └── vector_store.py
│   ├── engine/
│   │   ├── intent_recognition.py
│   │   ├── learning_cycle.py
│   │   ├── memory_manager.py
│   │   └── task_planner.py
│   ├── gateway/
│   │   ├── feishu_longpoll.py
│   │   ├── feishu_websocket.py
│   │   ├── im_adapter.py
│   │   └── message_router.py
│   ├── infrastructure/
│   │   ├── model_router.py
│   │   └── sandbox.py
│   ├── main.py
│   ├── skills/
│   │   └── skill_manager.py
│   ├── tools/
│   │   ├── office_tools.py
│   │   └── tool_executor.py
│   ├── types.py
│   └── utils.py
├── logs/
├── .env.example
├── .gitignore
├── requirements.txt
├── start.py
└── README.md
```

## 日志

日志文件位于 `logs/combined.log`，包含服务启动、消息处理、模型调用等详细信息。

## 常见问题

### Q: 飞书消息发送后未收到回复

A: 请检查：
1. Ollama 服务是否运行
2. 飞书 APP_ID 和 APP_SECRET 是否正确配置
3. 飞书应用是否已添加 `im.message.receive_v1` 事件订阅

### Q: 模型调用失败（404 错误）

A: 请确保 Ollama 服务正在运行：
```bash
ollama serve
```

### Q: 日志重复输出

A: 已修复，每个日志 handler 只会添加一次。

## 许可证

MIT License