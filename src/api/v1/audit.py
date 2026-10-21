"""Audit HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Depends, NotFoundException, Optional, Query, ValidationException, audit_log_service, authenticated_user, require_admin
)

router = APIRouter()


@router.get("/audit/logs")
async def query_audit_logs(
    operator_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    result: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    actor: str = Depends(authenticated_user)
):
    """查询审计日志"""
    require_admin(actor)
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
async def get_audit_log(log_id: str, actor: str = Depends(authenticated_user)):
    """获取审计日志详情"""
    require_admin(actor)
    log = audit_log_service.get_log_by_id(log_id)
    if not log:
        raise NotFoundException(
            message="日志不存在",
            detail=f"未找到ID为 {log_id} 的审计日志",
            context={"log_id": log_id}
        )
    return {"log": log.model_dump()}


@router.get("/audit/logs/operator/{operator_id}")
async def get_operator_logs(operator_id: str, actor: str = Depends(authenticated_user)):
    """获取指定用户的所有操作日志"""
    require_admin(actor)
    logs = audit_log_service.get_operator_logs(operator_id)
    return {"operator_id": operator_id, "logs": [log.model_dump() for log in logs]}


@router.get("/audit/logs/type/{operation_type}")
async def get_logs_by_type(operation_type: str, actor: str = Depends(authenticated_user)):
    """获取指定类型的操作日志"""
    require_admin(actor)
    logs = audit_log_service.get_logs_by_type(operation_type)
    return {"operation_type": operation_type, "logs": [log.model_dump() for log in logs]}


@router.post("/audit/verify")
async def verify_log_integrity(actor: str = Depends(authenticated_user)):
    """验证审计日志完整性"""
    require_admin(actor)
    integrity = audit_log_service.verify_log_integrity()
    return {"integrity_ok": integrity}


@router.post("/audit/export")
async def export_audit_logs(file_path: str, actor: str = Depends(authenticated_user)):
    """导出审计日志到文件"""
    require_admin(actor)
    success = audit_log_service.export_logs(file_path)
    if not success:
        raise ValidationException(
            message="导出失败",
            detail=f"无法导出日志到 {file_path}",
            context={"file_path": file_path}
        )
    return {"status": "success", "message": f"日志已导出到 {file_path}"}
