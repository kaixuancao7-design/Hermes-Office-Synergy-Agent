"""Skills HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Any, Depends, Dict, HTTPException, NotFoundException, ValidationException, authenticated_user, db, skill_manager
)

router = APIRouter()


@router.get("/skills")
async def get_skills():
    skills = skill_manager.get_all_skills()
    return {"skills": [skill.model_dump() for skill in skills]}


@router.post("/skills")
async def create_skill(skill_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    user_id = actor
    name = skill_data.get("name", "")
    description = skill_data.get("description", "")
    steps = skill_data.get("steps", [])

    if not name:
        raise ValidationException(
            message="技能名称不能为空",
            detail="name 字段是必需的",
            context={"user_id": user_id}
        )

    if not steps:
        raise ValidationException(
            message="技能步骤不能为空",
            detail="steps 字段是必需的，至少需要一个步骤",
            context={"user_id": user_id, "skill_name": name}
        )

    skill = skill_manager.create_custom_skill(user_id, name, description, steps)
    return {"skill": skill.model_dump()}


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise NotFoundException(
            message="技能不存在",
            detail=f"未找到ID为 {skill_id} 的技能",
            context={"skill_id": skill_id}
        )
    return {"skill": skill.model_dump()}


@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, user_id: str = Depends(authenticated_user), query: str = ""):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise NotFoundException(
            message="技能不存在",
            detail=f"未找到ID为 {skill_id} 的技能",
            context={"skill_id": skill_id, "user_id": user_id}
        )

    skill = skill_manager.apply_user_preferences(skill, user_id)

    if not skill_manager.can_execute_skill(user_id, skill_id):
        raise HTTPException(status_code=403, detail="没有执行技能的权限")
    from src.engine.skill_executor import skill_executor
    result = await skill_executor.execute_skill(skill, query, user_id)
    return {"results": result.step_results, "response": result.response,
            "steps_executed": result.steps_executed, "steps_failed": result.steps_failed}


@router.get("/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: str):
    """获取技能的所有版本"""
    versions = skill_manager.get_skill_versions(skill_id)
    return {"versions": [v.model_dump() for v in versions]}


@router.get("/skills/{skill_id}/versions/{version}")
async def get_skill_version(skill_id: str, version: str):
    """获取指定版本的技能"""
    version_data = skill_manager.get_skill_version(skill_id, version)
    if not version_data:
        raise NotFoundException(
            message="版本不存在",
            detail=f"未找到技能 {skill_id} 的版本 {version}",
            context={"skill_id": skill_id, "version": version}
        )
    return {"version": version_data.model_dump()}


@router.post("/skills/{skill_id}/rollback/{version}")
async def rollback_skill(skill_id: str, version: str, user_id: str = Depends(authenticated_user)):
    """回滚到指定版本"""
    try:
        skill = skill_manager.rollback_to_version(user_id, skill_id, version)
        if not skill:
            raise NotFoundException(
                message="回滚失败",
                detail=f"无法回滚到版本 {version}",
                context={"skill_id": skill_id, "version": version, "user_id": user_id}
            )
        return {"skill": skill.model_dump(), "message": f"已回滚到版本 {version}"}
    except PermissionError as e:
        raise ValidationException(
            message="权限不足",
            detail=str(e),
            context={"user_id": user_id}
        )


@router.get("/skills/{skill_id}/change-logs")
async def get_skill_change_logs(skill_id: str):
    """获取技能的修改日志"""
    logs = skill_manager.get_skill_change_logs(skill_id)
    return {"logs": [log.model_dump() for log in logs]}


@router.post("/skills/{skill_id}/permissions")
async def grant_permission(skill_id: str, permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """授予用户技能权限"""
    grantor_id = actor
    user_id = permission_data.get("user_id")
    permission = permission_data.get("permission")

    if not user_id or not permission:
        raise ValidationException(
            message="参数不完整",
            detail="user_id 和 permission 字段是必需的",
            context={"skill_id": skill_id}
        )

    success = skill_manager.grant_permission(grantor_id, skill_id, user_id, permission)
    if not success:
        raise ValidationException(
            message="授权失败",
            detail=f"用户 {grantor_id} 无权授权或权限类型无效",
            context={"grantor_id": grantor_id, "skill_id": skill_id, "user_id": user_id}
        )
    return {"status": "success", "message": f"已授予用户 {user_id} {permission} 权限"}


@router.delete("/skills/{skill_id}/permissions")
async def revoke_permission(skill_id: str, permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """撤销用户技能权限"""
    revoker_id = actor
    user_id = permission_data.get("user_id")
    permission = permission_data.get("permission")

    if not user_id or not permission:
        raise ValidationException(
            message="参数不完整",
            detail="user_id 和 permission 字段是必需的",
            context={"skill_id": skill_id}
        )

    success = skill_manager.revoke_permission(revoker_id, skill_id, user_id, permission)
    if not success:
        raise ValidationException(
            message="撤销权限失败",
            detail=f"用户 {revoker_id} 无权撤销权限",
            context={"revoker_id": revoker_id, "skill_id": skill_id, "user_id": user_id}
        )
    return {"status": "success", "message": f"已撤销用户 {user_id} 的 {permission} 权限"}


@router.get("/skills/{skill_id}/permissions")
async def get_skill_permissions(skill_id: str, actor: str = Depends(authenticated_user)):
    """获取技能的所有权限"""
    if not skill_manager.check_permission(actor, skill_id, "grant").allowed:
        raise HTTPException(status_code=403, detail="没有查看技能授权的权限")
    permissions = db.get_resource_permissions("skill", skill_id)
    return {"permissions": permissions}


@router.post("/skills/{skill_id}/check-permission")
async def check_skill_permission(skill_id: str, user_id: str, permission: str):
    """检查用户是否有指定权限"""
    result = skill_manager.check_permission(user_id, skill_id, permission)
    return {"allowed": result.allowed, "missing_permissions": result.missing_permissions}


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, updates: Dict[str, Any], user_id: str = Depends(authenticated_user)):
    """更新技能（需要编辑权限）"""
    try:
        skill = skill_manager.update_skill(user_id, skill_id, updates)
        if not skill:
            raise NotFoundException(
                message="技能不存在",
                detail=f"未找到ID为 {skill_id} 的技能",
                context={"skill_id": skill_id}
            )
        return {"skill": skill.model_dump()}
    except ValueError as e:
        raise ValidationException(message="技能参数无效", detail=str(e))
    except PermissionError as e:
        raise ValidationException(
            message="权限不足",
            detail=str(e),
            context={"user_id": user_id}
        )


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, user_id: str = Depends(authenticated_user)):
    """删除技能（需要删除权限）"""
    try:
        success = skill_manager.delete_skill(user_id, skill_id)
        if not success:
            raise NotFoundException(
                message="技能不存在",
                detail=f"未找到ID为 {skill_id} 的技能",
                context={"skill_id": skill_id}
            )
        return {"status": "success", "message": "技能已删除"}
    except PermissionError as e:
        raise ValidationException(
            message="权限不足",
            detail=str(e),
            context={"user_id": user_id}
        )
