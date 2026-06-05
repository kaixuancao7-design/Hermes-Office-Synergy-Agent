from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen3.5:9b"
    OLLAMA_MAX_TOKENS: int = 4096
    OLLAMA_TEMPERATURE: float = 0.7
    OLLAMA_TOP_P: float = 0.9
    OLLAMA_RETRY_COUNT: int = 3
    OLLAMA_TIMEOUT: int = 120
    ZHIPU_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    MOONSHOT_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_DEFAULT_MODEL: str = "deepseek-v4-pro"  # deepseek-v4-pro / deepseek-v4-flash

    DATABASE_PATH: str = "./data/agent.db"
    VECTOR_DB_PATH: str = "./data/vectors"
    
    PORT: int = 3000
    HOST: str = "0.0.0.0"
    
    ALLOWED_ORIGINS: str = "*"
    MAX_FILE_SIZE: int = 52428800
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    LOG_OUTPUTS: str = "console,file"  # console, file, json_file, syslog (逗号分隔)
    
    # 插件配置
    IM_ADAPTER_TYPE: str = "feishu"  # feishu, dingtalk, wecom, slack, discord
    MODEL_ROUTER_TYPE: str = "ollama"  # ollama, openai, anthropic, zhipu, moonshot, deepseek, multi
    MEMORY_STORE_TYPE: str = "redis_hybrid"  # chroma, simple, milvus, faiss, hybrid, redis_hybrid
    SKILL_MANAGER_TYPE: str = "hybrid"  # database, file, hybrid
    EMBEDDING_SERVICE_TYPE: str = "default"  # default, openai, ollama, sentence_transformer, zhipu, moonshot
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_PREFIX: str = "hermes:"
    
    # Milvus配置
    MILVUS_URI: Optional[str] = None  # 默认: http://localhost:19530
    MILVUS_TOKEN: Optional[str] = None
    TOOL_EXECUTOR_TYPE: str = "sandboxed"  # basic, sandboxed
    
    # 沙箱配置
    SANDBOX_ALLOWED_PATHS: Optional[str] = None
    SANDBOX_MAX_EXECUTION_TIME: int = 30
    
    # 飞书配置
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_BOT_NAME: str = "Hermes-Office-Synergy-Agent"
    FEISHU_CONNECTION_MODE: str = "websocket"
    
    # 钉钉配置
    DINGTALK_APP_KEY: Optional[str] = None
    DINGTALK_APP_SECRET: Optional[str] = None
    DINGTALK_TOKEN: Optional[str] = None
    
    # 企业微信配置
    WECOM_CORP_ID: Optional[str] = None
    WECOM_APP_SECRET: Optional[str] = None
    WECOM_AGENT_ID: Optional[str] = None
    
    # 微信配置（个人号）
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None
    
    # Slack 配置
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    
    # Discord 配置
    DISCORD_BOT_TOKEN: Optional[str] = None

    # 认证配置
    API_KEY_ENABLED: bool = False  # 设为 True 启用 API Key 认证
    API_KEYS: str = ""  # 逗号分隔的合法 API Key 列表（为空且启用时允许所有请求）

    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX_REQUESTS: int = 60  # 每个窗口期最大请求数
    RATE_LIMIT_WINDOW_SECONDS: int = 60  # 窗口期（秒）

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()