from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    OLLAMA_HOST: str = "http://localhost:11434"
    ZHIPU_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    
    DATABASE_PATH: str = "./data/agent.db"
    VECTOR_DB_PATH: str = "./data/vectors"
    
    PORT: int = 3000
    HOST: str = "0.0.0.0"
    
    ALLOWED_ORIGINS: str = "*"
    MAX_FILE_SIZE: int = 52428800
    
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
