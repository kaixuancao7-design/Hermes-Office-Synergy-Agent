"""插件抽象基类定义 - 遵循HERMES.md原则"""
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

# 插件白名单配置（遵循HERMES.md安全原则）
PLUGIN_WHITELIST = {
    'im_adapters': ['feishu', 'dingtalk', 'wecom', 'wechat', 'slack', 'discord'],
    'model_routers': ['openai', 'anthropic', 'ollama', 'zhipu', 'moonshot'],
    'memory_stores': ['chroma', 'milvus', 'faiss'],
    'skill_managers': ['default'],
    'tool_executors': ['default']
}

# 危险工具列表（需要管理员授权）
HAZARDOUS_TOOLS = ['file_delete', 'system_command', 'network_scan', 'data_export']


class PluginSecurityManager:
    """插件安全管理器 - 负责白名单校验和权限预检查"""
    
    @staticmethod
    def is_plugin_whitelisted(plugin_type: str, plugin_name: str) -> bool:
        """
        检查插件是否在白名单中
        
        Args:
            plugin_type: 插件类型（im_adapters, model_routers, memory_stores, etc.）
            plugin_name: 插件名称
        
        Returns:
            是否在白名单中
        """
        allowed_plugins = PLUGIN_WHITELIST.get(plugin_type, [])
        return plugin_name.lower() in allowed_plugins
    
    @staticmethod
    def check_tool_permission(user_id: str, tool_id: str) -> bool:
        """
        检查用户是否有权限执行工具
        
        Args:
            user_id: 用户ID
            tool_id: 工具ID
        
        Returns:
            是否有权限
        """
        from src.services.permission_service import permission_service
        
        # 危险工具需要管理员授权
        if tool_id in HAZARDOUS_TOOLS:
            user_role = permission_service.get_user_role(user_id)
            return user_role and user_role.role == 'admin'
        
        # 普通工具检查execute权限
        result = permission_service.check_tool_permission(user_id, tool_id, 'execute')
        return result.allowed
    
    @staticmethod
    def validate_plugin_config(plugin_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证插件配置的安全性
        
        Args:
            plugin_type: 插件类型
            config: 插件配置
        
        Returns:
            验证结果，包含是否通过和警告信息
        """
        issues = []
        warnings = []
        
        # 检查敏感信息
        sensitive_keys = ['password', 'secret', 'token', 'key']
        for key in sensitive_keys:
            if key in config:
                value = config[key]
                if isinstance(value, str) and len(value) > 0:
                    warnings.append(f"配置包含敏感信息: {key}")
        
        # 检查危险配置
        if plugin_type == 'im_adapters':
            if config.get('webhook_url'):
                warnings.append("使用Webhook可能存在安全风险")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }


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
    
    async def send_file(self, user_id: str, file_path: str, file_name: str = None) -> bool:
        """
        发送文件
        
        Args:
            user_id: 用户ID
            file_path: 文件路径
            file_name: 文件名（可选）
        
        Returns:
            是否发送成功
        """
        logger = get_logger("im")
        logger.warning(f"send_file not implemented for adapter type: {self.get_adapter_type()}")
        return False
    
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
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        """更新记忆条目"""
        pass
    
    @abstractmethod
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆（语义相似性检索）"""
        pass
    
    @abstractmethod
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        """获取单个记忆条目"""
        pass
    
    @abstractmethod
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        pass
    
    @abstractmethod
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        """获取用户所有记忆"""
        pass
    
    @abstractmethod
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def clear_memory(self, user_id: str) -> bool:
        """清空用户所有记忆"""
        pass
    
    @abstractmethod
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        """按类型清空用户记忆"""
        pass
    
    @abstractmethod
    def get_memory_count(self, user_id: str) -> int:
        """获取用户记忆数量"""
        pass
    
    @abstractmethod
    def get_memory_type(self) -> str:
        """获取存储类型"""
        pass
    
    @abstractmethod
    def persist(self) -> bool:
        """持久化存储（如果需要）"""
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
