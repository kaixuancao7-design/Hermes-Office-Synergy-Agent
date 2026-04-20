"""技能验证服务"""
from typing import List, Dict, Any, Optional
from src.types import SkillDraft, VerificationResult, CorrectionAnalysis, Skill, SkillStep
from src.plugins import get_model_router, get_skill_manager, get_memory_store
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("engine")


class SkillVerificationService:
    """技能验证服务"""
    
    def __init__(self):
        self.drafts: Dict[str, SkillDraft] = {}
        self.verification_results: Dict[str, VerificationResult] = {}
    
    def analyze_correction(
        self,
        user_id: str,
        original_output: str,
        corrected_output: str,
        context: str,
        user_intent: str
    ) -> CorrectionAnalysis:
        """分析修正，提取差异和可复用模式"""
        
        # 使用LLM进行深度分析
        model_router = get_model_router()
        if not model_router:
            logger.error("Model router not available for correction analysis")
            return self._basic_analysis(original_output, corrected_output, context)
        
        prompt = f"""
        Analyze the following correction to extract reusable patterns:
        
        User Intent: {user_intent}
        
        Context: {context}
        
        Original Output:
        {original_output}
        
        Corrected Output:
        {corrected_output}
        
        Please provide a detailed analysis in JSON format with:
        1. differences: List of key differences with type (addition, modification, deletion, improvement)
        2. intent_match: How well the corrected output matches user intent (0-1)
        3. context_relevance: How relevant the correction is to the context (0-1)
        4. actionable_steps: List of specific actions that can be automated
        5. trigger_conditions: List of conditions that would trigger this skill
        6. reusable_patterns: List of patterns that could be reused in similar tasks
        
        Format your response as valid JSON only.
        """
        
        try:
            model = model_router.select_model("skill_distillation", "medium")
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            
            import json
            result = json.loads(response)
            
            return CorrectionAnalysis(
                original_output=original_output,
                corrected_output=corrected_output,
                differences=result.get("differences", []),
                intent_match=result.get("intent_match", 0.0),
                context_relevance=result.get("context_relevance", 0.0),
                actionable_steps=result.get("actionable_steps", []),
                trigger_conditions=result.get("trigger_conditions", []),
                reusable_patterns=result.get("reusable_patterns", [])
            )
        except Exception as e:
            logger.error(f"LLM-based analysis failed: {str(e)}")
            return self._basic_analysis(original_output, corrected_output, context)
    
    def _basic_analysis(self, original: str, corrected: str, context: str) -> CorrectionAnalysis:
        """基础差异分析（备用方案）"""
        differences = []
        
        original_lines = original.split("\n")
        corrected_lines = corrected.split("\n")
        
        for i, (orig, corr) in enumerate(zip(original_lines, corrected_lines)):
            if orig != corr:
                if len(corr) > len(orig):
                    diff_type = "addition"
                elif len(corr) < len(orig):
                    diff_type = "deletion"
                else:
                    diff_type = "modification"
                
                differences.append({
                    "line": i + 1,
                    "type": diff_type,
                    "original": orig.strip(),
                    "corrected": corr.strip()
                })
        
        return CorrectionAnalysis(
            original_output=original,
            corrected_output=corrected,
            differences=differences,
            intent_match=0.7,
            context_relevance=0.8,
            actionable_steps=[],
            trigger_conditions=[],
            reusable_patterns=[]
        )
    
    def generate_skill_draft(
        self,
        user_id: str,
        analysis: CorrectionAnalysis,
        context: str,
        user_intent: str
    ) -> SkillDraft:
        """根据分析结果生成技能草稿"""
        
        # 从分析结果中提取技能信息
        skill_name = self._extract_skill_name(analysis, user_intent)
        description = self._extract_description(analysis)
        trigger_patterns = analysis.trigger_conditions
        steps = self._generate_steps(analysis)
        
        draft = SkillDraft(
            id=generate_id(),
            skill_name=skill_name,
            description=description,
            trigger_patterns=trigger_patterns,
            steps=steps,
            original_context=context,
            original_output=analysis.original_output,
            corrected_output=analysis.corrected_output,
            user_intent=user_intent,
            user_id=user_id,
            created_at=get_timestamp(),
            status="draft"
        )
        
        self.drafts[draft.id] = draft
        logger.info(f"Generated skill draft: {skill_name}")
        
        return draft
    
    def _extract_skill_name(self, analysis: CorrectionAnalysis, user_intent: str) -> str:
        """从分析结果中提取技能名称"""
        if analysis.reusable_patterns:
            return analysis.reusable_patterns[0][:50]
        
        # 从意图中提取
        intent_parts = user_intent.lower().split()
        action_verbs = ["generate", "create", "analyze", "extract", "summarize", "find", "search"]
        for verb in action_verbs:
            if verb in intent_parts:
                idx = intent_parts.index(verb)
                if idx + 1 < len(intent_parts):
                    return f"{verb.capitalize()} {intent_parts[idx + 1].capitalize()}"
        
        return f"Skill_{get_timestamp()}"
    
    def _extract_description(self, analysis: CorrectionAnalysis) -> str:
        """提取技能描述"""
        patterns_str = ", ".join(analysis.reusable_patterns[:3]) if analysis.reusable_patterns else "N/A"
        return f"Automates tasks involving: {patterns_str}"
    
    def _generate_steps(self, analysis: CorrectionAnalysis) -> List[SkillStep]:
        """生成技能步骤"""
        steps = []
        
        for i, action in enumerate(analysis.actionable_steps[:5], 1):
            step = SkillStep(
                id=generate_id(),
                action="execute",
                parameters={"instruction": action},
                next_step_id=None if i == len(analysis.actionable_steps[:5]) else generate_id()
            )
            steps.append(step)
        
        if not steps:
            # 如果没有可操作步骤，基于修正内容生成
            steps.append(SkillStep(
                id=generate_id(),
                action="generate",
                parameters={
                    "template": analysis.corrected_output,
                    "context": analysis.original_context
                }
            ))
        
        return steps
    
    def auto_verify(self, draft_id: str) -> VerificationResult:
        """自动验证技能草稿"""
        draft = self.drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Skill draft not found: {draft_id}")
        
        # 1. 检查技能名称和描述的完整性
        name_score = 1.0 if len(draft.skill_name) >= 3 else 0.5
        desc_score = 1.0 if len(draft.description) >= 10 else 0.5
        
        # 2. 检查步骤的可执行性
        steps_score = 1.0 if len(draft.steps) >= 1 else 0.3
        steps_valid = all(step.action and step.parameters for step in draft.steps)
        steps_score *= 1.0 if steps_valid else 0.5
        
        # 3. 检查触发模式的有效性
        trigger_score = 1.0 if len(draft.trigger_patterns) >= 1 else 0.4
        
        # 4. 搜索历史相似任务
        similar_tasks = self._find_similar_tasks(draft)
        
        # 5. 对比历史执行效果
        execution_comparison = None
        if similar_tasks:
            execution_comparison = self._compare_with_history(draft, similar_tasks)
        
        # 计算综合置信度
        confidence = (name_score * 0.15 + desc_score * 0.15 + 
                      steps_score * 0.4 + trigger_score * 0.3)
        
        # 判断是否通过验证
        verified = confidence >= 0.7
        
        result = VerificationResult(
            skill_draft_id=draft_id,
            verified=verified,
            verification_type="auto",
            confidence=confidence,
            feedback=self._generate_feedback(confidence, draft),
            similar_tasks=similar_tasks,
            execution_comparison=execution_comparison,
            verified_at=get_timestamp()
        )
        
        self.verification_results[draft_id] = result
        
        if verified:
            draft.status = "approved"
            self._convert_to_skill(draft)
            logger.info(f"Skill draft auto-verified: {draft.skill_name} (confidence: {confidence:.2f})")
        else:
            draft.status = "pending_review"
            logger.info(f"Skill draft needs manual review: {draft.skill_name} (confidence: {confidence:.2f})")
        
        return result
    
    def _find_similar_tasks(self, draft: SkillDraft) -> List[Dict[str, Any]]:
        """查找相似的历史任务"""
        memory_store = get_memory_store()
        if not memory_store:
            return []
        
        try:
            # 搜索程序性记忆中相似的工作流
            query = f"{draft.skill_name} {draft.description}"
            results = memory_store.search_memory(draft.user_id, query, limit=3)
            
            similar_tasks = []
            for result in results:
                if result.type == "procedural":
                    similar_tasks.append({
                        "id": result.id,
                        "content": result.content[:50],
                        "timestamp": result.timestamp
                    })
            
            return similar_tasks
        except Exception as e:
            logger.error(f"Searching similar tasks failed: {str(e)}")
            return []
    
    def _compare_with_history(self, draft: SkillDraft, similar_tasks: List[Dict[str, Any]]) -> Dict[str, float]:
        """与历史任务对比"""
        if not similar_tasks:
            return None
        
        # 模拟对比数据（实际中应从数据库获取）
        return {
            "similarity_score": 0.75,
            "avg_execution_time": 15.2,
            "success_rate": 0.88,
            "usage_count": 42
        }
    
    def _generate_feedback(self, confidence: float, draft: SkillDraft) -> str:
        """生成验证反馈"""
        feedback = []
        
        if len(draft.skill_name) < 3:
            feedback.append("技能名称过短，建议使用更具描述性的名称")
        if len(draft.description) < 10:
            feedback.append("技能描述不够详细")
        if len(draft.steps) == 0:
            feedback.append("缺少执行步骤")
        elif not all(step.action and step.parameters for step in draft.steps):
            feedback.append("步骤定义不完整")
        if len(draft.trigger_patterns) == 0:
            feedback.append("缺少触发条件")
        
        if confidence >= 0.9:
            return "技能草稿质量优秀，可以直接使用"
        elif confidence >= 0.7:
            if feedback:
                return f"基本通过，建议优化：{', '.join(feedback)}"
            return "技能草稿验证通过"
        else:
            if feedback:
                return f"需要人工审核，问题：{', '.join(feedback)}"
            return "需要人工审核确认"
    
    def manual_review(self, draft_id: str, approved: bool, reviewer_id: str, comments: str = "") -> VerificationResult:
        """人工审核技能草稿"""
        draft = self.drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Skill draft not found: {draft_id}")
        
        result = VerificationResult(
            skill_draft_id=draft_id,
            verified=approved,
            verification_type="manual",
            confidence=1.0 if approved else 0.0,
            feedback=comments if comments else ("已批准" if approved else "已拒绝"),
            similar_tasks=[],
            verified_at=get_timestamp(),
            verified_by=reviewer_id
        )
        
        self.verification_results[draft_id] = result
        
        if approved:
            draft.status = "approved"
            draft.reviewed_by = reviewer_id
            draft.reviewed_at = get_timestamp()
            draft.review_comments = comments
            self._convert_to_skill(draft)
            logger.info(f"Skill draft manually approved: {draft.skill_name}")
        else:
            draft.status = "rejected"
            draft.reviewed_by = reviewer_id
            draft.reviewed_at = get_timestamp()
            draft.review_comments = comments
            logger.info(f"Skill draft rejected: {draft.skill_name}")
        
        return result
    
    def _convert_to_skill(self, draft: SkillDraft) -> Skill:
        """将草稿转换为正式技能"""
        skill = Skill(
            id=generate_id(),
            name=draft.skill_name,
            description=draft.description,
            type="learned",
            trigger_patterns=draft.trigger_patterns,
            steps=draft.steps,
            metadata={
                "user_id": draft.user_id,
                "draft_id": draft.id,
                "source": "learned",
                "original_context": draft.original_context[:200]
            },
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        skill_manager = get_skill_manager()
        if skill_manager:
            skill_manager.add_skill(skill)
            logger.info(f"Learned skill saved: {skill.name}")
        
        return skill
    
    def get_draft(self, draft_id: str) -> Optional[SkillDraft]:
        """获取技能草稿"""
        return self.drafts.get(draft_id)
    
    def list_drafts(self, user_id: Optional[str] = None, status: Optional[str] = None) -> List[SkillDraft]:
        """列出技能草稿"""
        drafts = list(self.drafts.values())
        
        if user_id:
            drafts = [d for d in drafts if d.user_id == user_id]
        
        if status:
            drafts = [d for d in drafts if d.status == status]
        
        return sorted(drafts, key=lambda x: x.created_at, reverse=True)
    
    def get_verification_result(self, draft_id: str) -> Optional[VerificationResult]:
        """获取验证结果"""
        return self.verification_results.get(draft_id)


# 全局实例
skill_verification_service = SkillVerificationService()
