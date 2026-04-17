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

编辑 `.env` 文件，配置API密钥等参数。

### 启动服务

```bash
python start.py
```

服务将在 http://localhost:3000 启动。

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

- Docker沙箱执行
- 权限管控
- 路径白名单

## 支持的IM平台

- 飞书
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
├── .env.example
├── requirements.txt
├── start.py
└── README.md
```

## 许可证

MIT License
