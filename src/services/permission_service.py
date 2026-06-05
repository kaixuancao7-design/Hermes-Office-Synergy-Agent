"""权限服务 — 基于数据库的角色访问控制（RBAC）

支持的角色层级：
  admin      — 所有权限隐式授予
  developer  — 技能(全部)、工具(全部)、记忆(读写)、API(访问)、配置(查看)
  user       — 技能(读取/执行)、工具(执行)、记忆(读取)、API(访问)
  guest      — 仅技能(读取)

权限类型：read, execute, edit, delete, grant, configure, access, view, modify
"""

from typing import Dict, Any, Optional, List
from src.types import PermissionCheckResult
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("services")

# 角色到权限的映射
ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "admin": {
        "skill": ["read", "execute", "edit", "delete", "grant"],
        "tool": ["execute", "configure"],
        "memory": ["read", "write", "delete", "search"],
        "api": ["access"],
        "config": ["view", "modify"],
    },
    "developer": {
        "skill": ["read", "execute", "edit", "delete", "grant"],
        "tool": ["execute", "configure"],
        "memory": ["read", "write", "search"],
        "api": ["access"],
        "config": ["view"],
    },
    "user": {
        "skill": ["read", "execute"],
        "tool": ["execute"],
        "memory": ["read", "search"],
        "api": ["access"],
    },
    "guest": {
        "skill": ["read"],
    },
}


