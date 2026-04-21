from fastapi import APIRouter, Query
from typing import Dict, Any, Optional, List
from src.types import Message, Skill, UserProfile, SkillDraft, VerificationResult, AuditQueryResult
from src.gateway.message_router import message_router
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.skills.skill_manager import skill_manager
from src.engine.memory_manager import memory_manager
from src.engine.learning_cycle import learning_cycle
from src.services.skill_verification import skill_verification_service
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service
from src.utils import generate_id, get_timestamp
from src.exceptions import (
    SkillException,
    MemoryException,
    NotFoundException,
    ValidationException,
    IMException
)
from src.logging_config import get_logger

router = APIRouter(prefix="/api/v1")
logger = get_logger("api")


@router.post("/message")
async def send_message(message: Dict[str, Any]):
    user_id = message.get("user_id", "default_user")
    content = message.get("content", "")
    
    if not content:
        raise ValidationException(
            message="内容不能为空",
            detail="message.content 字段是必需的",
            context={"user_id": user_id}
        )
    
    msg = Message(
        id=generate_id(),
        user_id=user_id,
        content=content,
        role="user",
        timestamp=get_timestamp(),
        metadata=message.get("metadata")
    )
    
    response = message_router.route(msg)
    return {"response": response}


@router.post("/im/webhook/{adapter_type}")
async def im_webhook(adapter_type: str, payload: Dict[str, Any]):
    from src.utils import setup_logging
    from src.config import settings
    logger = setup_logging(settings.LOG_LEVEL)
    
    logger.info(f"Received webhook from {adapter_type}: {str(payload)[:500]}")
    
    adapter = im_adapter_manager.get_adapter(adapter_type)
    if not adapter:
        raise NotFoundException(
            message=f"适配器 {adapter_type} 不存在",
            detail=f"未找到类型为 {adapter_type} 的IM适配器",
            context={"adapter_type": adapter_type}
        )
    
    message = adapter.receive_message(payload)
    if not message:
        logger.info("Message ignored (adapter disabled or parsing failed)")
        return {"status": "ignored"}
    
    logger.info(f"Parsed message: user_id={message.user_id}, content={message.content[:100]}")
    
    response = message_router.route(message)
    logger.info(f"Generated response: {response[:100]}")
    
    try:
        adapter.send_message(Message(
            id=generate_id(),
            user_id=message.user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp()
        ))
    except Exception as e:
        raise IMException(
            message="发送消息失败",
            detail=str(e),
            context={"user_id": message.user_id, "adapter_type": adapter_type}
        )
    
    logger.info(f"Message sent successfully to user {message.user_id}")
    return {"status": "success", "response": response}


@router.get("/skills")
async def get_skills():
    skills = skill_manager.get_all_skills()
    return {"skills": [skill.model_dump() for skill in skills]}


@router.post("/skills")
async def create_skill(skill_data: Dict[str, Any]):
    user_id = skill_data.get("user_id", "default_user")
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
async def execute_skill(skill_id: str, user_id: str = "default_user"):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise NotFoundException(
            message="技能不存在",
            detail=f"未找到ID为 {skill_id} 的技能",
            context={"skill_id": skill_id, "user_id": user_id}
        )
    
    skill = skill_manager.apply_user_preferences(skill, user_id)
    
    results = []
    for step in skill.steps:
        results.append(f"{step.action}: {step.parameters}")
    
    return {"results": results}


@router.get("/user/{user_id}")
async def get_user_profile(user_id: str):
    profile = memory_manager.get_user_profile(user_id)
    if not profile:
        raise NotFoundException(
            message="用户不存在",
            detail=f"未找到ID为 {user_id} 的用户",
            context={"user_id": user_id}
        )
    return {"profile": profile.model_dump()}


@router.put("/user/{user_id}")
async def update_user_profile(user_id: str, updates: Dict[str, Any]):
    if not updates:
        raise ValidationException(
            message="更新内容不能为空",
            detail="updates 字段不能为空",
            context={"user_id": user_id}
        )
    
    memory_manager.update_user_profile(user_id, updates)
    return {"status": "success"}


