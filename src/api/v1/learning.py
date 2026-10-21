"""Learning HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Any, Depends, Dict, NotFoundException, Optional, ValidationException, authenticated_user, learning_cycle, permission_service, require_admin, skill_verification_service
)

router = APIRouter()


@router.post("/feedback")
async def submit_feedback(feedback: Dict[str, Any], actor: str = Depends(authenticated_user)):
    user_id = actor
    original = feedback.get("original", "")
    corrected = feedback.get("corrected", "")
    context = feedback.get("context", "")
    intent = feedback.get("intent", "")

    if not original or not corrected:
        raise ValidationException(
            message="反馈内容不完整",
            detail="original 和 corrected 字段都是必需的",
            context={"user_id": user_id}
        )

    learning_cycle.capture_correction(user_id, original, corrected, context, intent)
    return {"status": "success"}


@router.get("/skill-drafts")
async def get_skill_drafts(status: Optional[str] = None, user_id: Optional[str] = None, actor: str = Depends(authenticated_user)):
    """获取技能草稿列表"""
    if user_id is None and permission_service.get_user_role(actor) != "admin":
        user_id = actor
    if user_id is not None and actor != user_id:
        require_admin(actor)
    drafts = skill_verification_service.list_drafts(user_id=user_id, status="pending_review" if status == "pending" else status)
    return {"drafts": [draft.model_dump() for draft in drafts]}


@router.get("/skill-drafts/{draft_id}")
async def get_skill_draft(draft_id: str, actor: str = Depends(authenticated_user)):
    """获取技能草稿详情"""
    draft = learning_cycle.get_skill_draft(draft_id)
    if not draft:
        raise NotFoundException(
            message="技能草稿不存在",
            detail=f"未找到ID为 {draft_id} 的技能草稿",
            context={"draft_id": draft_id}
        )
    if draft.user_id != actor:
        require_admin(actor)
    return {"draft": draft.model_dump()}


@router.post("/skill-drafts/{draft_id}/review")
async def review_skill_draft(draft_id: str, review_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """人工审核技能草稿"""
    approved = review_data.get("approved", False)
    if not isinstance(approved, bool):
        raise ValidationException(message="approved 必须为布尔值")
    reviewer_id = actor
    comments = review_data.get("comments", "")

    require_admin(actor)
    try:
        result = learning_cycle.manual_review_skill(draft_id, approved, reviewer_id, comments)
    except ValueError as exc:
        raise ValidationException(message="草稿未通过发布校验", detail=str(exc))
    if result is None:
        raise NotFoundException(message="草稿不存在或不能发布")

    return {"result": result.model_dump()}


@router.get("/learning/stats")
async def get_learning_stats(user_id: Optional[str] = None, actor: str = Depends(authenticated_user)):
    """获取学习统计信息"""
    if user_id is None and permission_service.get_user_role(actor) != "admin":
        user_id = actor
    if user_id is not None and actor != user_id:
        require_admin(actor)
    stats = learning_cycle.get_learning_stats(user_id=user_id)
    return {"stats": stats}


@router.post("/learning/suggest-skill")
async def suggest_skill(task_description: str, user_id: str = Depends(authenticated_user)):
    """建议创建技能"""
    skill = learning_cycle.suggest_skill_creation(user_id, task_description)
    if skill:
        return {"skill": skill.model_dump()}
    return {"message": "This task is not suitable for skill creation"}
