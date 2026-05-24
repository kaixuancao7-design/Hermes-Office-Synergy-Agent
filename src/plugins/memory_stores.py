"""记忆存储插件实现"""
from typing import Dict, Any, Optional, List
from src.plugins.base import MemoryBase
from src.config import settings
from src.logging_config import get_logger
from src.types import MemoryEntry
from src.utils import generate_id, get_timestamp

logger = get_logger("memory")


class InMemoryStore(MemoryBase):
    """内存记忆存储"""
    
    def __init__(self):
        self.store: Dict[str, Any] = {}
    
    def store(self, key: str, value: Any) -> bool:
        self.store[key] = value
        return True
    
    def retrieve(self, key: str) -> Optional[Any]:
        return self.store.get(key)
    
    def delete(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
            return True
        return False
    
    def get_memory_type(self) -> str:
        return "in_memory"


class RedisStore(MemoryBase):
    """Redis记忆存储"""
    
    def __init__(self):
        self._client = None
        self._connect()
    
    def _connect(self):
        try:
            import redis
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            # 测试连接
            self._client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {str(e)}")
            self._client = None
    
    def store(self, key: str, value: Any) -> bool:
        if not self._client:
            return False
        
        try:
            import json
            serialized = json.dumps(value)
            self._client.set(f"{settings.REDIS_PREFIX}{key}", serialized)
            return True
        except Exception as e:
            logger.error(f"Redis存储失败: {str(e)}")
            return False
    
    def retrieve(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        
        try:
            import json
            data = self._client.get(f"{settings.REDIS_PREFIX}{key}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis获取失败: {str(e)}")
            return None
    
    def delete(self, key: str) -> bool:
        if not self._client:
            return False
        
        try:
            self._client.delete(f"{settings.REDIS_PREFIX}{key}")
            return True
        except Exception as e:
            logger.error(f"Redis删除失败: {str(e)}")
            return False
    
    def get_memory_type(self) -> str:
        return "redis"


class HybridMemoryStore(MemoryBase):
    """混合记忆存储（短期用Redis，长期用数据库）"""
    
    def __init__(self):
        self.redis_store = RedisStore()
        self.db_store = None
        self._init_db()
    
    def _init_db(self):
        try:
            from src.data.database import db
            self.db_store = db
            logger.info("混合存储初始化成功")
        except Exception as e:
            logger.error(f"数据库存储初始化失败: {str(e)}")
    
    def store(self, key: str, value: Any) -> bool:
        # 短期存储到Redis
        if not self.redis_store.store(key, value):
            return False
        
        # 如果是长期记忆，同时存储到数据库
        if isinstance(value, dict) and value.get("type") == "long_term":
            if self.db_store:
                try:
                    entry = MemoryEntry(
                        id=generate_id(),
                        user_id=value.get("user_id", "unknown"),
                        type=value.get("type", "long_term"),
                        content=str(value.get("content", "")),
                        embedding=value.get("embedding"),
                        timestamp=get_timestamp(),
                        tags=value.get("tags", [])
                    )
                    self.db_store.save_memory(entry)
                except Exception as e:
                    logger.error(f"数据库存储失败: {str(e)}")
        
        return True
    
    def retrieve(self, key: str) -> Optional[Any]:
        # 先从Redis获取
        result = self.redis_store.retrieve(key)
        if result:
            return result
        
        # 如果Redis没有，尝试从数据库获取
        if self.db_store:
            try:
                # 这是一个简化的实现，实际应该根据key来查询
                pass
            except Exception as e:
                logger.error(f"数据库获取失败: {str(e)}")
        
        return None
    
    def delete(self, key: str) -> bool:
        # 从Redis删除
        if not self.redis_store.delete(key):
            return False
        
        # 如果需要，也从数据库删除（这里简化处理）
        return True
    
    def get_memory_type(self) -> str:
        return "redis_hybrid"


# 记忆存储注册表
MEMORY_STORE_REGISTRY = {
    "in_memory": InMemoryStore,
    "redis": RedisStore,
    "redis_hybrid": HybridMemoryStore
}
