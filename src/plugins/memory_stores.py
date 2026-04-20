"""记忆存储插件实现"""
import logging
from typing import Dict, Any, List, Optional

from src.plugins.base import MemoryBase
from src.types import MemoryEntry
from src.config import settings
from src.utils import generate_id, get_timestamp
from src.exceptions import MemoryException

logger = logging.getLogger("hermes_office_agent")


class ChromaMemory(MemoryBase):
    """Chroma向量数据库记忆存储"""
    
    def __init__(self):
        self.client = None
        self._initialize()
    
    def _initialize(self):
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.client = chromadb.Client(Settings(
                persist_directory=settings.VECTOR_DB_PATH,
                anonymized_telemetry=False
            ))
            
            # 创建或获取集合
            self.collections = {
                "short_term": self.client.get_or_create_collection("short_term"),
                "long_term": self.client.get_or_create_collection("long_term"),
                "user_preferences": self.client.get_or_create_collection("user_preferences")
            }
            
            logger.info("Chroma记忆存储初始化成功")
        except Exception as e:
            logger.error(f"Chroma记忆存储初始化失败: {str(e)}")
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        """添加记忆条目"""
        try:
            collection = self.collections.get(entry.type, self.collections["long_term"])
            
            if not entry.embedding:
                entry.embedding = [0.0] * 384
            
            collection.add(
                ids=[entry.id],
                documents=[entry.content],
                embeddings=[entry.embedding],
                metadatas=[{
                    "user_id": user_id,
                    "type": entry.type,
                    "timestamp": entry.timestamp,
                    "tags": ",".join(entry.tags) if entry.tags else ""
                }]
            )
            
            return True
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            raise MemoryException(
                message="添加记忆失败",
                detail=str(e),
                context={"user_id": user_id, "memory_type": entry.type}
            )
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆"""
        try:
            results = []
            
            # 在所有集合中搜索
            for collection_name, collection in self.collections.items():
                try:
                    result = collection.query(
                        query_texts=[query],
                        n_results=limit,
                        where={"user_id": user_id}
                    )
                    
                    for i, doc in enumerate(result["documents"][0]):
                        entry = MemoryEntry(
                            id=result["ids"][0][i],
                            user_id=user_id,
                            type=collection_name,
                            content=doc,
                            embedding=result["embeddings"][0][i] if result["embeddings"] else None,
                            timestamp=result["metadatas"][0][i].get("timestamp", get_timestamp()),
                            tags=result["metadatas"][0][i].get("tags", "").split(",") if result["metadatas"] else []
                        )
                        results.append(entry)
                except Exception as e:
                    logger.debug(f"搜索集合 {collection_name} 失败: {str(e)}")
            
            # 按时间戳排序
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"搜索记忆失败: {str(e)}")
            return []
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        try:
            collection = self.collections.get(memory_type)
            if not collection:
                return []
            
            result = collection.get(
                where={"user_id": user_id}
            )
            
            entries = []
            for i, doc in enumerate(result["documents"]):
                entry = MemoryEntry(
                    id=result["ids"][i],
                    user_id=user_id,
                    type=memory_type,
                    content=doc,
                    embedding=result["embeddings"][i] if result["embeddings"] else None,
                    timestamp=result["metadatas"][i].get("timestamp", get_timestamp()),
                    tags=result["metadatas"][i].get("tags", "").split(",") if result["metadatas"] else []
                )
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return []
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        try:
            for collection in self.collections.values():
                try:
                    collection.delete(ids=[memory_id])
                    return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"删除记忆失败: {str(e)}")
            return False
    
    def clear_memory(self, user_id: str) -> bool:
        """清空用户记忆"""
        try:
            for collection in self.collections.values():
                collection.delete(where={"user_id": user_id})
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def get_memory_type(self) -> str:
        return "chroma"


class SimpleMemory(MemoryBase):
    """简单内存记忆存储（用于测试和轻量级场景）"""
    
    def __init__(self):
        self.memories: Dict[str, List[MemoryEntry]] = {}
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        """添加记忆条目"""
        if user_id not in self.memories:
            self.memories[user_id] = []
        
        self.memories[user_id].append(entry)
        return True
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆"""
        if user_id not in self.memories:
            return []
        
        results = []
        for entry in self.memories[user_id]:
            if query.lower() in entry.content.lower():
                results.append(entry)
        
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        if user_id not in self.memories:
            return []
        
        results = [entry for entry in self.memories[user_id] if entry.type == memory_type]
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        if user_id not in self.memories:
            return False
        
        original_length = len(self.memories[user_id])
        self.memories[user_id] = [entry for entry in self.memories[user_id] if entry.id != memory_id]
        
        return len(self.memories[user_id]) < original_length
    
    def clear_memory(self, user_id: str) -> bool:
        """清空用户记忆"""
        if user_id in self.memories:
            self.memories[user_id] = []
            return True
        return False
    
    def get_memory_type(self) -> str:
        return "simple"


class HybridMemory(MemoryBase):
    """混合记忆存储（短期用内存，长期用向量库）"""
    
    def __init__(self):
        self.short_term = SimpleMemory()
        self.long_term = ChromaMemory()
        self.SHORT_TERM_LIMIT = 100  # 短期记忆最大条数
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        """添加记忆条目"""
        if entry.type == "short":
            # 短期记忆
            self.short_term.add_memory(user_id, entry)
            
            # 检查是否需要清理
            memories = self.short_term.get_memory_by_type(user_id, "short")
            if len(memories) > self.SHORT_TERM_LIMIT:
                # 将最早的一半移到长期记忆
                memories.sort(key=lambda x: x.timestamp)
                to_move = memories[:len(memories) // 2]
                
                for mem in to_move:
                    mem.type = "long"
                    self.long_term.add_memory(user_id, mem)
                    self.short_term.delete_memory(user_id, mem.id)
            
            return True
        else:
            # 长期记忆直接存储到向量库
            return self.long_term.add_memory(user_id, entry)
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆（优先短期，再搜索长期）"""
        short_results = self.short_term.search_memory(user_id, query, limit)
        remaining = limit - len(short_results)
        
        if remaining > 0:
            long_results = self.long_term.search_memory(user_id, query, remaining)
            short_results.extend(long_results)
        
        return short_results[:limit]
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        if memory_type == "short":
            return self.short_term.get_memory_by_type(user_id, memory_type)
        else:
            return self.long_term.get_memory_by_type(user_id, memory_type)
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        if self.short_term.delete_memory(user_id, memory_id):
            return True
        return self.long_term.delete_memory(user_id, memory_id)
    
    def clear_memory(self, user_id: str) -> bool:
        """清空用户记忆"""
        self.short_term.clear_memory(user_id)
        self.long_term.clear_memory(user_id)
        return True
    
    def get_memory_type(self) -> str:
        return "hybrid"


# 记忆存储注册表
MEMORY_STORE_REGISTRY = {
    "chroma": ChromaMemory,
    "simple": SimpleMemory,
    "hybrid": HybridMemory
}
