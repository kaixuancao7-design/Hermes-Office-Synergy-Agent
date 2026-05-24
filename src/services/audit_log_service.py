"""审计日志服务"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("service")


@dataclass
class AuditLog:
    """审计日志条目"""
    id: str
    user_id: str
    action: str
    resource: str
    timestamp: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)


class AuditLogService:
    """审计日志服务"""
    
    def __init__(self):
        self.logs: Dict[str, AuditLog] = {}
    
    def log_action(self, user_id: str, action: str, resource: str, details: Optional[Dict[str, Any]] = None) -> None:
        """记录操作日志"""
        log_entry = AuditLog(
            id=generate_id(),
            user_id=user_id,
            action=action,
            resource=resource,
            timestamp=get_timestamp(),
            status="success",
            details=details or {}
        )
        
        self.logs[log_entry.id] = log_entry
        
        logger.info(f"[AUDIT] {action}: user_id={user_id}, resource={resource}")
    
    def log_error(self, user_id: str, action: str, resource: str, error: str) -> None:
        """记录错误日志"""
        log_entry = AuditLog(
            id=generate_id(),
            user_id=user_id,
            action=action,
            resource=resource,
            timestamp=get_timestamp(),
            status="failed",
            details={"error": error}
        )
        
        self.logs[log_entry.id] = log_entry
        
        logger.error(f"[AUDIT] {action} failed: user_id={user_id}, resource={resource}, error={error}")
    
    def get_user_logs(self, user_id: str, limit: int = 20) -> List[AuditLog]:
        """获取用户操作日志"""
        user_logs = [log for log in self.logs.values() if log.user_id == user_id]
        user_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return user_logs[:limit]
    
    def get_resource_logs(self, resource: str, limit: int = 20) -> List[AuditLog]:
        """获取资源操作日志"""
        resource_logs = [log for log in self.logs.values() if log.resource == resource]
        resource_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return resource_logs[:limit]


# 全局实例
audit_log_service = AuditLogService()
