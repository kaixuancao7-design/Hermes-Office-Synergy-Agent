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
    created_at: int
    updated_at: int


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
