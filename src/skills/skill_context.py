"""Claude风格的技能执行上下文"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from src.utils import generate_id, get_timestamp


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SkillExecutionContext:
    """技能执行上下文"""
    execution_id: str
    skill_id: str
    user_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    created_at: int = field(default_factory=get_timestamp)
    updated_at: int = field(default_factory=get_timestamp)

    def set_input(self, key: str, value: Any):
        """设置输入数据"""
        self.input_data[key] = value
        self._update_timestamp()

    def get_input(self, key: str, default=None) -> Any:
        """获取输入数据"""
        return self.input_data.get(key, default)

    def set_output(self, key: str, value: Any):
        """设置输出数据"""
        self.output_data[key] = value
        self._update_timestamp()

    def get_output(self, key: str, default=None) -> Any:
        """获取输出数据"""
        return self.output_data.get(key, default)

    def add_tool_call(self, tool_name: str, parameters: Dict[str, Any], result: Any):
        """记录工具调用"""
        self.tool_calls.append({
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "timestamp": get_timestamp()
        })
        self._update_timestamp()

    def set_status(self, status: ExecutionStatus):
        """设置执行状态"""
        self.status = status
        self._update_timestamp()

    def set_error(self, error: str):
        """设置错误信息"""
        self.error = error
        self.status = ExecutionStatus.FAILED
        self._update_timestamp()

    def _update_timestamp(self):
        """更新时间戳"""
        self.updated_at = get_timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "skill_id": self.skill_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "current_step": self.current_step,
            "tool_calls": self.tool_calls,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def is_completed(self) -> bool:
        """检查是否完成"""
        return self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]

    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self.status == ExecutionStatus.PAUSED


class SkillExecutionManager:
    """技能执行管理器"""

    def __init__(self):
        self._executions: Dict[str, SkillExecutionContext] = {}

    def create_execution(self, skill_id: str, user_id: str, input_data: Dict[str, Any]) -> SkillExecutionContext:
        """创建执行上下文"""
        execution_id = generate_id()
        context = SkillExecutionContext(
            execution_id=execution_id,
            skill_id=skill_id,
            user_id=user_id,
            input_data=input_data
        )
        self._executions[execution_id] = context
        return context

    def get_execution(self, execution_id: str) -> Optional[SkillExecutionContext]:
        """获取执行上下文"""
        return self._executions.get(execution_id)

    def update_execution(self, execution_id: str, updates: Dict[str, Any]):
        """更新执行上下文"""
        context = self._executions.get(execution_id)
        if context:
            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)
            context._update_timestamp()

    def remove_execution(self, execution_id: str):
        """移除执行上下文"""
        if execution_id in self._executions:
            del self._executions[execution_id]

    def get_user_executions(self, user_id: str) -> List[SkillExecutionContext]:
        """获取用户的所有执行上下文"""
        return [
            ctx for ctx in self._executions.values()
            if ctx.user_id == user_id and not ctx.is_completed()
        ]


# 全局实例
skill_execution_manager = SkillExecutionManager()