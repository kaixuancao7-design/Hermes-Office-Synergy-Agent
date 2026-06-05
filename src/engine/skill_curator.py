"""技能 Curator — 7天周期自主维护技能库

职责：
  1. 评分：按使用频率、成功率、活跃度给 learned 技能打分
  2. 合并：使用 LLM 检测功能相似的技能，提议合并
  3. 归档：长期未使用或低质量技能的归档
  4. 报告：生成 Curator 维护报告（skills/curator_report.md）
"""

import os
from typing import Dict, Any, List, Optional
from src.data.database import db
from src.utils import get_timestamp
from src.plugins.model_routers import call_model
from src.logging_config import get_logger

logger = get_logger("engine")

CURATOR_MERGE_PROMPT = """你是一个技能库管理员。请判断以下两个技能是否功能重复，是否需要合并。

## 技能 A
- 名称: {name_a}
- 描述: {desc_a}
- 触发模式: {triggers_a}
- 步骤数: {steps_a}

## 技能 B
- 名称: {name_b}
- 描述: {desc_b}
- 触发模式: {triggers_b}
- 步骤数: {steps_b}

## 要求
返回 JSON（只返回 JSON）：
{{
  "are_duplicates": true/false,
  "similarity_score": 0.0-1.0,
  "reason": "简短的理由说明",
  "merged_name": "如果合并，建议的新技能名称",
  "merged_description": "如果合并，建议的新描述"
}}

只有 similarity_score >= 0.7 才应标记为 are_duplicates=true。"""


