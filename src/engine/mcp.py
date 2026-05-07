"""Model Context Protocol (MCP) - 标准化模型上下文协议
提供统一的上下文管理接口，支持跨模型、跨组件的上下文传递
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Generic, TypeVar
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json

from pydantic import BaseModel, Field

from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("mcp")

T = TypeVar('T')


class ContextScope(Enum):
    """上下文作用域"""
    GLOBAL = "global"
    USER = "user"
    SESSION = "session"
    REQUEST = "request"


class ContextType(Enum):
    """上下文类型"""
    REACT = "react"
    PPT_WORKFLOW = "ppt_workflow"
    IM = "im"
    TOOL = "tool"
    MEMORY = "memory"
    CUSTOM = "custom"


class ContextState(Enum):
    """上下文状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ContextMetadata:
    """上下文元数据"""
    context_id: str
    context_type: ContextType
    scope: ContextScope
    created_at: int
    updated_at: int
    state: ContextState
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    version: int = 1
    ttl: Optional[int] = None  # 过期时间（秒）


class MCPContext(ABC, Generic[T]):
    """MCP上下文基类 - 所有MCP上下文的抽象接口"""

    @abstractmethod
    def get_metadata(self) -> ContextMetadata:
        """获取上下文元数据"""
        pass

    @abstractmethod
    def get_data(self) -> T:
        """获取上下文数据"""
        pass

    @abstractmethod
    def set_data(self, data: T) -> None:
        """设置上下文数据"""
        pass

    @abstractmethod
    def serialize(self) -> str:
        """序列化为字符串"""
        pass

    @classmethod
    @abstractmethod
    def deserialize(cls, data: str) -> 'MCPContext[T]':
        """从字符串反序列化"""
        pass

    @abstractmethod
    def merge(self, other: 'MCPContext[T]') -> 'MCPContext[T]':
        """合并另一个上下文"""
        pass

    @abstractmethod
    def clone(self) -> 'MCPContext[T]':
        """克隆上下文"""
        pass