@router.post("/adapters/register")
async def register_adapter(config: IMAdapterConfig):
    if not config.type:
        raise ValidationException(
            message="适配器类型不能为空",
            detail="type 字段是必需的",
            context={"config": config.model_dump()}
        )
    
    im_adapter_manager.register_adapter(config)
    return {"status": "success"}


@router.get("/memory/search")
async def search_memory(user_id: str, query: str):
    if not query:
        raise ValidationException(
            message="搜索关键词不能为空",
            detail="query 字段是必需的",
            context={"user_id": user_id}
        )
    
    results = memory_manager.search_long_term_memory(user_id, query)
    return {"results": [r.model_dump() for r in results]}


@router.post("/feedback")
async def submit_feedback(feedback: Dict[str, Any]):
    user_id = feedback.get("user_id", "default_user")
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


# ==================== 技能验证相关接口 ====================

@router.get("/skill-drafts")
async def get_skill_drafts(status: Optional[str] = None, user_id: Optional[str] = None):
    """获取技能草稿列表"""
    drafts = learning_cycle.get_pending_reviews() if status == "pending" else skill_verification_service.list_drafts(user_id=user_id, status=status)
    return {"drafts": [draft.model_dump() for draft in drafts]}


@router.get("/skill-drafts/{draft_id}")
async def get_skill_draft(draft_id: str):
    """获取技能草稿详情"""
    draft = learning_cycle.get_skill_draft(draft_id)
    if not draft:
        raise NotFoundException(
            message="技能草稿不存在",
            detail=f"未找到ID为 {draft_id} 的技能草稿",
            context={"draft_id": draft_id}
        )
    return {"draft": draft.model_dump()}


@router.post("/skill-drafts/{draft_id}/review")
async def review_skill_draft(draft_id: str, review_data: Dict[str, Any]):
    """人工审核技能草稿"""
    approved = review_data.get("approved", False)
    reviewer_id = review_data.get("reviewer_id", "admin")
    comments = review_data.get("comments", "")
    
    result = learning_cycle.manual_review_skill(
        draft_id=draft_id,
        approved=approved,
        reviewer_id=reviewer_id,
        comments=comments
    )
    
    return {"result": result.model_dump()}


@router.get("/learning/stats")
async def get_learning_stats(user_id: Optional[str] = None):
    """获取学习统计信息"""
    stats = learning_cycle.get_learning_stats(user_id=user_id)
    return {"stats": stats}


@router.post("/learning/suggest-skill")
async def suggest_skill(task_description: str, user_id: str = "default_user"):
    """建议创建技能"""
    skill = learning_cycle.suggest_skill_creation(user_id, task_description)
    if skill:
        return {"skill": skill.model_dump()}
    return {"message": "This task is not suitable for skill creation"}


# ==================== 技能版本管理接口 ====================

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
async def rollback_skill(skill_id: str, version: str, user_id: str = "admin"):
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


# ==================== 技能权限控制接口 ====================

@router.post("/users/{user_id}/role")
async def set_user_role(user_id: str, role: str, admin_id: str = "admin"):
    """设置用户角色（需要管理员权限）"""
    success = skill_manager.set_user_role(admin_id, user_id, role)
    if not success:
        raise ValidationException(
            message="设置角色失败",
            detail=f"管理员 {admin_id} 无权设置角色或角色类型无效",
            context={"admin_id": admin_id, "user_id": user_id, "role": role}
        )
    return {"status": "success", "user_id": user_id, "role": role}


@router.get("/users/{user_id}/role")
async def get_user_role(user_id: str):
    """获取用户角色"""
    role = skill_manager.skill_permission_manager.get_user_role(user_id)
    if not role:
        return {"user_id": user_id, "role": "guest"}
    return {"user_id": user_id, "role": role}


@router.post("/skills/{skill_id}/permissions")
async def grant_permission(skill_id: str, permission_data: Dict[str, Any]):
    """授予用户技能权限"""
    grantor_id = permission_data.get("grantor_id", "admin")
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
async def revoke_permission(skill_id: str, permission_data: Dict[str, Any]):
    """撤销用户技能权限"""
    revoker_id = permission_data.get("revoker_id", "admin")
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
async def get_skill_permissions(skill_id: str):
    """获取技能的所有权限"""
    permissions = skill_manager.skill_permission_manager.get_skill_permissions(skill_id)
    return {"permissions": [p.model_dump() for p in permissions]}


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str):
    """获取用户的所有权限"""
    permissions = skill_manager.skill_permission_manager.get_user_permissions(user_id)
    return {"permissions": permissions}


