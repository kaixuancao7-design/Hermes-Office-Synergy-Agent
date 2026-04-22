"""技能模块 - 提供技能管理、验证和触发功能

遵循HERMES.md四大核心原则：
1. Think Before Coding: 技能生成前必须进行假设澄清
2. Simplicity First: 技能保持极简，不过度设计
3. Surgical Changes: 精准修改，只做必要变更
4. Goal-Driven Execution: 目标可验证，测试闭环
"""

from .manager import SkillManager, skill_manager
from .preset_skills import PresetSkillsManager, preset_skills_manager
from .custom_skills import CustomSkillsManager, custom_skills_manager
from .learned_skills import LearnedSkillsManager, learned_skills_manager
from .triggers import SkillTriggerMatcher, trigger_matcher
from .validators import SkillValidator, skill_validator

__all__ = [
    'SkillManager',
    'skill_manager',
    'PresetSkillsManager',
    'preset_skills_manager',
    'CustomSkillsManager',
    'custom_skills_manager',
    'LearnedSkillsManager',
    'learned_skills_manager',
    'SkillTriggerMatcher',
    'trigger_matcher',
    'SkillValidator',
    'skill_validator'
]