"""技能验证器"""
from typing import Dict, Any
from src.types import Skill
from src.logging_config import get_logger

logger = get_logger("skill")


class SkillValidator:
    """技能验证器"""
    
    def __init__(self):
        pass
    
    def check_complexity(self, skill: Skill) -> Dict[str, Any]:
        """检查技能复杂度"""
        complexity = {
            'level': 'low',
            'step_count': len(skill.steps),
            'has_loops': False,
            'has_branches': False,
            'estimated_execution_time': 'short'
        }
        
        if len(skill.steps) >= 5:
            complexity['level'] = 'medium'
        if len(skill.steps) >= 10:
            complexity['level'] = 'high'
        
        for step in skill.steps:
            if hasattr(step, 'parameters'):
                params = step.parameters
                if params.get('loop') or params.get('repeat'):
                    complexity['has_loops'] = True
                    complexity['level'] = 'high'
                if params.get('if') or params.get('condition'):
                    complexity['has_branches'] = True
        
        if complexity['level'] == 'high':
            complexity['estimated_execution_time'] = 'long'
        elif complexity['level'] == 'medium':
            complexity['estimated_execution_time'] = 'medium'
        
        return complexity
    
    def validate_skill_changes(self, original_skill: Skill, updated_skill: Skill, user_request: str) -> Dict[str, Any]:
        """验证技能变更"""
        result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'changes': []
        }
        
        # 检查步骤数量变化
        original_steps = len(original_skill.steps)
        updated_steps = len(updated_skill.steps)
        
        if updated_steps > original_steps * 2:
            result['warnings'].append("步骤数量增加超过100%")
        
        # 检查是否有破坏性变更
        if original_skill.type != updated_skill.type:
            result['warnings'].append("技能类型已变更")
        
        if original_skill.name != updated_skill.name:
            result['changes'].append(f"名称: {original_skill.name} -> {updated_skill.name}")
        
        return result


# 全局实例
skill_validator = SkillValidator()
