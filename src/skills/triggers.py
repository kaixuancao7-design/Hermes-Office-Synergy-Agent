"""技能触发匹配模块 - 根据用户输入匹配相关技能"""

from typing import List, Dict, Optional, Any
from src.types import Skill
from src.data.database import db
from src.logging_config import get_logger
from src.services.permission_service import permission_service

logger = get_logger("skill")


class SkillTriggerMatcher:
    """技能触发匹配器 - 根据用户查询匹配相关技能"""

    def __init__(self):
        # 缓存技能列表（定期刷新）
        self._skills_cache = []
        self._cache_timestamp = 0

    def _refresh_cache(self):
        """刷新技能缓存"""
        self._skills_cache = db.get_all_skills()
        self._cache_timestamp = self._get_current_time()

    def _get_current_time(self):
        """获取当前时间戳"""
        import time
        return int(time.time())

    def _is_cache_stale(self):
        """检查缓存是否过期（超过5分钟）"""
        return (self._get_current_time() - self._cache_timestamp) > 300

    def find_relevant_skill(self, query: str, user_id: Optional[str] = None) -> Optional[Skill]:
        """查找相关技能"""
        # 刷新缓存
        if self._is_cache_stale():
            self._refresh_cache()

        # 过滤用户有权限访问的技能
        available_skills = self._filter_available_skills(user_id)

        # 匹配触发模式
        matches = self._match_trigger_patterns(query, available_skills)

        if not matches:
            return None

        # 选择最佳匹配
        return self._select_best_match(query, matches)

    def _filter_available_skills(self, user_id: Optional[str]) -> List[Skill]:
        """过滤用户有权限访问的技能"""
        if not user_id:
            return self._skills_cache

        # 获取用户角色
        user_role = permission_service.get_user_role(user_id)

        # 管理员可以访问所有技能
        if user_role and user_role.role == "admin":
            return self._skills_cache

        # 普通用户可以访问预设技能、自己创建的技能或被授权的技能
        available = []
        for skill in self._skills_cache:
            # 预设技能对所有用户可用
            if skill.type == "preset":
                available.append(skill)
                continue

            # 检查是否是自己创建的
            if skill.created_by == user_id:
                available.append(skill)
                continue

            # 检查是否有读取权限
            permission = permission_service.check_skill_permission(user_id, skill.id, "read")
            if permission.allowed:
                available.append(skill)

        return available

    def _match_trigger_patterns(self, query: str, skills: List[Skill]) -> List[Dict[str, Any]]:
        """匹配触发模式"""
        matches = []
        query_lower = query.lower()

        for skill in skills:
            for pattern in skill.trigger_patterns:
                pattern_lower = pattern.lower()
                # 检查模式是否在查询中
                if pattern_lower in query_lower:
                    matches.append({
                        "skill": skill,
                        "pattern": pattern,
                        "match_position": query_lower.find(pattern_lower),
                        "pattern_length": len(pattern)
                    })

        return matches

    def _select_best_match(self, query: str, matches: List[Dict[str, Any]]) -> Optional[Skill]:
        """选择最佳匹配的技能"""
        if not matches:
            return None

        # 按匹配位置和模式长度排序
        # 优先选择匹配位置靠前且模式较长的技能
        sorted_matches = sorted(matches, key=lambda x: (x["match_position"], -x["pattern_length"]))

        # 返回第一个匹配的技能
        return sorted_matches[0]["skill"]

    def find_all_relevant_skills(self, query: str, user_id: Optional[str] = None) -> List[Skill]:
        """查找所有相关技能（按匹配度排序）"""
        if self._is_cache_stale():
            self._refresh_cache()

        available_skills = self._filter_available_skills(user_id)
        matches = self._match_trigger_patterns(query, available_skills)

        # 按匹配度排序
        matches.sort(key=lambda x: (x["match_position"], -x["pattern_length"]))

        # 去重（同一个技能可能有多个匹配模式）
        seen_skills = set()
        result = []
        for match in matches:
            skill_id = match["skill"].id
            if skill_id not in seen_skills:
                seen_skills.add(skill_id)
                result.append(match["skill"])

        return result

    def suggest_skills(self, user_id: Optional[str] = None, limit: int = 5) -> List[Skill]:
        """推荐技能（根据用户使用历史或热门程度）"""
        if self._is_cache_stale():
            self._refresh_cache()

        available_skills = self._filter_available_skills(user_id)

        # 简单的推荐逻辑：按创建时间排序，返回最新的技能
        sorted_skills = sorted(available_skills, key=lambda s: s.created_at, reverse=True)

        return sorted_skills[:limit]

    def get_trigger_patterns(self, user_id: Optional[str] = None) -> List[str]:
        """获取用户可用的所有触发模式"""
        if self._is_cache_stale():
            self._refresh_cache()

        available_skills = self._filter_available_skills(user_id)

        patterns = []
        for skill in available_skills:
            patterns.extend(skill.trigger_patterns)

        return list(set(patterns))


# 全局实例
trigger_matcher = SkillTriggerMatcher()