@router.post("/skills/{skill_id}/check-permission")
async def check_skill_permission(skill_id: str, user_id: str, permission: str):
    """检查用户是否有指定权限"""
    result = skill_manager.check_permission(user_id, skill_id, permission)
    return {"allowed": result.allowed, "missing_permissions": result.missing_permissions}


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, updates: Dict[str, Any], user_id: str = "admin"):
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
    except PermissionError as e:
        raise ValidationException(
            message="权限不足",
            detail=str(e),
            context={"user_id": user_id}
        )


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, user_id: str = "admin"):
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


# ==================== 细粒度权限管理接口 ====================

@router.post("/users/{user_id}/role")
async def set_user_role(
    user_id: str,
    role: str,
    admin_id: str = "admin",
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
    return {"user_id": user_id, "role": role.role, "department": role.department}


@router.post("/permissions/skill")
async def grant_skill_permission(permission_data: Dict[str, Any]):
    """授予技能权限"""
    grantor_id = permission_data.get("grantor_id", "admin")
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
async def grant_tool_permission(permission_data: Dict[str, Any]):
    """授予工具权限"""
    grantor_id = permission_data.get("grantor_id", "admin")
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
async def grant_memory_permission(permission_data: Dict[str, Any]):
    """授予记忆权限"""
    grantor_id = permission_data.get("grantor_id", "admin")
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
async def grant_department_permission(permission_data: Dict[str, Any]):
    """为部门授予权限"""
    grantor_id = permission_data.get("grantor_id", "admin")
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
async def get_user_permissions_detail(user_id: str):
    """获取用户的所有权限详情"""
    permissions = permission_service.get_user_permissions(user_id)
    return {"user_id": user_id, "permissions": permissions}


@router.post("/permissions/check/skill")
async def check_skill_permission(skill_id: str, user_id: str, permission: str):
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


# ==================== 审计日志接口 ====================

@router.get("/audit/logs")
async def query_audit_logs(
    operator_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    result: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """查询审计日志"""
    result = audit_log_service.query_logs(
        operator_id=operator_id,
        operation_type=operation_type,
        target_type=target_type,
        target_id=target_id,
        start_time=start_time,
        end_time=end_time,
        result=result,
        page=page,
        page_size=page_size
    )
    return {
        "logs": [log.model_dump() for log in result.logs],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size
    }


@router.get("/audit/logs/{log_id}")
async def get_audit_log(log_id: str):
    """获取审计日志详情"""
    log = audit_log_service.get_log_by_id(log_id)
    if not log:
        raise NotFoundException(
            message="日志不存在",
            detail=f"未找到ID为 {log_id} 的审计日志",
            context={"log_id": log_id}
        )
    return {"log": log.model_dump()}


@router.get("/audit/logs/operator/{operator_id}")
async def get_operator_logs(operator_id: str):
    """获取指定用户的所有操作日志"""
    logs = audit_log_service.get_operator_logs(operator_id)
    return {"operator_id": operator_id, "logs": [log.model_dump() for log in logs]}


@router.get("/audit/logs/type/{operation_type}")
async def get_logs_by_type(operation_type: str):
    """获取指定类型的操作日志"""
    logs = audit_log_service.get_logs_by_type(operation_type)
    return {"operation_type": operation_type, "logs": [log.model_dump() for log in logs]}


@router.post("/audit/verify")
async def verify_log_integrity():
    """验证审计日志完整性"""
    integrity = audit_log_service.verify_log_integrity()
    return {"integrity_ok": integrity}


@router.post("/audit/export")
async def export_audit_logs(file_path: str):
    """导出审计日志到文件"""
    success = audit_log_service.export_logs(file_path)
    if not success:
        raise ValidationException(
            message="导出失败",
            detail=f"无法导出日志到 {file_path}",
            context={"file_path": file_path}
        )
    return {"status": "success", "message": f"日志已导出到 {file_path}"}
