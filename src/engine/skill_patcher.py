"""技能自动修补器 — 检测用户纠正是否关联到已有 learned 技能并提出修补草稿

与 LearningCycle 的区别：
  - LearningCycle: 从纠正中创建新技能草稿
  - SkillAutoPatcher: 检查用户编辑权限 → 为已有技能生成待审核修补草稿
"""

from typing import Optional, List
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.plugins.model_routers import call_model
from src.logging_config import get_logger

logger = get_logger("engine")

PATCH_SKILL_PROMPT = """你是一个智能办公助手。用户纠正了一个已有技能的执行结果。请分析并更新该技能的步骤。

## 当前技能定义
- 名称: {skill_name}
- 描述: {skill_description}
- 触发模式: {trigger_patterns}
- 当前步骤:
{current_steps}

## 原始输出（错误的）
{original_output}

## 用户纠正（正确的）
{corrected_output}

## 上下文
{context}

## 要求
分析用户的纠正，判断如何改进此技能的步骤。返回 JSON（只返回 JSON）：

{{
  "should_patch": true/false,
  "reason": "为什么需要/不需要修补",
  "updated_steps": [
    {{
      "action": "步骤动作",
      "parameters": {{"instruction": "更新后的指令描述"}}
    }},
    ...
  ],
  "new_trigger_patterns": ["新增的触发词1", ...]（可选，如果纠正暗示了新的触发场景）
}}

注意：
1. 如果纠正只是用户的偏好表达而非技能缺陷，should_patch 应为 false
2. updated_steps 应该基于原有步骤改进，而不是完全重写
3. 如果纠正毫无关联，should_patch 应为 false"""


