"""学习循环模块 - 实现反馈捕获、差异分析、技能提炼与验证

遵循HERMES.md原则：
1. Think Before Coding: 技能生成前必须进行假设澄清
2. Simplicity First: 技能保持极简，不过度设计
3. Surgical Changes: 精准修改，只做必要变更
4. Goal-Driven Execution: 目标可验证，测试闭环
"""
from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep, Intent, CorrectionAnalysis, SkillDraft, VerificationResult, AssumptionChecklist
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.plugins import get_model_router, get_skill_manager, get_memory_store
from src.config import settings
from src.logging_config import get_logger
from src.services.skill_verification import skill_verification_service

logger = get_logger("engine")


class LearningCycle:
    def __init__(self):
        self.pending_corrections: List[Dict[str, Any]] = []
        self.VERIFICATION_THRESHOLD = settings.LEARNING_VERIFICATION_THRESHOLD if hasattr(settings, 'LEARNING_VERIFICATION_THRESHOLD') else 0.7
        # 复杂度阈值（遵循HERMES.md）
        self.COMPLEXITY_THRESHOLDS = {
            'max_steps': 10,
            'max_branches': 3,
            'max_nesting': 2,
            'max_tools': 5
        }
    
    def capture_correction(
        self,
        user_id: str,
        original_output: str,
        corrected_output: str,
        task_context: str,
        user_intent: Optional[str] = None
    ) -> None:
        """
        捕获用户反馈
        
        Args:
            user_id: 用户ID
            original_output: 原始输出
            corrected_output: 修正后的输出
            task_context: 任务上下文
            user_intent: 用户意图（可选）
        """
        correction = {
            "user_id": user_id,
            "original": original_output,
            "corrected": corrected_output,
            "context": task_context,
            "intent": user_intent or self._extract_intent(task_context, original_output),
            "timestamp": get_timestamp()
        }
        self.pending_corrections.append(correction)
        
        logger.info(f"Captured correction from user {user_id}")
        
        # 立即处理单个修正（不再等待批量）
        self.process_single_correction(correction)
    
    def _extract_intent(self, context: str, output: str) -> str:
        """从上下文和输出中提取用户意图"""
        model_router = get_model_router()
        if not model_router:
            return "unknown"
        
        prompt = f"""
        Extract the user's intent from the following context and response:
        
        Context: {context}
        Response: {output}
        
        What was the user trying to accomplish? Keep it concise (1-2 sentences).
        """
        
        try:
            model = model_router.select_model("intent_extraction", "simple")
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            return response.strip()
        except Exception as e:
            logger.error(f"Intent extraction failed: {str(e)}")
            return "unknown"
    
    def process_single_correction(self, correction: Dict[str, Any]) -> None:
        """处理单个修正，执行完整的技能提炼与验证流程（遵循HERMES.md三闸门）"""
        try:
            # === 闸门1: 假设澄清 ===
            checklist = self._clarify_assumptions(correction)
            if not checklist.is_valid:
                logger.info(f"Assumption clarification failed, skipping: {checklist.issues}")
                return
            
            # Step 1: 深度差异分析
            analysis = self._analyze_correction(correction)
            
            # 跳过无价值的修正
            if not analysis.actionable_steps and not analysis.reusable_patterns:
                logger.debug("No actionable content found in correction")
                return
            
            # Step 2: 生成技能草稿（包含假设清单）
            draft = self._generate_skill_draft(correction, analysis, checklist)
            
            # === 闸门2: 复杂度检查 ===
            complexity_result = self._check_complexity(draft)
            if not complexity_result.is_acceptable:
                draft.status = "pending_review"
                draft.metadata["complexity_issues"] = complexity_result.issues
                logger.info(f"Skill complexity exceeds threshold, needs review: {draft.skill_name}")
                skill_verification_service.save_draft(draft)
                return
            
            # Step 3: 自动验证
            # === 闸门3: 测试验证 ===
            verification_result = self._verify_skill_draft(draft)
            
            if verification_result.verified:
                logger.info(f"Skill automatically verified: {draft.skill_name}")
            else:
                logger.info(f"Skill needs manual review: {draft.skill_name}")
                
        except Exception as e:
            logger.error(f"Processing correction failed: {str(e)}", exc_info=True)
    
    def _clarify_assumptions(self, correction: Dict[str, Any]) -> AssumptionChecklist:
        """
        假设澄清 - HERMES.md第一道闸门
        
        在生成技能草稿前，先分析并列出所有假设、方案和风险点，
        确保Agent理解正确，避免"瞎做"
        """
        model_router = get_model_router()
        if not model_router:
            return AssumptionChecklist(
                is_valid=False,
                issues=["No model router available for assumption clarification"]
            )
        
        prompt = f"""
        Analyze the following user feedback and generate an assumption checklist:
        
        User Intent: {correction.get('intent', 'unknown')}
        Original Output: {correction.get('original', '')}
        Corrected Output: {correction.get('corrected', '')}
        Context: {correction.get('context', '')}
        
        Please answer the following questions:
        
        1. What is the user's core need? (1-2 sentences)
        2. Are there any ambiguities or points that need confirmation?
        3. What system resources are involved? (files, APIs, databases)
        4. Are special permissions required? If yes, what kind?
        5. What exceptions might occur during execution?
        6. Are there any compliance risks?
        
        Format your response as JSON with the following structure:
        {{
            "core_need": "...",
            "ambiguities": ["...", "..."],
            "resources": ["...", "..."],
            "permissions_needed": ["...", "..."],
            "potential_exceptions": ["...", "..."],
            "compliance_risks": ["...", "..."],
            "is_understanding_clear": true/false,
            "confidence_score": 0.0-1.0
        }}
        """
        
        try:
            model = model_router.select_model("analysis", "simple")
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            
            import json
            result = json.loads(response)
            
            issues = []
            if not result.get("is_understanding_clear", False):
                issues.append("Understanding not clear")
            if result.get("confidence_score", 0) < 0.7:
                issues.append(f"Low confidence score: {result.get('confidence_score')}")
            if len(result.get("ambiguities", [])) > 0:
                issues.append(f"Unresolved ambiguities: {', '.join(result['ambiguities'])}")
            
            return AssumptionChecklist(
                is_valid=len(issues) == 0,
                core_need=result.get("core_need", ""),
                ambiguities=result.get("ambiguities", []),
                resources=result.get("resources", []),
                permissions_needed=result.get("permissions_needed", []),
                potential_exceptions=result.get("potential_exceptions", []),
                compliance_risks=result.get("compliance_risks", []),
                confidence_score=result.get("confidence_score", 0),
                issues=issues
            )
        except Exception as e:
            logger.error(f"Assumption clarification failed: {str(e)}")
            return AssumptionChecklist(
                is_valid=False,
                issues=[f"Clarification failed: {str(e)}"]
            )
    
    def _check_complexity(self, draft: SkillDraft) -> Dict[str, Any]:
        """
        复杂度检查 - HERMES.md第二道闸门
        
        检查技能草稿的复杂度是否在允许范围内
        """
        issues = []
        steps = draft.steps or []
        
        # 检查步骤数
        if len(steps) > self.COMPLEXITY_THRESHOLDS['max_steps']:
            issues.append(f"Steps ({len(steps)}) exceed threshold ({self.COMPLEXITY_THRESHOLDS['max_steps']})")
        
        # 检查条件分支数
        branch_count = sum(1 for step in steps if 'if' in step.action.lower() or 'branch' in step.action.lower())
        if branch_count > self.COMPLEXITY_THRESHOLDS['max_branches']:
            issues.append(f"Branches ({branch_count}) exceed threshold ({self.COMPLEXITY_THRESHOLDS['max_branches']})")
        
        # 检查嵌套深度（简单估算）
        nesting_count = sum(step.parameters.get('nesting_level', 0) for step in steps)
        if nesting_count > self.COMPLEXITY_THRESHOLDS['max_nesting']:
            issues.append(f"Nesting depth ({nesting_count}) exceed threshold ({self.COMPLEXITY_THRESHOLDS['max_nesting']})")
        
        # 检查工具调用数
        tool_count = sum(1 for step in steps if step.action == 'execute')
        if tool_count > self.COMPLEXITY_THRESHOLDS['max_tools']:
            issues.append(f"Tool calls ({tool_count}) exceed threshold ({self.COMPLEXITY_THRESHOLDS['max_tools']})")
        
        return {
            'is_acceptable': len(issues) == 0,
            'issues': issues,
            'step_count': len(steps),
            'branch_count': branch_count,
            'nesting_count': nesting_count,
            'tool_count': tool_count
        }
    
    def _analyze_correction(self, correction: Dict[str, Any]) -> CorrectionAnalysis:
        """
        深度分析修正内容
        
        不仅对比原始回复与修正回复，还结合对话上下文、用户意图，
        提炼可复用的"触发条件+执行步骤"
        """
        return skill_verification_service.analyze_correction(
            user_id=correction["user_id"],
            original_output=correction["original"],
            corrected_output=correction["corrected"],
            context=correction["context"],
            user_intent=correction["intent"]
        )
    
    def _generate_skill_draft(self, correction: Dict[str, Any], analysis: CorrectionAnalysis, 
                              checklist: Optional[AssumptionChecklist] = None) -> SkillDraft:
        """根据分析结果生成技能草稿（包含假设清单）"""
        draft = skill_verification_service.generate_skill_draft(
            user_id=correction["user_id"],
            analysis=analysis,
            context=correction["context"],
            user_intent=correction["intent"]
        )
        
        # 将假设清单存入metadata，便于管理员审核
        if checklist:
            draft.metadata["assumption_checklist"] = {
                "core_need": checklist.core_need,
                "ambiguities": checklist.ambiguities,
                "resources": checklist.resources,
                "permissions_needed": checklist.permissions_needed,
                "potential_exceptions": checklist.potential_exceptions,
                "compliance_risks": checklist.compliance_risks,
                "confidence_score": checklist.confidence_score
            }
        
        # 设置为待审核状态（默认）
        draft.status = "pending_review"
        return draft
    
    def _verify_skill_draft(self, draft: SkillDraft) -> VerificationResult:
        """验证技能草稿"""
        # 先尝试自动验证
        result = skill_verification_service.auto_verify(draft.id)
        
        # 如果自动验证不通过，检查是否需要人工审核
        if not result.verified:
            # 可以在这里添加通知机制，通知管理员进行人工审核
            self._notify_for_review(draft)
        
        return result
    
    def _notify_for_review(self, draft: SkillDraft) -> None:
        """通知管理员进行人工审核"""
        logger.info(f"Skill draft '{draft.skill_name}' needs manual review. Draft ID: {draft.id}")
        
        # 可以扩展：发送通知到IM、邮件等
        # 例如：通过飞书机器人通知管理员
    
    def process_corrections(self) -> None:
        """批量处理待处理的修正（兼容旧接口）"""
        for correction in self.pending_corrections:
            self.process_single_correction(correction)
        
        self.pending_corrections = []
    
    def manual_review_skill(self, draft_id: str, approved: bool, reviewer_id: str, comments: str = "") -> VerificationResult:
        """
        人工审核技能草稿
        
        Args:
            draft_id: 草稿ID
            approved: 是否批准
            reviewer_id: 审核者ID
            comments: 审核意见
        
        Returns:
            验证结果
        """
        return skill_verification_service.manual_review(
            draft_id=draft_id,
            approved=approved,
            reviewer_id=reviewer_id,
            comments=comments
        )
    
    def get_pending_reviews(self) -> List[SkillDraft]:
        """获取待审核的技能草稿"""
        return skill_verification_service.list_drafts(status="pending_review")
    
    def get_skill_draft(self, draft_id: str) -> Optional[SkillDraft]:
        """获取技能草稿详情"""
        return skill_verification_service.get_draft(draft_id)
    
    def suggest_skill_creation(self, user_id: str, task_description: str) -> Optional[Skill]:
        """基于任务描述建议创建技能"""
        # 分析任务是否适合创建技能
        prompt = f"""
        Analyze the following task and determine if it should be saved as a reusable skill:
        
        Task: {task_description}
        
        Consider:
        1. Is this task repetitive or likely to be performed again?
        2. Does it have clear, defined steps?
        3. Can it be parameterized for different inputs?
        
        If YES, provide in JSON format:
        {{
            "skill_name": "...",
            "description": "...",
            "trigger_patterns": [...],
            "steps": [...]
        }}
        
        If NO, respond with: NOT_A_SKILL
        """
        
        model_router = get_model_router()
        if not model_router:
            return None
        
        try:
            model = model_router.select_model("skill_analysis", "simple")
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            
            if response.strip() == "NOT_A_SKILL":
                return None
            
            import json
            result = json.loads(response)
            
            skill = Skill(
                id=generate_id(),
                name=result["skill_name"],
                description=result["description"],
                type="learned",
                trigger_patterns=result["trigger_patterns"],
                steps=[SkillStep(**step) for step in result["steps"]],
                metadata={"user_id": user_id, "source": "suggested"},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            )
            
            # 直接保存建议的技能
            skill_manager = get_skill_manager()
            if skill_manager:
                skill_manager.add_skill(skill)
                logger.info(f"Suggested skill created: {skill.name}")
            
            return skill
        except Exception as e:
            logger.error(f"Skill suggestion failed: {str(e)}")
            return None
    
    def get_learning_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """获取学习统计信息"""
        drafts = skill_verification_service.list_drafts(user_id=user_id)
        
        stats = {
            "total_drafts": len(drafts),
            "approved_count": len([d for d in drafts if d.status == "approved"]),
            "rejected_count": len([d for d in drafts if d.status == "rejected"]),
            "pending_count": len([d for d in drafts if d.status == "pending_review"]),
            "draft_count": len([d for d in drafts if d.status == "draft"])
        }
        
        return stats


# 全局实例
learning_cycle = LearningCycle()
