"""三闸门学习循环引擎 — 捕获 → 学习 → 应用

Gate 1 (捕获): 接收用户纠正反馈，分析原始输出与纠正输出的差异
Gate 2 (学习): 从纠正中提取可复用的步骤和触发模式，生成 SkillDraft
Gate 3 (应用): 人工审核草稿 → 批准后创建 learned 技能 → 部署到技能库
"""

import re
from typing import Dict, Any, Optional, List
from src.types import SkillDraft, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("engine")


class LearningCycle:
    """三闸门学习循环

    完整的反馈→学习→部署管道：
      1. capture_correction — 捕获用户纠正（Gate 1）
      2. _analyze_and_draft   — 分析差异并生成技能草稿（Gate 2）
      3. manual_review_skill  — 人工审核草稿（Gate 3）
      4. suggest_skill_creation — 主动建议可自动化的任务
    """

    def __init__(self):
        # 内存缓存（快速查找），数据库为持久化存储
        self.corrections: Dict[str, Dict[str, Any]] = {}      # user_id -> {correction_id: data}
        self.user_patterns: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> [patterns]

    # ========================================================================
    # Gate 1: 捕获（Capture）
    # ========================================================================

    def capture_correction(self, user_id: str, original: str, corrected: str,
                           context: str, intent: str = "") -> Optional[str]:
        """Gate 1: 捕获用户纠正反馈

        分析原始输出与纠正输出的差异，创建 SkillDraft（状态=draft）。

        Args:
            user_id:   用户 ID
            original:  模型原始输出
            corrected: 用户纠正后的输出
            context:   对话上下文
            intent:    原始意图类型

        Returns:
            创建的草稿 ID，失败时返回 None
        """
        correction_id = generate_id()

        # 保存到内存缓存
        correction = {
            "id": correction_id,
            "user_id": user_id,
            "original": original,
            "corrected": corrected,
            "context": context,
            "intent": intent,
            "timestamp": get_timestamp(),
            "status": "captured",
        }
        self.corrections.setdefault(user_id, {})[correction_id] = correction

        logger.info(f"[LEARN:G1] 捕获纠正 | user_id={user_id} | correction_id={correction_id}"
                     f" | intent={intent}")

        # 学习模式（内存）
        self._learn_pattern(user_id, original, corrected, context)

        # Gate 2: 分析差异 → 生成 SkillDraft
        draft_id = self._analyze_and_draft(user_id, original, corrected, context, intent)
        return draft_id

    # ========================================================================
    # Gate 2: 学习（Learn）
    # ========================================================================

    def _learn_pattern(self, user_id: str, original: str, corrected: str,
                       context: str) -> None:
        """从纠正中提取可复用模式（内存缓存）"""
        try:
            pattern = {
                "original": original,
                "corrected": corrected,
                "context": context,
                "timestamp": get_timestamp(),
                "confidence": 0.8,
            }
            self.user_patterns.setdefault(user_id, []).append(pattern)

            # 限制每个用户的模式缓存数量
            if len(self.user_patterns[user_id]) > 100:
                self.user_patterns[user_id] = self.user_patterns[user_id][-50:]

            logger.debug(f"[LEARN:G2] 模式已学习 | user_id={user_id}"
                         f" | pattern_count={len(self.user_patterns[user_id])}")
        except Exception as e:
            logger.error(f"[LEARN:G2] 学习失败: {str(e)}")

    def _analyze_and_draft(self, user_id: str, original: str, corrected: str,
                           context: str, intent: str) -> Optional[str]:
        """Gate 2: 分析纠正差异，生成 SkillDraft 并持久化

        通过比较 original 与 corrected 的差异提取：
          - 可复用的步骤模板
          - 触发关键词（从 context 提取）
          - 技能名称和描述
        """
        try:
            differences = self._diff_texts(original, corrected)
            trigger_patterns = self._extract_triggers(context, intent)
            skill_name = self._generate_skill_name(context, intent)

            steps = [
                {
                    "id": generate_id(),
                    "action": "analyze_input",
                    "parameters": {"instruction": f"分析用户输入: {context[:200]}"},
                },
                {
                    "id": generate_id(),
                    "action": "apply_correction",
                    "parameters": {
                        "instruction": "应用已学习的纠正模式",
                        "corrections": differences,
                    },
                },
            ]

            draft = SkillDraft(
                id=generate_id(),
                skill_name=skill_name,
                description=f"从用户纠正中自动学习: {context[:100]}",
                trigger_patterns=trigger_patterns,
                steps=[SkillStep(**s) for s in steps],
                original_context=context,
                original_output=original,
                corrected_output=corrected,
                user_intent=intent,
                user_id=user_id,
                created_at=get_timestamp(),
                status="draft",
            )

            # 自动验证：如果差异明确且上下文清晰，直接提升为 pending_review
            confidence = self._estimate_confidence(differences, context)
            if confidence >= 0.6:
                draft.status = "pending_review"
                logger.info(f"[LEARN:G2] 草稿自动提升为待审核 | confidence={confidence:.2f}")
            else:
                logger.info(f"[LEARN:G2] 草稿保存为draft | confidence={confidence:.2f}")

            # 持久化到数据库
            db.save_skill_draft(draft.model_dump())

            logger.info(f"[LEARN:G2] 技能草稿已创建 | draft_id={draft.id}"
                         f" | name={skill_name} | status={draft.status}")
            return draft.id

        except Exception as e:
            logger.error(f"[LEARN:G2] 草稿生成失败: {str(e)}", exc_info=True)
            return None

    # ========================================================================
    # Gate 3: 应用（Apply）
    # ========================================================================

    def manual_review_skill(self, draft_id: str, approved: bool,
                            reviewer_id: str = "admin",
                            comments: str = "") -> Optional[SkillDraft]:
        """Gate 3: 人工审核技能草稿

        - 批准 → 创建 learned 技能并部署到技能库
        - 拒绝 → 记录反馈，草稿标记为 rejected
        """
        draft_dict = db.get_skill_draft(draft_id)
        if not draft_dict:
            logger.warning(f"[LEARN:G3] 草稿不存在: {draft_id}")
            return None

        if approved:
            db.update_skill_draft_status(draft_id, "approved", reviewer_id, comments)

            # 通过 learned_skills_manager 创建正式技能
            from src.skills.learned_skills import learned_skills_manager
            skill = learned_skills_manager.create_from_draft(reviewer_id, draft_id)
            if skill:
                logger.info(f"[LEARN:G3] ✅ 技能已批准并部署 | draft_id={draft_id}"
                             f" | skill_id={skill.id} | skill_name={skill.name}")
            else:
                logger.error(f"[LEARN:G3] 技能创建失败 | draft_id={draft_id}")
                return None
        else:
            db.update_skill_draft_status(draft_id, "rejected", reviewer_id, comments)
            logger.info(f"[LEARN:G3] ❌ 草稿已拒绝 | draft_id={draft_id}"
                         f" | reviewer={reviewer_id} | comments={comments[:50]}")

        # 返回更新后的草稿
        updated = db.get_skill_draft(draft_id)
        return SkillDraft(**updated) if updated else None

    def suggest_skill_creation(self, user_id: str,
                                task_description: str) -> Optional[SkillDraft]:
        """主动建议：分析任务描述，判断是否值得创建技能

        当用户反复执行相似任务时，系统可以主动建议创建技能。
        """
        patterns = self.user_patterns.get(user_id, [])
        if not patterns:
            logger.debug(f"[LEARN:SUGGEST] 用户 {user_id} 无历史模式，无法建议")
            return None

        # 查找与当前任务相似的已有模式
        similar = []
        task_lower = task_description.lower()
        for p in patterns:
            original_lower = p["original"].lower()
            # 简单相似度：共享关键词
            common_words = set(task_lower.split()) & set(original_lower.split())
            if len(common_words) >= 2:
                similar.append(p)

        if len(similar) < 2:
            return None  # 至少需要2个相似模式才建议

        logger.info(f"[LEARN:SUGGEST] 发现 {len(similar)} 个相似模式，建议创建技能")

        return SkillDraft(
            id=generate_id(),
            skill_name=f"自动处理: {task_description[:50]}",
            description=f"基于 {len(similar)} 次历史纠正自动建议的技能",
            trigger_patterns=self._extract_triggers(task_description, ""),
            steps=[
                SkillStep(
                    id=generate_id(),
                    action="auto_process",
                    parameters={"instruction": task_description},
                ),
            ],
            original_context=task_description,
            original_output="",
            corrected_output="",
            user_intent="auto_suggested",
            user_id=user_id,
            created_at=get_timestamp(),
            status="draft",
        )

    # ========================================================================
    # 查询方法
    # ========================================================================

    def get_pending_reviews(self) -> List[SkillDraft]:
        """获取所有待审核的技能草稿"""
        drafts = db.get_pending_skill_drafts()
        return [SkillDraft(**d) for d in drafts]

    def get_skill_draft(self, draft_id: str) -> Optional[SkillDraft]:
        """获取单个技能草稿"""
        d = db.get_skill_draft(draft_id)
        return SkillDraft(**d) if d else None

    def get_corrections(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的纠正记录"""
        return list(self.corrections.get(user_id, {}).values())

    def approve_correction(self, user_id: str, correction_id: str) -> bool:
        """批准纠正（标记为已批准）"""
        if user_id not in self.corrections:
            return False
        if correction_id not in self.corrections[user_id]:
            return False
        self.corrections[user_id][correction_id]["status"] = "approved"
        return True

    def get_learning_stats(self, user_id: str = None) -> dict:
        """获取学习统计信息"""
        stats = db.get_learning_stats(user_id)
        # 添加内存中的模式数量
        stats["patterns_in_memory"] = (
            len(self.user_patterns.get(user_id, []))
            if user_id else sum(len(v) for v in self.user_patterns.values())
        )
        return stats

    def suggest_response(self, user_id: str, query: str) -> Optional[str]:
        """基于已学习的模式建议响应"""
        if user_id not in self.user_patterns:
            return None
        for pattern in self.user_patterns[user_id]:
            if pattern["original"] in query or query in pattern["original"]:
                logger.info(f"[LEARN:SUGGEST] 匹配已学习模式 | user_id={user_id}")
                return pattern["corrected"]
        return None

    # ========================================================================
    # 辅助方法
    # ========================================================================

    @staticmethod
    def _diff_texts(original: str, corrected: str) -> List[Dict[str, Any]]:
        """比较原始和纠正文本的差异（行级）"""
        orig_lines = original.splitlines()
        corr_lines = corrected.splitlines()
        diffs = []
        for i, (o, c) in enumerate(zip(orig_lines, corr_lines)):
            if o != c:
                diffs.append({"line": i, "original": o, "corrected": c})
        # 额外行
        if len(corr_lines) > len(orig_lines):
            for i in range(len(orig_lines), len(corr_lines)):
                diffs.append({"line": i, "original": "", "corrected": corr_lines[i]})
        elif len(orig_lines) > len(corr_lines):
            for i in range(len(corr_lines), len(orig_lines)):
                diffs.append({"line": i, "original": orig_lines[i], "corrected": ""})
        return diffs

    @staticmethod
    def _extract_triggers(context: str, intent: str) -> List[str]:
        """从上下文和意图中提取触发关键词"""
        triggers = []
        # 从意图映射
        intent_triggers = {
            "summarization": ["总结", "摘要", "概括"],
            "question_answering": ["什么是", "如何", "为什么"],
            "code_generation": ["代码", "编程", "写"],
            "document_analysis": ["分析", "解读", "文件"],
            "creative_writing": ["写", "创作", "生成"],
            "task_execution": ["帮我", "执行", "完成"],
        }
        if intent in intent_triggers:
            triggers.extend(intent_triggers[intent])

        # 从上下文提取高频中文词（简单实现）
        chinese_words = re.findall(r'[一-鿿]{2,4}', context)
        from collections import Counter
        top_words = [w for w, _ in Counter(chinese_words).most_common(5) if len(w) >= 2]
        triggers.extend(top_words)

        # 去重，最多10个
        seen = set()
        result = []
        for t in triggers:
            if t.lower() not in seen:
                seen.add(t.lower())
                result.append(t)
        return result[:10]

    @staticmethod
    def _generate_skill_name(context: str, intent: str) -> str:
        """根据上下文和意图生成技能名称"""
        intent_names = {
            "summarization": "智能总结",
            "question_answering": "智能问答",
            "code_generation": "代码生成",
            "document_analysis": "文档分析",
            "creative_writing": "创意写作",
            "task_execution": "任务执行",
            "ppt_generate_outline": "PPT大纲生成",
            "ppt_generate_from_content": "PPT内容生成",
            "ppt_custom_generate": "PPT生成",
        }
        base = intent_names.get(intent, "自动处理")
        # 截取上下文中的关键短语
        short_ctx = context[:30].strip()
        return f"{base}: {short_ctx}" if short_ctx else base

    @staticmethod
    def _estimate_confidence(differences: List[Dict], context: str) -> float:
        """估算草稿质量置信度"""
        if not differences:
            return 0.0
        # 差异越多越具体 → 置信度越高（有明确的改进方向）
        diff_score = min(0.5, len(differences) * 0.1)
        # 上下文越丰富 → 置信度越高
        ctx_score = min(0.3, len(context) / 1000 * 0.3)
        return 0.2 + diff_score + ctx_score  # 基准 0.2


# 全局实例
learning_cycle = LearningCycle()
