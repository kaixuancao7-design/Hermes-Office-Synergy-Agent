from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    OLLAMA_HOST: str = "http://localhost:11434"
    ZHIPU_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    MOONSHOT_API_KEY: Optional[str] = None
    
    DATABASE_PATH: str = "./data/agent.db"
    VECTOR_DB_PATH: str = "./data/vectors"
    
    PORT: int = 3000
    HOST: str = "0.0.0.0"
    
    ALLOWED_ORIGINS: str = "*"
    MAX_FILE_SIZE: int = 52428800
    
    LOG_LEVEL: str = "DEBUG"
    
    # 插件配置
    IM_ADAPTER_TYPE: str = "feishu"  # feishu, dingtalk, wecom, slack, discord
    MODEL_ROUTER_TYPE: str = "ollama"  # ollama, openai, anthropic, zhipu, moonshot, multi
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
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
