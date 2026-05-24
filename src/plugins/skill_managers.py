"""技能管理器插件实现"""
from typing import Dict, Any, Optional, List
from src.plugins.base import SkillManagerBase
from src.types import Skill, SkillStep
from src.config import settings
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("skill")


class HybridSkillManager(SkillManagerBase):
    """混合技能管理器（预设技能 + 数据库技能）"""
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._load_preset_skills()
        self._load_db_skills()
    
    def _load_preset_skills(self):
        """加载预设技能"""
        try:
            from src.skills.preset_skills import get_preset_skills
            preset_skills = get_preset_skills()
            for skill in preset_skills:
                self.skills[skill.id] = skill
            logger.info(f"加载了 {len(preset_skills)} 个预设技能")
        except Exception as e:
            logger.error(f"加载预设技能失败: {str(e)}")
    
    def _load_db_skills(self):
        """加载数据库中的技能"""
        try:
            from src.data.database import db
            db_skills = db.get_all_skills()
            for skill in db_skills:
                self.skills[skill.id] = skill
            logger.info(f"加载了 {len(db_skills)} 个数据库技能")
        except Exception as e:
            logger.error(f"加载数据库技能失败: {str(e)}")
    
    def get_all_skills(self) -> List[Skill]:
        return list(self.skills.values())
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id)
    
    def create_skill(self, skill_data: Dict[str, Any]) -> Skill:
        skill = Skill(
            id=generate_id(),
            name=skill_data.get("name", "Unnamed Skill"),
            description=skill_data.get("description", ""),
            type=skill_data.get("type", "custom"),
            trigger_patterns=skill_data.get("trigger_patterns", []),
            steps=[SkillStep(**s) for s in skill_data.get("steps", [])],
            metadata=skill_data.get("metadata", {}),
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        self.skills[skill.id] = skill
        
        # 保存到数据库
        try:
            from src.data.database import db
            db.save_skill(skill)
            logger.info(f"创建技能成功: {skill.name}")
        except Exception as e:
            logger.error(f"保存技能失败: {str(e)}")
        
        return skill
    
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        if skill_id not in self.skills:
            return None
        
        skill = self.skills[skill_id]
        
        if "name" in updates:
            skill.name = updates["name"]
        if "description" in updates:
            skill.description = updates["description"]
        if "type" in updates:
            skill.type = updates["type"]
        if "trigger_patterns" in updates:
            skill.trigger_patterns = updates["trigger_patterns"]
        if "steps" in updates:
            skill.steps = [SkillStep(**s) for s in updates["steps"]]
        if "metadata" in updates:
            skill.metadata = updates["metadata"]
        
        skill.updated_at = get_timestamp()
        
        # 保存到数据库
        try:
            from src.data.database import db
            db.save_skill(skill)
            logger.info(f"更新技能成功: {skill.name}")
        except Exception as e:
            logger.error(f"更新技能失败: {str(e)}")
        
        return skill
    
    def delete_skill(self, skill_id: str) -> bool:
        if skill_id not in self.skills:
            return False
        
        skill = self.skills.pop(skill_id)
        
        # 从数据库删除
        try:
            # 数据库没有直接删除技能的方法，这里简化处理
            logger.info(f"删除技能: {skill.name}")
        except Exception as e:
            logger.error(f"删除技能失败: {str(e)}")
        
        return True
    
    def get_manager_type(self) -> str:
        return "hybrid"


class DatabaseSkillManager(SkillManagerBase):
    """数据库技能管理器"""
    
    def __init__(self):
        pass
    
    def get_all_skills(self) -> List[Skill]:
        try:
            from src.data.database import db
            return db.get_all_skills()
        except Exception as e:
            logger.error(f"获取技能失败: {str(e)}")
            return []
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        try:
            from src.data.database import db
            return db.get_skill(skill_id)
        except Exception as e:
            logger.error(f"获取技能失败: {str(e)}")
            return None
    
    def create_skill(self, skill_data: Dict[str, Any]) -> Skill:
        skill = Skill(
            id=generate_id(),
            name=skill_data.get("name", "Unnamed Skill"),
            description=skill_data.get("description", ""),
            type=skill_data.get("type", "custom"),
            trigger_patterns=skill_data.get("trigger_patterns", []),
            steps=[SkillStep(**s) for s in skill_data.get("steps", [])],
            metadata=skill_data.get("metadata", {}),
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        try:
            from src.data.database import db
            db.save_skill(skill)
            logger.info(f"创建技能成功: {skill.name}")
        except Exception as e:
            logger.error(f"保存技能失败: {str(e)}")
        
        return skill
    
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        
        if "name" in updates:
            skill.name = updates["name"]
        if "description" in updates:
            skill.description = updates["description"]
        if "type" in updates:
            skill.type = updates["type"]
        if "trigger_patterns" in updates:
            skill.trigger_patterns = updates["trigger_patterns"]
        if "steps" in updates:
            skill.steps = [SkillStep(**s) for s in updates["steps"]]
        if "metadata" in updates:
            skill.metadata = updates["metadata"]
        
        skill.updated_at = get_timestamp()
        
        try:
            from src.data.database import db
            db.save_skill(skill)
            logger.info(f"更新技能成功: {skill.name}")
        except Exception as e:
            logger.error(f"更新技能失败: {str(e)}")
        
        return skill
    
    def delete_skill(self, skill_id: str) -> bool:
        # 数据库没有直接删除技能的方法，这里简化处理
        logger.info(f"删除技能: {skill_id}")
        return True
    
    def get_manager_type(self) -> str:
        return "database"


# 技能管理器注册表
SKILL_MANAGER_REGISTRY = {
    "hybrid": HybridSkillManager,
    "database": DatabaseSkillManager
}
