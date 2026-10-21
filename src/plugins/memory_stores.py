"""记忆存储插件实现"""
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from src.plugins.base import MemoryBase
from src.config import settings
from src.logging_config import get_logger
from src.types import MemoryEntry
from src.utils import generate_id, get_timestamp

logger = get_logger("memory")


class InMemoryStore(MemoryBase):
    """内存记忆存储"""
    
    def __init__(self):
        self._values: Dict[str, Any] = {}
    
    def store(self, key: str, value: Any) -> bool:
        self._values[key] = value
        return True
    
    def retrieve(self, key: str) -> Optional[Any]:
        return self._values.get(key)
    
    def delete(self, key: str) -> bool:
        if key in self._values:
            del self._values[key]
            return True
        return False
    
    def get_memory_type(self) -> str:
        return "in_memory"


class SimpleMemoryStore(MemoryBase):
    """SQLite-backed memory with user-scoped entries and general key/value storage."""
    def __init__(self, database=None):
        from src.data.database import db
        self.db = database or db
        with self._connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS memory_key_values (key TEXT PRIMARY KEY, payload TEXT NOT NULL, kind TEXT NOT NULL)")

    @contextmanager
    def _connection(self):
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def store(self, key, value):
        import json
        entry = value if isinstance(value, MemoryEntry) else None
        if isinstance(value, dict) and {"id", "user_id", "type", "content", "timestamp", "tags"} <= value.keys():
            entry = MemoryEntry.model_validate(value)
        payload = json.dumps(entry.model_dump() if entry else value, ensure_ascii=False)
        with self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO memory_key_values VALUES (?, ?, ?)",
                         (key, payload, "memory" if entry else "value"))
            if entry:
                conn.execute("""INSERT INTO memory (id,user_id,type,content,embedding,timestamp,tags,group_id,group_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET type=excluded.type,content=excluded.content,
                        embedding=excluded.embedding,timestamp=excluded.timestamp,tags=excluded.tags,
                        group_id=excluded.group_id,group_name=excluded.group_name
                    WHERE memory.user_id=excluded.user_id""", (entry.id, entry.user_id, entry.type,
                    entry.content, json.dumps(entry.embedding), entry.timestamp, json.dumps(entry.tags, ensure_ascii=False),
                    entry.group_id, entry.group_name))
                owner = conn.execute("SELECT user_id FROM memory WHERE id=?", (entry.id,)).fetchone()
                if owner[0] != entry.user_id:
                    raise PermissionError("Memory ID belongs to another user")
        return True

    def retrieve(self, key):
        import json
        with self._connection() as conn:
            row = conn.execute("SELECT payload,kind FROM memory_key_values WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        return MemoryEntry.model_validate(value) if row[1] == "memory" else value

    def delete(self, key):
        with self._connection() as conn:
            value = self.retrieve(key)
            if isinstance(value, MemoryEntry):
                return self.delete_memory(value.user_id, value.id)
            return conn.execute("DELETE FROM memory_key_values WHERE key=?", (key,)).rowcount > 0

    def add_memory(self, user_id, entry):
        entry = MemoryEntry.model_validate(entry)
        if entry.user_id != user_id:
            raise PermissionError("Memory user does not match the current user")
        return self.store(f"memory:{user_id}:{entry.id}", entry)

    @staticmethod
    def _entry(row):
        from src.data.database import _safe_deserialize
        return MemoryEntry(id=row[0], user_id=row[1], type=row[2], content=row[3],
            embedding=_safe_deserialize(row[4]), timestamp=row[5],
            tags=_safe_deserialize(row[6], []), group_id=row[7], group_name=row[8])

    def get_user_memories(self, user_id, memory_type=None):
        with self._connection() as conn:
            rows = conn.execute("SELECT id,user_id,type,content,embedding,timestamp,tags,group_id,group_name FROM memory WHERE user_id=?" +
                (" AND type=?" if memory_type else "") + " ORDER BY timestamp DESC,id", (user_id, memory_type) if memory_type else (user_id,)).fetchall()
        return [self._entry(row) for row in rows]

    def search_memory(self, user_id, query, limit=5, memory_type=None):
        if not user_id or not query.strip():
            return []
        terms = query.casefold().split()
        entries = self.get_user_memories(user_id, memory_type)
        scored = [(sum(entry.content.casefold().count(term) for term in terms), entry) for entry in entries]
        scored = [(score, entry) for score, entry in scored if score > 0]
        scored.sort(key=lambda item: (item[0], item[1].timestamp), reverse=True)
        return [entry for _, entry in scored[:max(0, min(limit, 100))]]

    def delete_memory(self, user_id, memory_id):
        import json
        with self._connection() as conn:
            changed = conn.execute("DELETE FROM memory WHERE user_id=? AND id=?", (user_id, memory_id)).rowcount
            for key, payload in conn.execute("SELECT key,payload FROM memory_key_values WHERE kind='memory'").fetchall():
                value = json.loads(payload)
                if value.get("id") == memory_id and value.get("user_id") == user_id:
                    conn.execute("DELETE FROM memory_key_values WHERE key=?", (key,))
        return changed > 0

    def get_memory_count(self, user_id):
        with self._connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM memory WHERE user_id=?", (user_id,)).fetchone()[0]

    def get_memory_type(self):
        return "simple"


class RedisStore(MemoryBase):
    """Redis记忆存储"""
    
    def __init__(self):
        self._client = None
        self._connect_timeout = 2
    
    def _connect(self):
        if self._client is not None:
            return
        
        try:
            import redis
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=self._connect_timeout,
                socket_connect_timeout=self._connect_timeout
            )
            self._client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {str(e)}")
            self._client = None
    
    def _ensure_connection(self):
        if self._client is None:
            self._connect()
    
    def store(self, key: str, value: Any) -> bool:
        self._ensure_connection()
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
        self._ensure_connection()
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
        self._ensure_connection()
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
    
    def add_memory(self, user_id: str, memory_entry: MemoryEntry) -> bool:
        """添加记忆条目（兼容message_router的调用）"""
        try:
            # 构建存储键
            key = f"memory:{user_id}:{memory_entry.id}"
            
            # 转换为字典格式存储
            value = {
                "user_id": memory_entry.user_id,
                "type": memory_entry.type,
                "content": memory_entry.content,
                "embedding": memory_entry.embedding,
                "timestamp": memory_entry.timestamp,
                "tags": memory_entry.tags,
                "group_id": memory_entry.group_id,
                "group_name": memory_entry.group_name
            }
            
            return self.store(key, value)
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            return False
    
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
    "simple": SimpleMemoryStore,
    "in_memory": InMemoryStore,
    "redis": RedisStore,
    "redis_hybrid": HybridMemoryStore
}
