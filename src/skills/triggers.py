"""技能触发器匹配器 — Tier 1 轻量级匹配 + Tier 2 按需加载

设计原则:
  - Tier 1 (匹配阶段): 使用 SkillSummary 进行评分，不加载完整 Skill 对象
    SkillSummary 仅包含匹配所需的字段（trigger_patterns, name, description,
    step_instructions），内存占用为完整 Skill 的 1/5 ~ 1/10
  - Tier 2 (加载阶段): 确认匹配后，通过 load_full_skill() 按需加载完整 Skill
    仅在需要执行技能步骤时才加载 SkillStep 对象和 metadata
"""

from typing import Dict, Any, Optional, List, Tuple
from src.types import Skill, SkillSummary
from src.data.database import db
from src.logging_config import get_logger

logger = get_logger("skill")


class TriggerMatcher:
    """触发器匹配器 — 支持三层懒加载

    Tier 1: find_relevant_skill() 使用 SkillSummary 进行轻量级匹配
    Tier 2: load_full_skill() 按需加载完整 Skill 用于执行
    """

    def __init__(self):
        pass

    # =========================================================================
    # Tier 1: 轻量级匹配（仅使用 SkillSummary）
    # =========================================================================

    def find_relevant_skill(
        self, query: str, user_id: Optional[str] = None
    ) -> Optional[SkillSummary]:
        """Tier 1: 使用轻量级摘要查找最匹配的技能

        仅加载 SkillSummary（不含完整步骤对象），
        匹配评分所需的所有字段均已包含。
        匹配成功后调用 load_full_skill() 获取完整 Skill。

        Args:
            query: 用户查询
            user_id: 用户 ID（用于记录 learned 技能使用）

        Returns:
            最佳匹配的 SkillSummary，或 None
        """
        query_lower = query.lower()

        # Tier 1: 加载轻量级摘要（不反序列化完整 SkillStep）
        summaries = db.get_skills_summaries()

        best_match = None
        best_score = 0.0

        for summary in summaries:
            score = self._calculate_summary_score(summary, query_lower)

            if score > best_score and score >= 0.3:
                best_score = score
                best_match = summary

        if best_match:
            logger.info(
                f"[T1_MATCH] 找到相关技能: {best_match.name}, "
                f"匹配度: {best_score:.2f}, type={best_match.type}"
            )

            # 记录 learned 技能的使用（为 Curator 评分提供数据）
            if best_match.type == "learned":
                try:
                    db.record_skill_usage(best_match.id, user_id or "unknown")
                except Exception:
                    pass

        return best_match

    def find_relevant_skill_with_near_misses(
        self, query: str, user_id: Optional[str] = None
    ) -> Tuple[Optional[SkillSummary], List[Tuple[SkillSummary, float]]]:
        """Tier 1: 查找最佳匹配 + 接近匹配列表（用于渐进式披露建议）

        Args:
            query: 用户查询
            user_id: 用户 ID

        Returns:
            (best_match, near_misses) 元组:
              - best_match: 最高分技能摘要（score >= 0.5），或 None
              - near_misses: [(SkillSummary, score), ...] 列表，
                             包含 0.3 <= score < 0.5 的技能，
                             按分数降序排列，最多 3 个
        """
        query_lower = query.lower()

        # Tier 1: 加载轻量级摘要
        summaries = db.get_skills_summaries()

        best_match = None
        best_score = 0.0
        near_misses: List[Tuple[SkillSummary, float]] = []

        for summary in summaries:
            score = self._calculate_summary_score(summary, query_lower)

            if score >= 0.5 and score > best_score:
                best_score = score
                best_match = summary
            elif 0.3 <= score < 0.5:
                near_misses.append((summary, score))

        # 按分数降序排列，最多保留 3 个
        near_misses.sort(key=lambda x: x[1], reverse=True)
        near_misses = near_misses[:3]

        if best_match:
            logger.info(
                f"[T1_MATCH] 找到最佳匹配: {best_match.name} "
                f"(score={best_score:.2f}), near_misses={len(near_misses)}"
            )
            if best_match.type == "learned":
                try:
                    db.record_skill_usage(best_match.id, user_id or "unknown")
                except Exception:
                    pass

        return best_match, near_misses

    def _calculate_summary_score(
        self, summary: SkillSummary, query: str
    ) -> float:
        """基于 SkillSummary 计算匹配分数（与 _calculate_match_score 等效）

        评分规则（与完整 Skill 版本一致）:
          - 每个匹配的 trigger_pattern: +0.3
          - name 匹配: +0.2
          - description 匹配: +0.1
          - 每个匹配的 step_instruction: +0.1
          - 上限: 1.0
        """
        score = 0.0

        # 检查触发模式
        if summary.trigger_patterns:
            for pattern in summary.trigger_patterns:
                if pattern.lower() in query:
                    score += 0.3

        # 检查技能名称
        if summary.name.lower() in query:
            score += 0.2

        # 检查描述
        if summary.description and summary.description.lower() in query:
            score += 0.1

        # 检查步骤指令（替代原来的 step.parameters.instruction）
        for instruction in summary.step_instructions:
            if instruction and instruction.lower() in query:
                score += 0.1

        return min(score, 1.0)

    # =========================================================================
    # Tier 2: 按需加载完整 Skill
    # =========================================================================

    def load_full_skill(self, skill_id: str) -> Optional[Skill]:
        """Tier 2: 按需加载完整技能（仅在确认匹配后调用）

        从数据库加载包含完整 SkillStep 对象和 metadata 的 Skill。
        应在 Tier 1 匹配成功后、执行技能步骤前调用。

        Args:
            skill_id: 技能 ID（来自 SkillSummary.id）

        Returns:
            完整 Skill 对象，或 None（如果技能不存在）
        """
        skill = db.get_skill(skill_id)
        if skill:
            logger.debug(f"[T2_LOAD] Loaded full skill: {skill.name} ({len(skill.steps)} steps)")
        else:
            logger.warning(f"[T2_LOAD] Skill not found: {skill_id}")
        return skill

    # =========================================================================
    # 兼容层: 保留旧的 _calculate_match_score 以支持完整 Skill 对象评分
    # =========================================================================

    def _calculate_match_score(self, skill, query: str) -> float:
        """计算匹配分数（兼容 Skill 和 SkillSummary 对象）

        优先使用 SkillSummary 路径（更高效），
        如果传入完整 Skill 对象则自动降级到 step.parameters.instruction 提取。
        """
        # 如果是 SkillSummary，使用高效路径
        if isinstance(skill, SkillSummary):
            return self._calculate_summary_score(skill, query)

        # 完整 Skill 对象的兼容路径
        score = 0.0

        if skill.trigger_patterns:
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query:
                    score += 0.3

        if skill.name.lower() in query:
            score += 0.2

        if skill.description and skill.description.lower() in query:
            score += 0.1

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
