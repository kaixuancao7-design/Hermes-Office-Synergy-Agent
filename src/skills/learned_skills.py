"""学习技能管理器"""
from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class LearnedSkillsManager:
    """学习生成技能管理器"""
    
    def __init__(self):
        pass
    
    def create_from_draft(self, user_id: str, draft_id: str) -> Optional[Skill]:
        """从草稿创建学习生成的技能"""
        try:
            # 简化实现：实际应该从数据库获取草稿
            draft = self._get_draft(draft_id)
            
            if not draft:
                return None
            
            skill = Skill(
                id=generate_id(),
                name=draft.get('name', '未命名技能'),
                description=draft.get('description', ''),
                type='learned',
                trigger_patterns=draft.get('trigger_patterns', []),
                steps=[SkillStep(**s) for s in draft.get('steps', [])],
                metadata=draft.get('metadata', {}),
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by=user_id,
                version='1.0.0'
            )
            
            db.save_skill(skill)
            
            logger.info(f"从草稿创建学习技能: {skill.name}")
            
            return skill
        
        except Exception as e:
            logger.error(f"创建学习技能失败: {str(e)}")
            return None
    
    def _get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取技能草稿"""
        return db.get_skill_draft(draft_id)


# 全局实例
learned_skills_manager = LearnedSkillsManager()
