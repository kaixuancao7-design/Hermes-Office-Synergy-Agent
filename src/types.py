from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel
from datetime import datetime


class UserProfile(BaseModel):
    id: str
    name: str
    role: str
    writing_style: str
    preferences: Dict[str, Any]
    created_at: int
    updated_at: int


class Message(BaseModel):
    id: str
    user_id: str
    content: str
    role: Literal['user', 'assistant', 'system']
    timestamp: int
    metadata: Optional[Dict[str, Any]] = None


class SkillStep(BaseModel):
    id: str
    action: str
    parameters: Dict[str, Any]
    next_step_id: Optional[str] = None
    condition: Optional[str] = None


class Skill(BaseModel):
    id: str
    name: str
    description: str
    type: Literal['preset', 'custom', 'learned']
    trigger_patterns: List[str]
    steps: List[SkillStep]
    metadata: Dict[str, Any]
    version: str = "1.0.0"
    created_at: int
    updated_at: int
    created_by: Optional[str] = None


class SkillVersion(BaseModel):
    """技能版本记录"""
    id: str
    skill_id: str
    version: str
    name: str
    description: str
    type: Literal['preset', 'custom', 'learned']
    trigger_patterns: List[str]
    steps: List[SkillStep]
    metadata: Dict[str, Any]
    created_by: Optional[str]
    created_at: int
    change_type: Literal['create', 'update', 'rollback']
    change_note: Optional[str] = None


class SkillChangeLog(BaseModel):
    """技能修改日志"""
    id: str
    skill_id: str
    version: str
    changed_by: str
    changed_at: int
    change_type: Literal['create', 'update', 'delete', 'rollback']
    change_description: str
    previous_version: Optional[str] = None
    new_version: Optional[str] = None


class UserRole(BaseModel):
    """用户角色"""
    user_id: str
    role: Literal['admin', 'user', 'guest']
    created_at: int


class SkillPermission(BaseModel):
    """技能权限"""
    id: str
    skill_id: str
    user_id: str
    permission: Literal['read', 'execute', 'edit', 'delete', 'grant']
    granted_by: str
    granted_at: int


class PermissionCheckResult(BaseModel):
    """权限检查结果"""
    allowed: bool
    missing_permissions: List[str]


class ToolParameter(BaseModel):
    name: str
    type: Literal['string', 'number', 'boolean', 'file', 'array']
    required: bool
    description: str


class Tool(BaseModel):
    id: str
    name: str
    description: str
    type: Literal['api', 'local', 'browser', 'rpa']
    parameters: List[ToolParameter]
    returns: str


class MemoryEntry(BaseModel):
    id: str
    user_id: str
    type: Literal['short', 'long', 'procedural']
    content: str
    embedding: Optional[List[float]] = None
    timestamp: int
    tags: List[str]


class TaskStep(BaseModel):
    id: str
    description: str
    status: Literal['pending', 'in_progress', 'completed', 'failed']
    tool_call: Optional['ToolCall'] = None
    result: Optional[str] = None
    error: Optional[str] = None


class Task(BaseModel):
    id: str
    user_id: str
    goal: str
    status: Literal['pending', 'in_progress', 'completed', 'failed']
    steps: List[TaskStep]
    created_at: int
    updated_at: int


class ToolCall(BaseModel):
    tool_id: str
    parameters: Dict[str, Any]


class Intent(BaseModel):
    type: str
    confidence: float
    entities: Dict[str, str]


class ModelRoute(BaseModel):
    model: str
    provider: Literal['openai', 'claude', 'ollama', 'zhipu', 'kimi']
    endpoint: str
    api_key: Optional[str] = None
    capabilities: List[str]
    cost_per_token: float


class Session(BaseModel):
    id: str
    user_id: str
    context: List[Message]
    created_at: int
    last_active_at: int


class IMAdapterConfig(BaseModel):
    type: Literal['feishu', 'dingtalk', 'wecom', 'wechat', 'slack', 'discord']
    enabled: bool
    config: Dict[str, Any]


class SkillDraft(BaseModel):
    """技能草稿"""
    id: str
    skill_name: str
    description: str
    trigger_patterns: List[str]
    steps: List[SkillStep]
    original_context: str
    original_output: str
    corrected_output: str
    user_intent: str
    user_id: str
    created_at: int
    status: Literal['draft', 'pending_review', 'approved', 'rejected']
    review_comments: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[int] = None


class VerificationResult(BaseModel):
    """验证结果"""
    skill_draft_id: str
    verified: bool
    verification_type: Literal['auto', 'manual']
    confidence: float
    feedback: str
    similar_tasks: List[Dict[str, Any]]
    execution_comparison: Optional[Dict[str, float]] = None
    verified_at: int
    verified_by: Optional[str] = None


class CorrectionAnalysis(BaseModel):
    """差异分析结果"""
    original_output: str
    corrected_output: str
    differences: List[Dict[str, Any]]
    intent_match: float
    context_relevance: float
    actionable_steps: List[str]
    trigger_conditions: List[str]
    reusable_patterns: List[str]
