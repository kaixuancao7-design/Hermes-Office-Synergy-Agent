"""审计日志服务"""
from typing import List, Dict, Any, Optional
from src.types import AuditLog, AuditQueryResult
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
import hashlib

logger = get_logger("services")


class AuditLogService:
    """审计日志服务 - 提供不可篡改的操作记录"""
    
    def __init__(self):
        self.logs: List[AuditLog] = []
        self.logs_by_operator: Dict[str, List[AuditLog]] = {}  # operator_id -> logs
        self.logs_by_type: Dict[str, List[AuditLog]] = {}  # operation_type -> logs
        self._previous_checksum = "0" * 64  # 初始校验和
    
    def _generate_checksum(self, log: AuditLog) -> str:
        """生成日志校验和（SHA-256）"""
        data = f"{log.id}{log.operation_type}{log.operator_id}{log.operation_detail}{log.timestamp}{log.result}"
        combined = f"{self._previous_checksum}{data}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def log_operation(
        self,
        operation_type: str,
        operator_id: str,
        operation_detail: str,
        result: str = "success",
        error_message: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        operator_name: Optional[str] = None,
        operator_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AuditLog:
        """记录操作日志"""
        log = AuditLog(
            id=generate_id(),
            operation_type=operation_type,
            operator_id=operator_id,
            operator_name=operator_name,
            operator_role=operator_role,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            operation_detail=operation_detail,
            result=result,
            error_message=error_message,
            timestamp=get_timestamp(),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            checksum="",
            previous_checksum=self._previous_checksum
        )
        
        # 生成校验和
        log.checksum = self._generate_checksum(log)
        self._previous_checksum = log.checksum
        
        # 存储日志
        self.logs.append(log)
        
        # 按操作人索引
        if operator_id not in self.logs_by_operator:
            self.logs_by_operator[operator_id] = []
        self.logs_by_operator[operator_id].append(log)
        
        # 按操作类型索引
        if operation_type not in self.logs_by_type:
            self.logs_by_type[operation_type] = []
        self.logs_by_type[operation_type].append(log)
        
        logger.info(f"Audit log: {operation_type} by {operator_id} - {result}")
        return log
    
    def verify_log_integrity(self) -> bool:
        """验证日志完整性（检查校验和链）"""
        previous_checksum = "0" * 64
        
        for log in self.logs:
            # 验证日志中的前一个校验和是否正确
            if log.previous_checksum != previous_checksum:
                logger.error(f"Integrity check failed at log {log.id}: previous_checksum mismatch")
                return False
            
            # 重新计算当前校验和
            data = f"{log.id}{log.operation_type}{log.operator_id}{log.operation_detail}{log.timestamp}{log.result}"
            expected_checksum = hashlib.sha256(f"{previous_checksum}{data}".encode()).hexdigest()
            
            if log.checksum != expected_checksum:
                logger.error(f"Integrity check failed at log {log.id}: checksum mismatch")
                return False
            
            previous_checksum = log.checksum
        
        logger.info("All audit logs passed integrity check")
        return True
    
    def query_logs(
        self,
        operator_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        result: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> AuditQueryResult:
        """查询审计日志"""
        filtered = self.logs.copy()
        
        # 过滤条件
        if operator_id:
            filtered = [log for log in filtered if log.operator_id == operator_id]
        
        if operation_type:
            filtered = [log for log in filtered if log.operation_type == operation_type]
        
        if target_type:
            filtered = [log for log in filtered if log.target_type == target_type]
        
        if target_id:
            filtered = [log for log in filtered if log.target_id == target_id]
        
        if start_time:
            filtered = [log for log in filtered if log.timestamp >= start_time]
        
        if end_time:
            filtered = [log for log in filtered if log.timestamp <= end_time]
        
        if result:
            filtered = [log for log in filtered if log.result == result]
        
        # 按时间降序排序
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 分页
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = filtered[start:end]
        
        return AuditQueryResult(
            logs=paginated,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def get_log_by_id(self, log_id: str) -> Optional[AuditLog]:
        """根据ID获取日志"""
        for log in self.logs:
            if log.id == log_id:
                return log
        return None
    
    def get_operator_logs(self, operator_id: str) -> List[AuditLog]:
        """获取指定用户的所有操作日志"""
        return self.logs_by_operator.get(operator_id, [])
    
    def get_logs_by_type(self, operation_type: str) -> List[AuditLog]:
        """获取指定类型的操作日志"""
        return self.logs_by_type.get(operation_type, [])
    
    def export_logs(self, file_path: str) -> bool:
        """导出日志到文件"""
        try:
            import json
            logs_data = [log.dict() for log in self.logs]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(logs_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Exported {len(self.logs)} audit logs to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export audit logs: {str(e)}")
            return False
    
    # ==================== 便捷方法 ====================
    
    def log_login(self, user_id: str, result: str = "success", ip_address: Optional[str] = None, 
                  user_agent: Optional[str] = None, error_message: Optional[str] = None):
        """记录登录操作"""
        self.log_operation(
            operation_type='login',
            operator_id=user_id,
            operation_detail=f"User login attempt",
            result=result,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_logout(self, user_id: str):
        """记录登出操作"""
        self.log_operation(
            operation_type='logout',
            operator_id=user_id,
            operation_detail=f"User logout"
        )
    
    def log_skill_create(self, operator_id: str, skill_id: str, skill_name: str):
        """记录技能创建"""
        self.log_operation(
            operation_type='skill_create',
            operator_id=operator_id,
            operation_detail=f"Created skill: {skill_name}",
            target_type='skill',
            target_id=skill_id,
            target_name=skill_name
        )
    
    def log_skill_edit(self, operator_id: str, skill_id: str, skill_name: str, changes: str):
        """记录技能编辑"""
        self.log_operation(
            operation_type='skill_edit',
            operator_id=operator_id,
            operation_detail=f"Edited skill {skill_name}: {changes}",
            target_type='skill',
            target_id=skill_id,
            target_name=skill_name
        )
    
    def log_skill_delete(self, operator_id: str, skill_id: str, skill_name: str):
        """记录技能删除"""
        self.log_operation(
            operation_type='skill_delete',
            operator_id=operator_id,
            operation_detail=f"Deleted skill: {skill_name}",
            target_type='skill',
            target_id=skill_id,
            target_name=skill_name
        )
    
    def log_skill_execute(self, operator_id: str, skill_id: str, skill_name: str, result: str = "success"):
        """记录技能执行"""
        self.log_operation(
            operation_type='skill_execute',
            operator_id=operator_id,
            operation_detail=f"Executed skill: {skill_name}",
            result=result,
            target_type='skill',
            target_id=skill_id,
            target_name=skill_name
        )
    
    def log_tool_execute(self, operator_id: str, tool_id: str, tool_name: str, result: str = "success"):
        """记录工具执行"""
        self.log_operation(
            operation_type='tool_execute',
            operator_id=operator_id,
            operation_detail=f"Executed tool: {tool_name}",
            result=result,
            target_type='tool',
            target_id=tool_id,
            target_name=tool_name
        )
    
    def log_tool_configure(self, operator_id: str, tool_id: str, tool_name: str, changes: str):
        """记录工具配置"""
        self.log_operation(
            operation_type='tool_configure',
            operator_id=operator_id,
            operation_detail=f"Configured tool {tool_name}: {changes}",
            target_type='tool',
            target_id=tool_id,
            target_name=tool_name
        )
    
    def log_feedback_submit(self, operator_id: str, detail: str):
        """记录反馈提交"""
        self.log_operation(
            operation_type='feedback_submit',
            operator_id=operator_id,
            operation_detail=f"Submitted feedback: {detail[:100]}..."
        )
    
    def log_config_modify(self, operator_id: str, config_key: str, old_value: str, new_value: str):
        """记录配置修改"""
        self.log_operation(
            operation_type='config_modify',
            operator_id=operator_id,
            operation_detail=f"Modified config {config_key}: {old_value} -> {new_value}",
            target_type='config',
            target_id=config_key,
            target_name=config_key
        )
    
    def log_permission_grant(self, operator_id: str, resource_type: str, resource_id: str, 
                            user_id: str, permission: str):
        """记录权限授予"""
        self.log_operation(
            operation_type='permission_grant',
            operator_id=operator_id,
            operation_detail=f"Granted {permission} permission for {resource_type} {resource_id} to user {user_id}",
            target_type=resource_type,
            target_id=resource_id
        )
    
    def log_permission_revoke(self, operator_id: str, resource_type: str, resource_id: str,
                             user_id: str, permission: str):
        """记录权限撤销"""
        self.log_operation(
            operation_type='permission_revoke',
            operator_id=operator_id,
            operation_detail=f"Revoked {permission} permission for {resource_type} {resource_id} from user {user_id}",
            target_type=resource_type,
            target_id=resource_id
        )
    
    def log_role_change(self, operator_id: str, user_id: str, old_role: str, new_role: str):
        """记录角色变更"""
        self.log_operation(
            operation_type='role_change',
            operator_id=operator_id,
            operation_detail=f"Changed role for user {user_id}: {old_role} -> {new_role}",
            target_type='user',
            target_id=user_id,
            target_name=user_id
        )


# 全局实例
audit_log_service = AuditLogService()