class BaseMCPContext(MCPContext[Dict[str, Any]]):
    """基础MCP上下文实现"""

    def __init__(
        self,
        context_type: ContextType,
        scope: ContextScope = ContextScope.REQUEST,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        self._data: Dict[str, Any] = {}
        self._metadata = ContextMetadata(
            context_id=generate_id(),
            context_type=context_type,
            scope=scope,
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            state=ContextState.ACTIVE,
            user_id=user_id,
            session_id=session_id
        )

    def get_metadata(self) -> ContextMetadata:
        return self._metadata

    def get_data(self) -> Dict[str, Any]:
        return self._data.copy()

    def set_data(self, data: Dict[str, Any]) -> None:
        self._data = data.copy()
        self._metadata.updated_at = get_timestamp()

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据项"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置数据项"""
        self._data[key] = value
        self._metadata.updated_at = get_timestamp()

    def has(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self._data

    def delete(self, key: str) -> bool:
        """删除数据项"""
        if key in self._data:
            del self._data[key]
            self._metadata.updated_at = get_timestamp()
            return True
        return False

    def clear(self) -> None:
        """清空数据"""
        self._data.clear()
        self._metadata.updated_at = get_timestamp()

    def update_state(self, state: ContextState) -> None:
        """更新状态"""
        self._metadata.state = state
        self._metadata.updated_at = get_timestamp()

    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag not in self._metadata.tags:
            self._metadata.tags.append(tag)
            self._metadata.updated_at = get_timestamp()

    def remove_tag(self, tag: str) -> bool:
        """移除标签"""
        if tag in self._metadata.tags:
            self._metadata.tags.remove(tag)
            self._metadata.updated_at = get_timestamp()
            return True
        return False

    def serialize(self) -> str:
        """序列化为JSON字符串"""
        payload = {
            "metadata": {
                "context_id": self._metadata.context_id,
                "context_type": self._metadata.context_type.value,
                "scope": self._metadata.scope.value,
                "created_at": self._metadata.created_at,
                "updated_at": self._metadata.updated_at,
                "state": self._metadata.state.value,
                "user_id": self._metadata.user_id,
                "session_id": self._metadata.session_id,
                "tags": self._metadata.tags,
                "version": self._metadata.version
            },
            "data": self._data
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def deserialize(cls, data: str) -> 'BaseMCPContext':
        """从JSON字符串反序列化"""
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise ValueError(f"无效的JSON格式: {str(e)}") from e
        
        try:
            metadata = payload["metadata"]
        except KeyError:
            logger.error("反序列化失败: 缺少metadata字段")
            raise ValueError("反序列化失败: 缺少metadata字段")
        
        # 解析上下文类型
        try:
            context_type = ContextType(metadata["context_type"])
        except (KeyError, ValueError) as e:
            logger.error(f"无效的context_type: {metadata.get('context_type')}")
            context_type = ContextType.CUSTOM
        
        # 解析作用域
        try:
            scope = ContextScope(metadata["scope"])
        except (KeyError, ValueError) as e:
            logger.error(f"无效的scope: {metadata.get('scope')}")
            scope = ContextScope.REQUEST
        
        ctx = cls(
            context_type=context_type,
            scope=scope,
            user_id=metadata.get("user_id"),
            session_id=metadata.get("session_id")
        )
        
        # 设置上下文ID
        try:
            ctx._metadata.context_id = metadata["context_id"]
        except KeyError:
            logger.warning("缺少context_id，使用自动生成的ID")
        
        # 设置时间戳
        try:
            ctx._metadata.created_at = int(metadata["created_at"])
        except (KeyError, ValueError):
            ctx._metadata.created_at = get_timestamp()
        
        try:
            ctx._metadata.updated_at = int(metadata["updated_at"])
        except (KeyError, ValueError):
            ctx._metadata.updated_at = get_timestamp()
        
        # 解析状态
        try:
            ctx._metadata.state = ContextState(metadata["state"])
        except (KeyError, ValueError) as e:
            logger.error(f"无效的state: {metadata.get('state')}")
            ctx._metadata.state = ContextState.ACTIVE
        
        # 设置标签和版本
        ctx._metadata.tags = metadata.get("tags", [])
        ctx._metadata.version = int(metadata.get("version", 1))
        
        # 设置数据
        ctx._data = payload.get("data", {})
        
        logger.debug(f"反序列化上下文成功: {ctx._metadata.context_id}")
        return ctx

    def merge(self, other: 'MCPContext[Dict[str, Any]]') -> 'BaseMCPContext':
        """合并另一个上下文"""
        merged = self.clone()
        other_data = other.get_data()
        
        for key, value in other_data.items():
            if key not in merged._data:
                merged._data[key] = value
            else:
                if isinstance(merged._data[key], dict) and isinstance(value, dict):
                    merged._data[key] = {**merged._data[key], **value}
                elif isinstance(merged._data[key], list) and isinstance(value, list):
                    merged._data[key] = merged._data[key] + value
                else:
                    merged._data[key] = value
        
        merged._metadata.updated_at = get_timestamp()
        return merged

    def clone(self) -> 'BaseMCPContext':
        """克隆上下文"""
        cloned = BaseMCPContext(
            context_type=self._metadata.context_type,
            scope=self._metadata.scope,
            user_id=self._metadata.user_id,
            session_id=self._metadata.session_id
        )
        cloned._metadata = ContextMetadata(
            context_id=self._metadata.context_id,
            context_type=self._metadata.context_type,
            scope=self._metadata.scope,
            created_at=self._metadata.created_at,
            updated_at=get_timestamp(),
            state=self._metadata.state,
            user_id=self._metadata.user_id,
            session_id=self._metadata.session_id,
            tags=self._metadata.tags.copy(),
            version=self._metadata.version
        )
        cloned._data = self._data.copy()
        return cloned

    def __repr__(self) -> str:
        return f"BaseMCPContext(id={self._metadata.context_id}, type={self._metadata.context_type.value})"


class MCPManager:
    """MCP上下文管理器 - 管理所有MCP上下文的生命周期"""

    def __init__(self):
        self._contexts: Dict[str, BaseMCPContext] = {}
        self._user_contexts: Dict[str, List[str]] = {}  # user_id -> [context_id]
        self._session_contexts: Dict[str, List[str]] = {}  # session_id -> [context_id]
        self._type_contexts: Dict[ContextType, List[str]] = {}  # type -> [context_id]
        logger.info("MCP管理器初始化完成")

    def create_context(
        self,
        context_type: ContextType,
        scope: ContextScope = ContextScope.REQUEST,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> BaseMCPContext:
        """创建新的MCP上下文"""
        ctx = BaseMCPContext(
            context_type=context_type,
            scope=scope,
            user_id=user_id,
            session_id=session_id
        )
        
        if initial_data:
            ctx.set_data(initial_data)
        
        self._contexts[ctx.get_metadata().context_id] = ctx
        
        if user_id:
            if user_id not in self._user_contexts:
                self._user_contexts[user_id] = []
            self._user_contexts[user_id].append(ctx.get_metadata().context_id)
        
        if session_id:
            if session_id not in self._session_contexts:
                self._session_contexts[session_id] = []
            self._session_contexts[session_id].append(ctx.get_metadata().context_id)
        
        if context_type not in self._type_contexts:
            self._type_contexts[context_type] = []
        self._type_contexts[context_type].append(ctx.get_metadata().context_id)
        
        logger.debug(f"创建MCP上下文: {ctx.get_metadata().context_id}, type={context_type.value}")
        return ctx

    def get_context(self, context_id: str) -> Optional[BaseMCPContext]:
        """根据ID获取上下文"""
        return self._contexts.get(context_id)

    def get_contexts_by_user(self, user_id: str, context_type: Optional[ContextType] = None) -> List[BaseMCPContext]:
        """获取用户的所有上下文（可按类型过滤）"""
        context_ids = self._user_contexts.get(user_id, [])
        contexts = [self._contexts[cid] for cid in context_ids if cid in self._contexts]
        
        if context_type:
            contexts = [ctx for ctx in contexts if ctx.get_metadata().context_type == context_type]
        
        return contexts

    def get_contexts_by_session(self, session_id: str) -> List[BaseMCPContext]:
        """获取会话的所有上下文"""
        context_ids = self._session_contexts.get(session_id, [])
        return [self._contexts[cid] for cid in context_ids if cid in self._contexts]

    def get_contexts_by_type(self, context_type: ContextType) -> List[BaseMCPContext]:
        """获取指定类型的所有上下文"""
        context_ids = self._type_contexts.get(context_type, [])
        return [self._contexts[cid] for cid in context_ids if cid in self._contexts]

    def update_context(self, context_id: str, data: Dict[str, Any]) -> bool:
        """更新上下文数据"""
        ctx = self._contexts.get(context_id)
        if ctx:
            ctx.set_data(data)
            logger.debug(f"更新MCP上下文: {context_id}")
            return True
        return False

    def delete_context(self, context_id: str) -> bool:
        """删除上下文"""
        ctx = self._contexts.get(context_id)
        if not ctx:
            return False
        
        metadata = ctx.get_metadata()
        
        del self._contexts[context_id]
        
        if metadata.user_id and metadata.user_id in self._user_contexts:
            if context_id in self._user_contexts[metadata.user_id]:
                self._user_contexts[metadata.user_id].remove(context_id)
        
        if metadata.session_id and metadata.session_id in self._session_contexts:
            if context_id in self._session_contexts[metadata.session_id]:
                self._session_contexts[metadata.session_id].remove(context_id)
        
        if metadata.context_type in self._type_contexts:
            if context_id in self._type_contexts[metadata.context_type]:
                self._type_contexts[metadata.context_type].remove(context_id)
        
        logger.debug(f"删除MCP上下文: {context_id}")
        return True

    def archive_context(self, context_id: str) -> bool:
        """归档上下文"""
        ctx = self._contexts.get(context_id)
        if ctx:
            ctx.update_state(ContextState.ARCHIVED)
            logger.debug(f"归档MCP上下文: {context_id}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理过期的上下文"""
        cleaned = 0
        current_time = get_timestamp()
        
        for context_id, ctx in list(self._contexts.items()):
            metadata = ctx.get_metadata()
            if metadata.ttl and (current_time - metadata.updated_at) > metadata.ttl:
                self.delete_context(context_id)
                cleaned += 1
        
        if cleaned > 0:
            logger.info(f"清理过期MCP上下文: {cleaned} 个")
        
        return cleaned

    def get_all_contexts(self) -> List[BaseMCPContext]:
        """获取所有上下文"""
        return list(self._contexts.values())

    def get_context_count(self) -> Dict[str, int]:
        """获取上下文统计"""
        return {
            "total": len(self._contexts),
            "user": len(self._user_contexts),
            "session": len(self._session_contexts),
            "types": {t.value: len(cids) for t, cids in self._type_contexts.items()}
        }


class MCPAdapter:
    """MCP适配器 - 适配现有上下文到MCP标准"""

    @staticmethod
    def adapt_react_state(react_state: Any, user_id: str) -> BaseMCPContext:
        """适配ReActState到MCP上下文"""
        ctx = mcp_manager.create_context(
            context_type=ContextType.REACT,
            scope=ContextScope.USER,
            user_id=user_id,
            initial_data={
                "user_query": react_state.user_query,
                "thoughts": [t.model_dump() for t in react_state.thoughts],
                "actions": [a.model_dump() for a in react_state.actions],
                "observations": [o.model_dump() for o in react_state.observations],
                "current_step": react_state.current_step,
                "is_completed": react_state.is_completed,
                "final_response": react_state.final_response
            }
        )
        return ctx

    @staticmethod
    def adapt_skill_execution_context(execution_ctx: Any, user_id: str) -> BaseMCPContext:
        """适配SkillExecutionContext到MCP上下文（Claude范式）"""
        ctx = mcp_manager.create_context(
            context_type=ContextType.PPT_WORKFLOW,
            scope=ContextScope.USER,
            user_id=user_id,
            initial_data={
                "skill_id": execution_ctx.skill_id,
                "execution_id": execution_ctx.execution_id,
                "input_data": execution_ctx.input_data,
                "output_data": execution_ctx.output_data,
                "current_step": execution_ctx.current_step,
                "tool_calls": execution_ctx.tool_calls,
                "status": execution_ctx.status.value if hasattr(execution_ctx.status, 'value') else str(execution_ctx.status),
                "error": execution_ctx.error
            }
        )
        return ctx

    @staticmethod
    def adapt_custom_data(data: Dict[str, Any], context_type: ContextType,
                         user_id: Optional[str] = None) -> BaseMCPContext:
        """适配自定义数据到MCP上下文"""
        return mcp_manager.create_context(
            context_type=context_type,
            scope=ContextScope.REQUEST,
            user_id=user_id,
            initial_data=data
        )


class ContextRegistry:
    """上下文注册表 - 统一管理所有类型的上下文

    提供统一的接口来管理：
    - MCP原生上下文 (BaseMCPContext)
    - 外部上下文 (ReActState, PPTWorkflowContext 等)
    """

    def __init__(self):
        self._mcp_contexts: Dict[str, BaseMCPContext] = {}
        self._external_contexts: Dict[str, Any] = {}
        self._context_aliases: Dict[str, str] = {}  # alias -> context_id
        self._type_registry: Dict[str, type] = {
            "react": object,
            "ppt_workflow": object,
        }
        logger.info("上下文注册表初始化完成")

    def register_mcp_context(self, ctx: BaseMCPContext) -> str:
        """注册MCP上下文"""
        ctx_id = ctx.get_metadata().context_id
        self._mcp_contexts[ctx_id] = ctx
        logger.debug(f"注册MCP上下文: {ctx_id}")
        return ctx_id

    def register_external_context(
        self,
        context_id: str,
        context: Any,
        context_type: ContextType,
        user_id: Optional[str] = None,
        alias: Optional[str] = None
    ) -> None:
        """注册外部上下文（ReActState、PPTWorkflowContext等）"""
        self._external_contexts[context_id] = {
            "context": context,
            "type": context_type,
            "user_id": user_id,
            "mcp_synced": False
        }

        if alias:
            self._context_aliases[alias] = context_id

        logger.debug(f"注册外部上下文: {context_id}, type={context_type.value}")

    def get_mcp_context(self, context_id: str) -> Optional[BaseMCPContext]:
        """获取MCP上下文"""
        return self._mcp_contexts.get(context_id)

    def get_external_context(self, context_id: str) -> Optional[Any]:
        """获取外部上下文"""
        entry = self._external_contexts.get(context_id)
        return entry["context"] if entry else None

    def get_context_by_alias(self, alias: str) -> Optional[Any]:
        """通过别名获取上下文"""
        context_id = self._context_aliases.get(alias)
        if not context_id:
            return None

        if context_id in self._mcp_contexts:
            return self._mcp_contexts[context_id]
        entry = self._external_contexts.get(context_id)
        return entry["context"] if entry else None

    def get_contexts_by_user(self, user_id: str) -> Dict[str, List[Any]]:
        """获取用户的所有上下文"""
        result = {"mcp": [], "external": []}

        for ctx in self._mcp_contexts.values():
            if ctx.get_metadata().user_id == user_id:
                result["mcp"].append(ctx)

        for entry in self._external_contexts.values():
            if entry["user_id"] == user_id:
                result["external"].append(entry["context"])

        return result

    def sync_to_mcp(self, context_id: str) -> Optional[BaseMCPContext]:
        """将外部上下文同步到MCP格式"""
        entry = self._external_contexts.get(context_id)
        if not entry:
            return None

        context = entry["context"]
        context_type = entry["type"]
        user_id = entry["user_id"]

        if context_type == ContextType.REACT:
            mcp_ctx = MCPAdapter.adapt_react_state(context, user_id or "")
        elif context_type == ContextType.PPT_WORKFLOW:
            mcp_ctx = MCPAdapter.adapt_skill_execution_context(context, user_id or "")
        else:
            mcp_ctx = MCPAdapter.adapt_custom_data(
                {"data": str(context)},
                context_type,
                user_id
            )

        entry["mcp_synced"] = True
        return self.register_mcp_context(mcp_ctx)

    def sync_from_mcp(self, mcp_context_id: str, target_context_id: str) -> bool:
        """从MCP上下文同步回外部上下文"""
        mcp_ctx = self._mcp_contexts.get(mcp_context_id)
        entry = self._external_contexts.get(target_context_id)

        if not mcp_ctx or not entry:
            return False

        data = mcp_ctx.get_data()
        context = entry["context"]

        if hasattr(context, 'user_query'):
            context.user_query = data.get("user_query", context.user_query)
        if hasattr(context, 'current_step'):
            context.current_step = data.get("current_step", context.current_step)
        if hasattr(context, 'is_completed'):
            context.is_completed = data.get("is_completed", context.is_completed)

        entry["mcp_synced"] = True
        return True

    def unregister_context(self, context_id: str) -> bool:
        """取消注册上下文"""
        if context_id in self._mcp_contexts:
            del self._mcp_contexts[context_id]
            logger.debug(f"注销MCP上下文: {context_id}")
            return True

        if context_id in self._external_contexts:
            del self._external_contexts[context_id]
            logger.debug(f"注销外部上下文: {context_id}")
            return True

        for alias, cid in list(self._context_aliases.items()):
            if cid == context_id:
                del self._context_aliases[alias]

        return False

    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计"""
        return {
            "mcp_contexts": len(self._mcp_contexts),
            "external_contexts": len(self._external_contexts),
            "aliases": len(self._context_aliases),
            "type_counts": {
                ct.value: sum(1 for e in self._external_contexts.values() if e["type"] == ct)
                for ct in ContextType
            }
        }


context_registry = ContextRegistry()


# 全局MCP管理器实例
mcp_manager = MCPManager()
