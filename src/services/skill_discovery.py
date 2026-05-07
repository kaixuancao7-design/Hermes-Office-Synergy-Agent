"""Claude风格的技能发现服务"""

from typing import List, Dict, Any, Optional
from src.types import Skill
from src.data.database import db
from src.logging_config import get_logger

logger = get_logger("skill.discovery")


class SkillDiscoveryService:
    """技能发现和推荐服务"""

    def __init__(self):
        self._skills = []
        self._index_skills()

    def _index_skills(self):
        """索引所有技能"""
        self._skills = db.get_all_skills()
        logger.info(f"已索引 {len(self._skills)} 个技能")

    def search_skills(self, query: str, top_k: int = 5) -> List[Skill]:
        """语义搜索技能"""
        if not query:
            return self._skills[:top_k]

        results = []
        query_lower = query.lower()

        for skill in self._skills:
            score = self._calculate_match_score(query_lower, skill)
            if score > 0:
                results.append((skill, score))

        # 按匹配度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in results[:top_k]]

    def _calculate_match_score(self, query_lower: str, skill: Skill) -> float:
        """计算匹配分数"""
        score = 0.0

        # 名称匹配（权重最高）
        if query_lower in skill.name.lower():
            score += 0.4

        # 描述匹配
        if query_lower in skill.description.lower():
            score += 0.3

        # 触发模式匹配
        for pattern in skill.trigger_patterns:
            if pattern.lower() in query_lower or query_lower in pattern.lower():
                score += 0.3
                break

        # 标签匹配
        tags = skill.metadata.get("tags", [])
        for tag in tags:
            if tag.lower() in query_lower or query_lower in tag.lower():
                score += 0.2
                break

        return min(score, 1.0)

    def recommend_skills(self, user_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> List[Skill]:
        """基于上下文推荐技能"""
        # 简化实现：返回所有预设技能
        return [skill for skill in self._skills if skill.type == "preset"][:5]

    def get_skill_by_tag(self, tag: str) -> List[Skill]:
        """按标签获取技能"""
        return [
            skill for skill in self._skills
            if tag in skill.metadata.get("tags", [])
        ]

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """根据名称获取技能"""
        for skill in self._skills:
            if skill.name == name:
                return skill
        return None

    def get_all_skills(self) -> List[Skill]:
        """获取所有技能"""
        return self._skills

    def get_skills_for_llm(self) -> List[Dict[str, Any]]:
        """获取技能列表（用于LLM格式）"""
        skills_info = []

        for skill in self._skills:
            skills_info.append({
                "name": skill.name,
                "description": skill.description,
                "triggers": skill.trigger_patterns,
                "tags": skill.metadata.get("tags", []),
                "input_schema": skill.metadata.get("input_schema", {})
            })

        return skills_info

    def refresh_index(self):
        """刷新技能索引"""
        self._index_skills()


# 全局实例
skill_discovery = SkillDiscoveryService()