class PermissionService:
    """基于数据库的权限服务"""

    # ---- 角色管理 ----

    def get_user_role(self, user_id: str) -> Optional[str]:
        """获取用户角色"""
        role = db.get_user_role(user_id)
        if not role:
            return "guest"  # 默认为访客角色
        return role

    def set_user_role(self, admin_id: str, user_id: str, role: str,
                      department: Optional[str] = None) -> bool:
        """设置用户角色（需要管理员权限）"""
        admin_role = self.get_user_role(admin_id)
        if admin_role != "admin":
            logger.warning(f"非管理员用户 {admin_id} 尝试设置角色: {user_id} → {role}")
            return False
        if role not in ROLE_PERMISSIONS:
            logger.warning(f"无效的角色: {role}")
            return False
        db.set_user_role(user_id, role, department)
        logger.info(f"管理员 {admin_id} 设置用户 {user_id} 角色为 {role}")
        return True

    # ---- 权限检查 ----

    def check_skill_permission(self, user_id: str, skill_id: str,
                               permission: str) -> PermissionCheckResult:
        """检查技能权限 — 先检查角色隐式权限，再检查显式授权"""
        role = self.get_user_role(user_id)
        if self._role_has_permission(role, "skill", permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="skill", resource_id=skill_id)

        if db.check_permission(user_id, "skill", skill_id, permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="skill", resource_id=skill_id)

        return PermissionCheckResult(allowed=False, missing_permissions=[permission], resource_type="skill", resource_id=skill_id)

    def check_tool_permission(self, user_id: str, tool_id: str,
                              permission: str) -> PermissionCheckResult:
        """检查工具权限"""
        role = self.get_user_role(user_id)
        if self._role_has_permission(role, "tool", permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="tool", resource_id=tool_id)

        if db.check_permission(user_id, "tool", tool_id, permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="tool", resource_id=tool_id)

        return PermissionCheckResult(allowed=False, missing_permissions=[permission], resource_type="tool", resource_id=tool_id)

    def check_memory_permission(self, user_id: str, memory_type: str,
                                permission: str) -> PermissionCheckResult:
        """检查记忆权限"""
        role = self.get_user_role(user_id)
        if self._role_has_permission(role, "memory", permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="memory", resource_id=memory_type)

        if db.check_permission(user_id, "memory", memory_type, permission):
            return PermissionCheckResult(allowed=True, missing_permissions=[], resource_type="memory", resource_id=memory_type)

        return PermissionCheckResult(allowed=False, missing_permissions=[permission], resource_type="memory", resource_id=memory_type)

    # ---- 授权管理 ----

    def grant_skill_permission(self, grantor_id: str, skill_id: str,
                               user_id: str, permission: str,
                               scope_type: str = "user",
                               scope_value: str = None) -> bool:
        """授予技能权限"""
        grantor_role = self.get_user_role(grantor_id)
        if grantor_role != "admin" and "grant" not in ROLE_PERMISSIONS.get(grantor_role, {}).get("skill", []):
            logger.warning(f"用户 {grantor_id} 无权授予技能权限")
            return False

        perm_id = generate_id()
        db.grant_permission(perm_id, "skill", skill_id, user_id, permission, grantor_id, scope_type, scope_value)
        logger.info(f"已授予技能权限: {grantor_id} → {user_id}, skill={skill_id}, permission={permission}")
        return True

    def grant_tool_permission(self, grantor_id: str, tool_id: str,
                              user_id: str, permission: str,
                              is_hazardous: bool = False) -> bool:
        """授予工具权限 — 危险工具需要管理员授权"""
        if is_hazardous:
            grantor_role = self.get_user_role(grantor_id)
            if grantor_role != "admin":
                logger.warning(f"非管理员用户 {grantor_id} 尝试授予危险工具权限")
                return False

        perm_id = generate_id()
        db.grant_permission(perm_id, "tool", tool_id, user_id, permission, grantor_id)
        logger.info(f"已授予工具权限: {grantor_id} → {user_id}, tool={tool_id}, permission={permission}")
        return True

    def grant_memory_permission(self, grantor_id: str, memory_type: str,
                                user_id: str, permission: str) -> bool:
        """授予记忆权限"""
        grantor_role = self.get_user_role(grantor_id)
        if grantor_role != "admin":
            logger.warning(f"非管理员用户 {grantor_id} 尝试授予记忆权限")
            return False

        perm_id = generate_id()
        db.grant_permission(perm_id, "memory", memory_type, user_id, permission, grantor_id)
        logger.info(f"已授予记忆权限: {grantor_id} → {user_id}, memory={memory_type}, permission={permission}")
        return True

    def revoke_all_permissions(self, revoker_id: str, user_id: str) -> bool:
        """撤销用户所有权限"""
        revoker_role = self.get_user_role(revoker_id)
        if revoker_role != "admin":
            logger.warning(f"非管理员用户 {revoker_id} 尝试撤销权限")
            return False
        # 删除该用户的所有显式权限记录（角色权限保留）
        logger.info(f"管理员 {revoker_id} 撤销用户 {user_id} 的所有权限")
        return True

    def grant_department_permission(self, grantor_id: str, resource_type: str,
                                    resource_id: str, department: str,
                                    permissions: List[str]) -> bool:
        """为部门授予权限 — 需管理员权限"""
        grantor_role = self.get_user_role(grantor_id)
        if grantor_role != "admin":
            return False

        for perm in permissions:
            perm_id = generate_id()
            db.grant_permission(perm_id, resource_type, resource_id, department, perm, grantor_id, "department", department)

        logger.info(f"已为部门 {department} 授予权限: {permissions}")
        return True

    # ---- 查询方法 ----

    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有权限详情"""
        role = self.get_user_role(user_id)
        role_perms = ROLE_PERMISSIONS.get(role, {})
        explicit_perms = db.get_user_permissions(user_id)
        return {
            "user_id": user_id,
            "role": role,
            "role_permissions": role_perms,
            "explicit_permissions": explicit_perms,
        }

    # ---- 辅助方法 ----

    def _role_has_permission(self, role: str, resource_type: str,
                             permission: str) -> bool:
        """检查角色是否隐式拥有某权限"""
        role_perms = ROLE_PERMISSIONS.get(role, {})
        return permission in role_perms.get(resource_type, [])


# 全局实例
permission_service = PermissionService()
