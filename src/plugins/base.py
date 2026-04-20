"""插件抽象基类定义"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from src.types import Message, MemoryEntry, Skill
from src.exceptions import (
    IMException,
    ModelException,
    MemoryException,
    SkillException,
    ToolException
)


class IMAdapterBase(ABC):
    """IM适配器抽象基类"""
    
    @abstractmethod
    async def start(self) -> bool:
        """启动适配器"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """停止适配器"""
        pass
    
    @abstractmethod
    async def send_message(self, user_id: str, content: str) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    def get_adapter_type(self) -> str:
        """获取适配器类型"""
        pass


class ModelRouterBase(ABC):
    """模型路由抽象基类"""
    
    @abstractmethod
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择模型"""
        pass
    
    @abstractmethod
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用模型"""
        pass
    
    @abstractmethod
    def get_model_type(self) -> str:
        """获取模型类型"""
        pass


class MemoryBase(ABC):
    """记忆存储抽象基类"""
    
    @abstractmethod
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        """添加记忆条目"""
        pass
    
    @abstractmethod
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        pass
    
    @abstractmethod
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def clear_memory(self, user_id: str) -> bool:
        """清空用户记忆"""
        pass
    
    @abstractmethod
    def get_memory_type(self) -> str:
        """获取存储类型"""
        pass


class SkillManagerBase(ABC):
    """技能管理抽象基类"""
    
    @abstractmethod
    def add_skill(self, skill: Skill) -> bool:
        """添加技能"""
        pass
    
    @abstractmethod
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        pass
    
    @abstractmethod
    def get_all_skills(self) -> List[Skill]:
        """获取所有技能"""
        pass
    
    @abstractmethod
    def find_relevant_skill(self, query: str) -> Optional[Skill]:
        """查找相关技能"""
        pass
    
    @abstractmethod
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        pass
    
    @abstractmethod
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        pass
    
    @abstractmethod
    def get_manager_type(self) -> str:
        """获取管理器类型"""
        pass


class ToolExecutorBase(ABC):
    """工具执行抽象基类"""
    
    @abstractmethod
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        pass
    
    @abstractmethod
    def register_tool(self, tool_id: str, tool_class: Any) -> bool:
        """注册工具"""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[str]:
        """获取所有可用工具"""
        pass
    
    @abstractmethod
    def get_executor_type(self) -> str:
        """获取执行器类型"""
        pass
