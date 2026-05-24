"""插件系统基础模块 - 定义所有插件的基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class IMAdapterBase(ABC):
    """IM适配器基类"""
    
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
    
    def get_adapter_type(self) -> str:
        """获取适配器类型"""
        return self.__class__.__name__


class ModelRouterBase(ABC):
    """模型路由器基类"""
    
    @abstractmethod
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到合适的模型"""
        pass
    
    def get_router_type(self) -> str:
        """获取路由类型"""
        return self.__class__.__name__


class MemoryBase(ABC):
    """记忆存储基类"""
    
    @abstractmethod
    def store(self, key: str, value: Any) -> bool:
        """存储数据"""
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Optional[Any]:
        """获取数据"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除数据"""
        pass
    
    def get_memory_type(self) -> str:
        """获取记忆类型"""
        return self.__class__.__name__


class SkillManagerBase(ABC):
    """技能管理器基类"""
    
    @abstractmethod
    def get_all_skills(self) -> List[Any]:
        """获取所有技能"""
        pass
    
    @abstractmethod
    def get_skill(self, skill_id: str) -> Optional[Any]:
        """获取指定技能"""
        pass
    
    @abstractmethod
    def create_skill(self, skill_data: Dict[str, Any]) -> Any:
        """创建技能"""
        pass
    
    @abstractmethod
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Any:
        """更新技能"""
        pass
    
    @abstractmethod
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        pass
    
    def get_manager_type(self) -> str:
        """获取管理器类型"""
        return self.__class__.__name__


class ToolExecutorBase(ABC):
    """工具执行器基类"""
    
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
        """获取所有工具"""
        pass
    
    def get_executor_type(self) -> str:
        """获取执行器类型"""
        return self.__class__.__name__
