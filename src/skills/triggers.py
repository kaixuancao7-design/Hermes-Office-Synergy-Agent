"""技能触发器匹配器"""
from typing import Dict, Any, Optional, List
from src.types import Skill
from src.data.database import db
from src.logging_config import get_logger

logger = get_logger("skill")


class TriggerMatcher:
    """触发器匹配器"""
    
    def __init__(self):
        pass
    
    def find_relevant_skill(self, query: str, user_id: Optional[str] = None) -> Optional[Skill]:
        """查找相关技能"""
        query_lower = query.lower()
        
        # 获取所有技能
        skills = db.get_all_skills()
        
        best_match = None
        best_score = 0
        
        for skill in skills:
            score = self._calculate_match_score(skill, query_lower)
            
            if score > best_score and score >= 0.3:
                best_score = score
                best_match = skill
        
        if best_match:
            logger.info(f"找到相关技能: {best_match.name}, 匹配度: {best_score}")

            # 记录 learned 技能的使用（为 Curator 评分提供数据）
            if best_match.type == "learned":
                try:
                    db.record_skill_usage(best_match.id, user_id or "unknown")
                except Exception:
                    pass  # 静默失败，不影响主流程

        return best_match
    
    def _calculate_match_score(self, skill: Skill, query: str) -> float:
        """计算匹配分数"""
        score = 0.0
        
        # 检查触发模式
        if skill.trigger_patterns:
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query:
                    score += 0.3
        
        # 检查技能名称
        if skill.name.lower() in query:
            score += 0.2
        
        # 检查描述
        if skill.description and skill.description.lower() in query:
            score += 0.1
        
        # 检查步骤中的关键词
        for step in skill.steps:
            if hasattr(step, 'parameters') and step.parameters:
                instruction = step.parameters.get('instruction', '')
                if instruction.lower() in query:
                    score += 0.1
        
        return min(score, 1.0)


class SkillTriggerMatcher(TriggerMatcher):
    """技能触发器匹配器（别名）"""
    pass


# 全局实例
trigger_matcher = TriggerMatcher()
