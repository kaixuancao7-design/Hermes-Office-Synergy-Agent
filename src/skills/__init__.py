"""技能模块 - 提供技能注册、触发匹配和编排能力"""

# 导入核心组件
from src.skills.manager import SkillManager, skill_manager
from src.skills.triggers import SkillTriggerMatcher, trigger_matcher
from src.skills.workflow import SkillWorkflowEngine, SkillWorkflowStep, create_ppt_workflow
from src.skills.intent import IntentModel, ContextualIntentAnalyzer, intent_model, contextual_analyzer

# 导入技能类型
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
    "SkillWorkflowEngine",
    "SkillWorkflowStep",
    "IntentModel",
    "ContextualIntentAnalyzer",
    
    # 全局实例
    "skill_manager",
    "trigger_matcher",
    "intent_model",
    "contextual_analyzer",
    
    # 技能管理器
    "PresetSkillsManager",
    "preset_skills_manager",
    "CustomSkillsManager",
    "custom_skills_manager",
    "LearnedSkillsManager",
    "learned_skills_manager",
    
    # 适配器
    "anthropics_adapter",
    "presentation_skill_adapter",
    
    # 工具函数
    "create_ppt_workflow"
]
