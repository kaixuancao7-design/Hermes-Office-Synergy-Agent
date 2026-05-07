"""技能模块 - 提供技能注册、触发匹配和编排能力（Claude范式）"""

# 核心组件
from src.skills.manager import SkillManager, skill_manager
from src.skills.triggers import SkillTriggerMatcher, trigger_matcher
from src.skills.skill_parser import SkillParser, skill_parser

# Claude范式组件（主要执行引擎）
from src.skills.skill_loader import SkillLoader, skill_loader
from src.skills.skill_context import SkillExecutionContext, ExecutionStatus, SkillExecutionManager, skill_execution_manager
from src.skills.claude_executor import ClaudeSkillExecutor, claude_skill_executor

# 意图识别从 engine 模块导入（已合并）
from src.engine.intent_recognition import IntentRecognizer, ContextualIntentAnalyzer, intent_recognizer, contextual_analyzer

# 导入技能类型（保留用于向后兼容）
from src.skills.preset_skills import PresetSkillsManager, preset_skills_manager
from src.skills.custom_skills import CustomSkillsManager, custom_skills_manager
from src.skills.learned_skills import LearnedSkillsManager, learned_skills_manager

# 导入适配器
from src.skills.adapters.anthropics_adapter import anthropics_adapter
from src.skills.adapters.presentation_skill_adapter import presentation_skill_adapter

# 导出公共API
__all__ = [
    # 核心类
    "SkillManager",
    "SkillTriggerMatcher",
    "SkillParser",
    "IntentRecognizer",
    "ContextualIntentAnalyzer",
    
    # Claude范式组件
    "SkillLoader",
    "SkillExecutionContext",
    "ExecutionStatus",
    "SkillExecutionManager",
    "ClaudeSkillExecutor",
    
    # 全局实例
    "skill_manager",
    "trigger_matcher",
    "skill_parser",
    "intent_recognizer",
    "contextual_analyzer",
    "skill_loader",
    "skill_execution_manager",
    "claude_skill_executor",
    
    # 技能管理器（保留用于向后兼容）
    "PresetSkillsManager",
    "preset_skills_manager",
    "CustomSkillsManager",
    "custom_skills_manager",
    "LearnedSkillsManager",
    "learned_skills_manager",
    
    # 适配器
    "anthropics_adapter",
    "presentation_skill_adapter"
]
