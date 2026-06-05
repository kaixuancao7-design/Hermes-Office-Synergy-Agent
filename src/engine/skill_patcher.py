"""技能自动修补器 — 检测用户纠正是否关联到已有 learned 技能并自动修补

与 LearningCycle 的区别：
  - LearningCycle: 从纠正中创建新技能草稿
  - SkillAutoPatcher: 检查纠正是否属于已有技能 → 直接修补该技能的步骤
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

    async def find_related_skill(self, query_context: str) -> Optional[Skill]:
        """在 learned 技能中查找与纠正上下文相关的技能

        使用触发词匹配进行初筛，选择最匹配的。
        """
        all_skills = db.get_all_skills()
        learned = [s for s in all_skills if s.type == "learned"]

        if not learned:
            return None

        # 限制检查数量
        learned = learned[:self.MAX_SKILLS_TO_CHECK]

        best_score = 0.0
        best_skill = None

        for skill in learned:
            score = self._calculate_relevance(skill, query_context)
            if score > best_score and score >= self.MIN_RELEVANCE_SCORE:
                best_score = score
                best_skill = skill

        if best_skill:
            logger.info(f"[AUTO_PATCH] Found related skill: {best_skill.name}"
                         f" | score={best_score:.2f}")
        return best_skill

    def _calculate_relevance(self, skill: Skill, context: str) -> float:
        """计算技能与上下文的相关性分数

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
                          corrected_output: str, context: str) -> Optional[Skill]:
        """使用 LLM 分析纠正并修补技能步骤

        Args:
            skill: 需要修补的技能
            original_output: 原始（错误的）输出
            corrected_output: 用户纠正（正确的）输出
            context: 对话上下文

        Returns:
            更新后的 Skill，无需修补时返回 None
        """
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
            return self._apply_patch(skill, patch_result)

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

    def _apply_patch(self, skill: Skill, patch_result: dict) -> Optional[Skill]:
        """应用 LLM 返回的修补结果到技能"""
        # 更新步骤
        updated_steps_raw = patch_result.get("updated_steps", [])
        if not updated_steps_raw:
            return None

        new_steps = [
            SkillStep(
                id=generate_id(),
                action=s.get("action", "execute"),
                parameters=s.get("parameters", {}),
            )
            for s in updated_steps_raw
        ]

        # 更新触发模式
        new_triggers = patch_result.get("new_trigger_patterns", [])
        if new_triggers:
            existing = set(t.lower() for t in skill.trigger_patterns)
            for t in new_triggers:
                if t.lower() not in existing:
                    skill.trigger_patterns.append(t)
                    existing.add(t.lower())

        # 版本号递增
        parts = skill.version.split(".")
        if len(parts) == 3:
            skill.version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

        skill.steps = new_steps
        skill.updated_at = get_timestamp()

        # 持久化
        db.save_skill(skill)

        # 更新 SKILL.md
        try:
            from src.skills.skill_md import skill_md_manager
            skill_md_manager.write_skill_md(skill)
        except Exception as e:
            logger.warning(f"[AUTO_PATCH] SKILL.md update failed: {e}")

        logger.info(f"[AUTO_PATCH] Skill patched: {skill.name}"
                     f" | v{skill.version} | steps={len(new_steps)}"
                     f" | triggers={len(skill.trigger_patterns)}")
        return skill


# 全局实例
skill_auto_patcher = SkillAutoPatcher()
