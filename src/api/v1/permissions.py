"""Permissions HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Any, Depends, Dict, Optional, ValidationException, authenticated_user, db, permission_service, require_admin
)

router = APIRouter()


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str, actor: str = Depends(authenticated_user)):
    if actor != user_id:
        require_admin(actor)
    """获取用户的所有权限"""
    permissions = permission_service.get_user_permissions(user_id)
    return {"permissions": permissions}


@router.post("/users/{user_id}/role")
async def set_user_role(
    user_id: str,
    role: str,
    admin_id: str = Depends(authenticated_user),
    department: Optional[str] = None
):
    """设置用户角色（需要管理员权限）"""
    success = permission_service.set_user_role(admin_id, user_id, role, department)
    if not success:
        raise ValidationException(
            message="设置角色失败",
            detail=f"管理员 {admin_id} 无权设置角色或角色类型无效",
            context={"admin_id": admin_id, "user_id": user_id, "role": role}
        )
    return {"status": "success", "user_id": user_id, "role": role, "department": department}


@router.get("/users/{user_id}/role")
async def get_user_role(user_id: str):
    """获取用户角色信息"""
    role = permission_service.get_user_role(user_id)
    if not role:
        return {"user_id": user_id, "role": "guest", "department": None}
    return {"user_id": user_id, "role": role, "department": db.get_user_department(user_id)}


@router.post("/permissions/skill")
async def grant_skill_permission(permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """授予技能权限"""
    grantor_id = actor
    skill_id = permission_data.get("skill_id")
    user_id = permission_data.get("user_id")
    permission = permission_data.get("permission")

    if not skill_id or not user_id or not permission:
        raise ValidationException(
            message="参数不完整",
            detail="skill_id, user_id 和 permission 字段是必需的",
            context={}
        )

    success = permission_service.grant_skill_permission(grantor_id, skill_id, user_id, permission)
    if not success:
        raise ValidationException(
            message="授权失败",
            detail=f"用户 {grantor_id} 无权授权",
            context={"grantor_id": grantor_id, "skill_id": skill_id, "user_id": user_id}
        )
    return {"status": "success", "message": f"已授予用户 {user_id} {permission} 权限"}


@router.post("/permissions/tool")
async def grant_tool_permission(permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """授予工具权限"""
    grantor_id = actor
    tool_id = permission_data.get("tool_id")
    user_id = permission_data.get("user_id")
    permission = permission_data.get("permission")
    is_hazardous = permission_data.get("is_hazardous", False)

    if not tool_id or not user_id or not permission:
        raise ValidationException(
            message="参数不完整",
            detail="tool_id, user_id 和 permission 字段是必需的",
            context={}
        )

    success = permission_service.grant_tool_permission(grantor_id, tool_id, user_id, permission, is_hazardous)
    if not success:
        raise ValidationException(
            message="授权失败",
            detail=f"用户 {grantor_id} 无权授权或危险工具需要管理员授权",
            context={"grantor_id": grantor_id, "tool_id": tool_id, "user_id": user_id}
        )
    return {"status": "success", "message": f"已授予用户 {user_id} {permission} 权限"}


@router.post("/permissions/memory")
async def grant_memory_permission(permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """授予记忆权限"""
    grantor_id = actor
    memory_type = permission_data.get("memory_type")
    user_id = permission_data.get("user_id")
    permission = permission_data.get("permission")

    if not memory_type or not user_id or not permission:
        raise ValidationException(
            message="参数不完整",
            detail="memory_type, user_id 和 permission 字段是必需的",
            context={}
        )

    success = permission_service.grant_memory_permission(grantor_id, memory_type, user_id, permission)
    if not success:
        raise ValidationException(
            message="授权失败",
            detail=f"用户 {grantor_id} 无权授权",
            context={"grantor_id": grantor_id, "memory_type": memory_type, "user_id": user_id}
        )
    return {"status": "success", "message": f"已授予用户 {user_id} {permission} 权限"}


@router.post("/permissions/department")
async def grant_department_permission(permission_data: Dict[str, Any], actor: str = Depends(authenticated_user)):
    """为部门授予权限"""
    grantor_id = actor
    resource_type = permission_data.get("resource_type")
    resource_id = permission_data.get("resource_id")
    department = permission_data.get("department")
    permissions = permission_data.get("permissions", [])

    if not resource_type or not resource_id or not department:
        raise ValidationException(
            message="参数不完整",
            detail="resource_type, resource_id 和 department 字段是必需的",
            context={}
        )

    success = permission_service.grant_department_permission(grantor_id, resource_type, resource_id, department, permissions)
    if not success:
        raise ValidationException(
            message="授权失败",
            detail=f"用户 {grantor_id} 无权授权",
            context={"grantor_id": grantor_id, "resource_type": resource_type, "department": department}
        )
    return {"status": "success", "message": f"已为部门 {department} 授予权限 {permissions}"}


@router.get("/users/{user_id}/permissions/detail")
async def get_user_permissions_detail(user_id: str, actor: str = Depends(authenticated_user)):
    """获取用户的所有权限详情"""
    if actor != user_id:
        require_admin(actor)
    permissions = permission_service.get_user_permissions(user_id)
    return {"user_id": user_id, "permissions": permissions}


@router.post("/permissions/check/skill")
async def check_skill_permission_v2(skill_id: str, user_id: str, permission: str):
    """检查技能权限"""
    result = permission_service.check_skill_permission(user_id, skill_id, permission)
    return {
        "allowed": result.allowed,
        "missing_permissions": result.missing_permissions,
        "resource_type": result.resource_type,
        "resource_id": result.resource_id
    }


@router.post("/permissions/check/tool")
async def check_tool_permission(tool_id: str, user_id: str, permission: str):
    """检查工具权限"""
    result = permission_service.check_tool_permission(user_id, tool_id, permission)
    return {
        "allowed": result.allowed,
        "missing_permissions": result.missing_permissions,
        "resource_type": result.resource_type,
        "resource_id": result.resource_id
    }


@router.post("/permissions/check/memory")
async def check_memory_permission(memory_type: str, user_id: str, permission: str):
    """检查记忆权限"""
    result = permission_service.check_memory_permission(user_id, memory_type, permission)
    return {
        "allowed": result.allowed,
        "missing_permissions": result.missing_permissions,
        "resource_type": result.resource_type,
        "resource_id": result.resource_id
    }
