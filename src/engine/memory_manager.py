"""记忆管理器模块"""
from typing import Dict, Any, Optional, List
from src.logging_config import get_logger
from src.plugins import get_memory_store
from src.types import MemoryEntry
from src.utils import generate_id, get_timestamp

logger = get_logger("engine")


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self):
        pass
    
    def store_memory(self, user_id: str, content: str, memory_type: str = "short") -> bool:
        """存储记忆"""
        memory_store = get_memory_store()
        if not memory_store:
            logger.warning("记忆存储插件不可用")
            return False
        
        try:
            memory_entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type=memory_type,
                content=content,
                timestamp=get_timestamp(),
                tags=[memory_type]
            )
            
            memory_store.store(f"{user_id}_{memory_type}_{get_timestamp()}", memory_entry)
            logger.debug(f"记忆存储成功: user_id={user_id}, type={memory_type}")
            return True
        
        except Exception as e:
            logger.error(f"记忆存储失败: {str(e)}")
            return False
    
    def retrieve_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """检索记忆"""
        memory_store = get_memory_store()
        if not memory_store:
            logger.warning("记忆存储插件不可用")
            return []
        
        try:
            results = memory_store.search_memory(user_id, query, limit)
            logger.debug(f"记忆检索完成: user_id={user_id}, results={len(results)}")
            return results
        
        except Exception as e:
            logger.error(f"记忆检索失败: {str(e)}")
            return []
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        memory_store = get_memory_store()
        if not memory_store:
            logger.warning("记忆存储插件不可用")
            return False
        
        try:
            result = memory_store.delete(f"{user_id}_{memory_id}")
            logger.debug(f"记忆删除: user_id={user_id}, memory_id={memory_id}, result={result}")
            return result
        
        except Exception as e:
            logger.error(f"记忆删除失败: {str(e)}")
            return False
    
    def get_user_memories(self, user_id: str, memory_type: Optional[str] = None) -> List[MemoryEntry]:
        """获取用户记忆列表"""
        memory_store = get_memory_store()
        if not memory_store:
            logger.warning("记忆存储插件不可用")
            return []
        
        try:
            # 简化实现：实际应该根据类型筛选
            return []
        
        except Exception as e:
            logger.error(f"获取记忆列表失败: {str(e)}")
            return []


# 全局实例
memory_manager = MemoryManager()