class SkillCurator:
    """技能库自主维护器

    评分公式：score = 0.4 * usage_freq + 0.3 * success_rate + 0.3 * recency
    """

    CYCLE_INTERVAL_SECONDS = 7 * 24 * 3600  # 7 天

    # 阈值
    ARCHIVE_SCORE_THRESHOLD = 0.2     # 低于此分数 + 30天未使用 → 归档
    ARCHIVE_INACTIVE_DAYS = 30        # 不活跃天数阈值
    MERGE_SIMILARITY_THRESHOLD = 0.7  # LLM 判断相似度 >= 此值 → 建议合并

    def __init__(self):
        self.last_run_at: Optional[int] = None

    # ========================================================================
    # 主循环
    # ========================================================================

    async def run_curation_cycle(self) -> dict:
        """执行完整的 Curator 维护循环

        Returns:
            包含各阶段结果的报告字典
        """
        logger.info("[CURATOR] Starting curation cycle...")
        start_time = get_timestamp()

        try:
            # Phase 1: 评分
            scored = self._score_skills()
            logger.info(f"[CURATOR] Phase 1: Scored {len(scored)} learned skills")

            # Phase 2: 相似技能检测与合并
            merges = await self._merge_similar_skills(scored)
            logger.info(f"[CURATOR] Phase 2: Found {len(merges)} merge candidates")

            # Phase 3: 归档
            archived = self._archive_unused(scored)
            logger.info(f"[CURATOR] Phase 3: Archived {len(archived)} skills")

            # Phase 4: 生成报告
            report = self._generate_report(scored, merges, archived, start_time)
            self._write_report_md(report)

            self.last_run_at = start_time
            logger.info(f"[CURATOR] Curation cycle complete |"
                         f" scored={len(scored)} | merges={len(merges)}"
                         f" | archived={len(archived)}")

            return report

        except Exception as e:
            logger.error(f"[CURATOR] Curation cycle failed: {e}", exc_info=True)
            return {"error": str(e), "timestamp": start_time}

    # ========================================================================
    # Phase 1: 评分
    # ========================================================================

    def _score_skills(self) -> List[dict]:
        """对所有 learned 技能进行评分"""
        all_stats = db.get_all_learned_skill_usage()
        now = get_timestamp()
        max_uses = max((s["total_uses"] for s in all_stats), default=1)

        scored = []
        for s in all_stats:
            # 使用频率 (0-1 归一化)
            usage_freq = min(s["total_uses"] / max(max_uses, 1), 1.0)

            # 成功率
            success_rate = (
                s["success_count"] / max(s["total_uses"], 1)
                if s["total_uses"] > 0 else 0.5
            )

            # 活跃度（最近使用天数，越近越高）
            last_used = s["last_used_at"] or 0
            days_since_last_use = (now - last_used) / 86400 if last_used > 0 else 999
            recency = max(0.0, 1.0 - days_since_last_use / self.ARCHIVE_INACTIVE_DAYS)

            score = 0.4 * usage_freq + 0.3 * success_rate + 0.3 * recency

            scored.append({
                **s,
                "usage_freq": usage_freq,
                "success_rate": success_rate,
                "recency": recency,
                "curator_score": round(score, 3),
                "days_since_last_use": round(days_since_last_use, 1),
            })

        scored.sort(key=lambda x: x["curator_score"], reverse=True)
        return scored

    # ========================================================================
    # Phase 2: 合并检测
    # ========================================================================

    async def _merge_similar_skills(self, scored: List[dict]) -> List[dict]:
        """使用 LLM 检测功能相似的技能对"""
        merges = []

        # 只比较活跃技能（分数 >= 阈值）
        active = [s for s in scored if s["curator_score"] >= self.ARCHIVE_SCORE_THRESHOLD]
        if len(active) < 2:
            return merges

        # 两两比较（限制比较次数）
        max_comparisons = min(len(active) * (len(active) - 1) // 2, 10)
        compared = 0

        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                if compared >= max_comparisons:
                    break
                compared += 1

                result = await self._compare_pair(active[i], active[j])
                if result and result.get("are_duplicates"):
                    merges.append({
                        "skill_a": active[i]["skill_name"],
                        "skill_b": active[j]["skill_name"],
                        "similarity": result.get("similarity_score", 0),
                        "reason": result.get("reason", ""),
                        "merged_name": result.get("merged_name", ""),
                        "merged_description": result.get("merged_description", ""),
                    })

        return merges

    async def _compare_pair(self, skill_a: dict, skill_b: dict) -> Optional[dict]:
        """使用 LLM 比较两个技能"""
        import json
        import re

        # 快速预筛选：触发词重叠度
        a_skills = db.get_skill(skill_a["skill_id"])
        b_skills = db.get_skill(skill_b["skill_id"])

        if not a_skills or not b_skills:
            return None

        prompt = CURATOR_MERGE_PROMPT.format(
            name_a=skill_a["skill_name"],
            desc_a=a_skills.description or "",
            triggers_a=", ".join(a_skills.trigger_patterns or [])[:200],
            steps_a=len(a_skills.steps),
            name_b=skill_b["skill_name"],
            desc_b=b_skills.description or "",
            triggers_b=", ".join(b_skills.trigger_patterns or [])[:200],
            steps_b=len(b_skills.steps),
        )

        try:
            response = await call_model(prompt)
            if not response:
                return None
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass
        return None

    # ========================================================================
    # Phase 3: 归档
    # ========================================================================

    def _archive_unused(self, scored: List[dict]) -> List[str]:
        """归档低质量或长期未使用的技能"""
        archived = []

        for s in scored:
            if (s["curator_score"] < self.ARCHIVE_SCORE_THRESHOLD
                    and s["days_since_last_use"] > self.ARCHIVE_INACTIVE_DAYS):
                # 标记为 archived（更新 metadata）
                skill = db.get_skill(s["skill_id"])
                if skill:
                    skill.metadata["archived"] = True
                    skill.metadata["archived_at"] = get_timestamp()
                    skill.metadata["archived_reason"] = (
                        f"Curator: score={s['curator_score']:.2f},"
                        f" inactive={s['days_since_last_use']}d"
                    )
                    db.save_skill(skill)
                    archived.append(s["skill_name"])
                    logger.info(f"[CURATOR] Archived: {s['skill_name']}"
                                 f" (score={s['curator_score']:.2f},"
                                 f" inactive={s['days_since_last_use']}d)")

        return archived

    # ========================================================================
    # Phase 4: 报告
    # ========================================================================

    def _generate_report(self, scored: List[dict], merges: List[dict],
                         archived: List[str], timestamp: int) -> dict:
        """生成 Curator 报告"""
        top_5 = scored[:5]
        bottom_5 = scored[-5:] if len(scored) >= 5 else scored

        return {
            "timestamp": timestamp,
            "total_learned_skills": len(scored),
            "avg_score": round(sum(s["curator_score"] for s in scored) / max(len(scored), 1), 3),
            "top_performers": [
                {"name": s["skill_name"], "score": s["curator_score"],
                 "uses": s["total_uses"]} for s in top_5
            ],
            "bottom_performers": [
                {"name": s["skill_name"], "score": s["curator_score"],
                 "uses": s["total_uses"]} for s in bottom_5
            ],
            "merge_candidates": merges,
            "archived_skills": archived,
            "recommendations": self._generate_recommendations(scored, merges, archived),
        }

    def _generate_recommendations(self, scored: List[dict], merges: List[dict],
                                   archived: List[str]) -> List[str]:
        """生成 Curator 建议"""
        recs = []

        if archived:
            recs.append(f"已归档 {len(archived)} 个低质量技能：{', '.join(archived)}")

        if merges:
            for m in merges:
                recs.append(
                    f"建议合并: {m['skill_a']} + {m['skill_b']}"
                    f" → {m.get('merged_name', 'new_skill')}"
                    f" (相似度: {m['similarity']})"
                )

        low_score_count = sum(1 for s in scored if s["curator_score"] < 0.3)
        if low_score_count > len(scored) * 0.5:
            recs.append(f"警告: {low_score_count}/{len(scored)} 个技能质量较低，建议审核")

        if not recs:
            recs.append("技能库健康状态良好，无需特别处理。")

        return recs

    def _write_report_md(self, report: dict) -> None:
        """将报告写入 Markdown 文件"""
        report_dir = "skills"
        os.makedirs(report_dir, exist_ok=True)
        filepath = os.path.join(report_dir, "curator_report.md")

        lines = [
            "# Curator Report",
            "",
            f"**Generated at**: {report['timestamp']}",
            f"**Total learned skills**: {report['total_learned_skills']}",
            f"**Average score**: {report['avg_score']}",
            "",
            "## Top Performers",
            "",
        ]
        for s in report.get("top_performers", []):
            lines.append(f"- **{s['name']}** — score={s['score']}, uses={s['uses']}")

        lines.extend(["", "## Bottom Performers", ""])
        for s in report.get("bottom_performers", []):
            lines.append(f"- **{s['name']}** — score={s['score']}, uses={s['uses']}")

        lines.extend(["", "## Merge Candidates", ""])
        for m in report.get("merge_candidates", []):
            lines.append(
                f"- {m['skill_a']} + {m['skill_b']}"
                f" → {m.get('merged_name', '?')} (similarity={m['similarity']})"
            )

        lines.extend(["", "## Archived", ""])
        for name in report.get("archived_skills", []):
            lines.append(f"- {name}")

        lines.extend(["", "## Recommendations", ""])
        for r in report.get("recommendations", []):
            lines.append(f"- {r}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        logger.info(f"[CURATOR] Report written: {filepath}")


# 全局实例
skill_curator = SkillCurator()