class SkillAutoPatcher:
    """自动检测并修补已有 learned 技能

    在用户纠正检测后异步触发，不阻塞用户响应。
    """

    MIN_RELEVANCE_SCORE = 0.5   # 相关性分数阈值
    MAX_SKILLS_TO_CHECK = 20    # 最多检查的 learned 技能数量

    # ========================================================================
    # 技能关联检测
    # ========================================================================

    async def find_related_skill(self, query_context: str, user_id: str = None) -> Optional[Skill]:
        """在 learned 技能中查找与纠正上下文相关的技能

        Tier 1: 使用 SkillSummary 进行轻量级初筛
        Tier 2: 确认匹配后按需加载完整 Skill
        """
        if not user_id:
            return None
        # Tier 1: 使用摘要进行轻量级匹配
        all_summaries = db.get_skills_summaries()
        learned = [s for s in all_summaries if s.type == "learned" and self._can_edit(user_id, s.id)]

        if not learned:
            return None

        # 限制检查数量
        learned = learned[:self.MAX_SKILLS_TO_CHECK]

        best_score = 0.0
        best_summary = None

        for summary in learned:
            score = self._calculate_relevance(summary, query_context)
            if score > best_score and score >= self.MIN_RELEVANCE_SCORE:
                best_score = score
                best_summary = summary

        if best_summary:
            logger.info(f"[AUTO_PATCH] Found related skill: {best_summary.name}"
                         f" | score={best_score:.2f}")
            # Tier 2: 按需加载完整 Skill
            return db.get_skill(best_summary.id)

        return None

    def _calculate_relevance(self, skill, context: str) -> float:
        """计算技能与上下文的相关性分数（兼容 Skill 和 SkillSummary）

        使用触发模式匹配率 + 名称/描述重叠度。
        """
        context_lower = context.lower()
        hits = 0
        total = max(len(skill.trigger_patterns), 1)

        for pattern in skill.trigger_patterns:
            if pattern.lower() in context_lower:
                hits += 1

        pattern_score = hits / total

        # 名称匹配加分
        name_bonus = 0.2 if skill.name.lower() in context_lower else 0.0
        desc_bonus = 0.1 if (
            skill.description and skill.description[:30].lower() in context_lower
        ) else 0.0

        return min(pattern_score + name_bonus + desc_bonus, 1.0)

    # ========================================================================
    # 技能修补
    # ========================================================================

    async def patch_skill(self, skill: Skill, original_output: str,
                          corrected_output: str, context: str, user_id: str = None) -> Optional[str]:
        """使用 LLM 分析纠正并修补技能步骤

        Args:
            skill: 需要修补的技能
            original_output: 原始（错误的）输出
            corrected_output: 用户纠正（正确的）输出
            context: 对话上下文

        Returns:
            更新后的 Skill，无需修补时返回 None
        """
        if not user_id or not self._can_edit(user_id, skill.id):
            return None
        logger.info(f"[AUTO_PATCH] Analyzing correction for skill: {skill.name}")

        try:
            # 1. 构建提示词
            prompt = self._build_patch_prompt(skill, original_output, corrected_output, context)

            # 2. 调用 LLM
            llm_response = await call_model(prompt)
            if not llm_response or not llm_response.strip():
                logger.warning("[AUTO_PATCH] LLM returned empty response")
                return None

            # 3. 解析结果
            import json
            import re

            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if not json_match:
                return None

            patch_result = json.loads(json_match.group(0))

            # 4. 判断是否需要修补
            if not patch_result.get("should_patch", False):
                logger.info(f"[AUTO_PATCH] LLM decided not to patch:"
                             f" {patch_result.get('reason', 'no reason given')}")
                return None

            # 5. 应用修补
            return self._apply_patch(skill, patch_result, user_id)

        except Exception as e:
            logger.error(f"[AUTO_PATCH] Patch failed: {e}", exc_info=True)
            return None

    def _build_patch_prompt(self, skill: Skill, original: str,
                            corrected: str, context: str) -> str:
        """构建修补提示词"""
        step_lines = []
        for i, step in enumerate(skill.steps, 1):
            params = str(step.parameters)[:200]
            step_lines.append(f"  {i}. action={step.action} | params={params}")

        return PATCH_SKILL_PROMPT.format(
            skill_name=skill.name,
            skill_description=skill.description or "",
            trigger_patterns=", ".join(skill.trigger_patterns or []),
            current_steps="\n".join(step_lines) if step_lines else "(none)",
            original_output=original[:500],
            corrected_output=corrected[:500],
            context=context[:500],
        )

    @staticmethod
    def _can_edit(user_id, skill_id):
        from src.services.permission_service import permission_service
        skill = db.get_skill(skill_id)
        return bool(skill and not skill.metadata.get("archived") and not skill.metadata.get("quarantined") and
                    (skill.created_by == user_id or permission_service.check_skill_permission(user_id, skill_id, "edit").allowed))

    def _apply_patch(self, skill, patch_result, user_id=None):
        """Create a reviewable proposal; never mutate the live skill."""
        import hashlib
        import json
        from src.types import SkillDraft
        from src.services.skill_verification import validate_definition
        if not user_id or not self._can_edit(user_id, skill.id):
            return None
        current = db.get_skill(skill.id)
        if not current or current.version != skill.version:
            return None
        raw = patch_result.get("updated_steps")
        if not isinstance(raw, list) or not raw:
            return None
        by_id = {step.id: step for step in skill.steps}
        steps = []
        for index, update in enumerate(raw):
            original = by_id.get(update.get("id")) if update.get("id") else (skill.steps[index] if index < len(skill.steps) else None)
            values = original.model_dump() if original else {"id": generate_id(), "parameters": {}}
            values.update(update)
            if original and update.get("action", original.action) == original.action:
                values["parameters"] = {**original.parameters, **update.get("parameters", {})}
            steps.append(SkillStep.model_validate(values))
        triggers = list(dict.fromkeys(skill.trigger_patterns + patch_result.get("new_trigger_patterns", [])))
        draft = SkillDraft(id=generate_id(), skill_name=skill.name, description=skill.description,
            trigger_patterns=triggers, steps=steps, original_context=patch_result.get("reason", "Patch proposal"),
            original_output="", corrected_output="", user_intent="skill_patch", user_id=user_id,
            created_at=get_timestamp(), status="pending_review", metadata={"source": "auto_patch",
                "target_skill_id": skill.id, "base_version": skill.version})
        validate_definition(draft)
        source = json.dumps({"user": user_id, "skill": skill.id, "version": skill.version,
                             "steps": [step.model_dump() for step in steps], "triggers": triggers}, sort_keys=True, ensure_ascii=False)
        return db.save_learning_draft("patch:" + hashlib.sha256(source.encode()).hexdigest(), draft)


# 全局实例
skill_auto_patcher = SkillAutoPatcher()
