"""自定义技能管理器"""
from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class CustomSkillsManager:
    """自定义技能管理器"""
    
    def __init__(self):
        pass
    
    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]]) -> Skill:
        """创建自定义技能"""
        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type='custom',
            trigger_patterns=[],
            steps=[SkillStep(**s) for s in steps],
            metadata={},
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id,
            version='1.0.0'
        )
        
        db.save_skill(skill)
        
        logger.info(f"创建自定义技能: {name} by user {user_id}")
        
        return skill
    
    def update_custom_skill(self, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        """更新自定义技能"""
        skill = db.get_skill(skill_id)
        if not skill:
            return None
        
        if 'name' in updates:
            skill.name = updates['name']
        if 'description' in updates:
            skill.description = updates['description']
        if 'steps' in updates:
            skill.steps = [SkillStep(**s) for s in updates['steps']]
        if 'trigger_patterns' in updates:
            skill.trigger_patterns = updates['trigger_patterns']
        
        skill.updated_at = get_timestamp()
        
        # 更新版本
        parts = skill.version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            skill.version = f"{major}.{minor}.{patch}"
        
        db.save_skill(skill)
        
        return skill


# 全局实例
custom_skills_manager = CustomSkillsManager()
