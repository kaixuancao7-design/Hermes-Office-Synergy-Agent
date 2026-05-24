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
    IM_ADAPTER_TYPE: str = "feishu"
    MODEL_ROUTER_TYPE: str = "ollama"
    MEMORY_STORE_TYPE: str = "in_memory"
    SKILL_MANAGER_TYPE: str = "hybrid"
    EMBEDDING_SERVICE_TYPE: str = "default"

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_PREFIX: str = "hermes:"

    # Milvus配置
    MILVUS_URI: Optional[str] = None
    MILVUS_TOKEN: Optional[str] = None
    TOOL_EXECUTOR_TYPE: str = "default"

    # 沙箱配置
    SANDBOX_ALLOWED_PATHS: Optional[str] = None
    SANDBOX_MAX_EXECUTION_TIME: int = 30

    # 飞书配置
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_VERIFICATION_TOKEN: Optional[str] = None
    FEISHU_ENCRYPT_KEY: Optional[str] = None

    # 向量数据库配置
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # PPT配置
    PPT_TEMPLATE_DIR: str = "./templates/ppt"
    PPT_OUTPUT_DIR: str = "./output/ppt"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()