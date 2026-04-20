"""细粒度权限管理服务"""
from typing import List, Dict, Any, Optional
from src.types import (
    UserRole, PermissionScope, SkillPermission, ToolPermission, 
    MemoryPermission, ApiPermission, PermissionCheckResult
)
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("services")

# 角色权限映射
ROLE_PERMISSIONS = {
    'admin': {
        'skill': ['read', 'execute', 'edit', 'delete', 'grant'],
        'tool': ['execute', 'configure'],
        'memory': ['read', 'write', 'delete', 'search'],
        'api': ['access'],
        'config': ['view', 'modify']
    },
    'developer': {
        'skill': ['read', 'execute', 'edit', 'delete', 'grant'],
        'tool': ['execute', 'configure'],
        'memory': ['read', 'write', 'search'],
        'api': ['access'],
        'config': ['view']
    },
    'user': {
        'skill': ['read', 'execute'],
        'tool': ['execute'],
        'memory': ['read', 'search'],
        'api': ['access'],
        'config': ['view']
    },
    'guest': {
        'skill': ['read'],
        'tool': [],
        'memory': [],
        'api': [],
        'config': []
    }
}

# 危险工具列表（需要特殊权限）
HAZARDOUS_TOOLS = ['file_delete', 'system_command', 'network_scan', 'data_export']


class FineGrainedPermissionService:
    """细粒度权限管理服务"""
    
    def __init__(self):
        self.user_roles: Dict[str, UserRole] = {}  # user_id -> UserRole
        self.skill_permissions: Dict[str, List[SkillPermission]] = {}  # skill_id -> permissions
        self.tool_permissions: Dict[str, List[ToolPermission]] = {}  # tool_id -> permissions
        self.memory_permissions: Dict[str, List[MemoryPermission]] = {}  # memory_type -> permissions
        self.api_permissions: Dict[str, List[ApiPermission]] = {}  # endpoint -> permissions
        
        # 初始化默认管理员
        self._initialize_default_admin()
    
    def _initialize_default_admin(self):
        """初始化默认管理员"""
        self.user_roles["admin"] = UserRole(
            user_id="admin",
            role="admin",
            department="admin",
            created_at=get_timestamp()
        )
        logger.info("Initialized default admin user")
    
    def set_user_role(self, admin_id: str, user_id: str, role: str, department: Optional[str] = None) -> bool:
        """设置用户角色（需要管理员权限）"""
        if not self._is_admin(admin_id):
            logger.error(f"User {admin_id} is not an admin")
            return False
        
        if role not in ROLE_PERMISSIONS:
            logger.error(f"Invalid role: {role}")
            return False
        
        self.user_roles[user_id] = UserRole(
            user_id=user_id,
            role=role,
            department=department,
            created_at=get_timestamp()
        )
        logger.info(f"Set role '{role}' for user {user_id} in department {department}")
        return True
    
    def get_user_role(self, user_id: str) -> Optional[UserRole]:
        """获取用户角色信息"""
        return self.user_roles.get(user_id)
    
    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        role = self.user_roles.get(user_id)
        return role is not None and role.role == 'admin'
    
    def _is_developer(self, user_id: str) -> bool:
        """检查用户是否是开发人员"""
        role = self.user_roles.get(user_id)
        return role is not None and role.role == 'developer'
    
    # ==================== 技能权限 ====================
    
    def grant_skill_permission(self, grantor_id: str, skill_id: str, user_id: str, 
                              permission: str, scope: Optional[PermissionScope] = None) -> bool:
        """授予技能权限"""
        if not self._check_grant_permission(grantor_id, 'skill'):
            logger.error(f"User {grantor_id} cannot grant skill permissions")
            return False
        
        perm = SkillPermission(
            id=generate_id(),
            skill_id=skill_id,
            user_id=user_id,
            permission=permission,
            granted_by=grantor_id,
            granted_at=get_timestamp(),
            scope=scope
        )
        
        if skill_id not in self.skill_permissions:
            self.skill_permissions[skill_id] = []
        self.skill_permissions[skill_id].append(perm)
        
        logger.info(f"Granted {permission} permission for skill {skill_id} to user {user_id}")
        return True
    
    def check_skill_permission(self, user_id: str, skill_id: str, permission: str) -> PermissionCheckResult:
        """检查技能权限"""
        # 检查角色权限
        role = self.user_roles.get(user_id)
        if not role:
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[permission],
                resource_type='skill',
                resource_id=skill_id
            )
        
        # 管理员拥有所有权限
        if role.role == 'admin':
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查角色默认权限
        role_perms = ROLE_PERMISSIONS.get(role.role, {}).get('skill', [])
        if permission in role_perms:
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查直接授权
        permissions = self.skill_permissions.get(skill_id, [])
        for perm in permissions:
            if perm.user_id == user_id and perm.permission == permission:
                return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=[permission],
            resource_type='skill',
            resource_id=skill_id
        )
    
    # ==================== 工具权限 ====================
    
    def grant_tool_permission(self, grantor_id: str, tool_id: str, user_id: str, 
                             permission: str, is_hazardous: bool = False) -> bool:
        """授予工具权限"""
        if not self._check_grant_permission(grantor_id, 'tool'):
            logger.error(f"User {grantor_id} cannot grant tool permissions")
            return False
        
        # 危险工具需要管理员授权
        if is_hazardous or tool_id in HAZARDOUS_TOOLS:
            if not self._is_admin(grantor_id):
                logger.error(f"Only admin can grant access to hazardous tool {tool_id}")
                return False
        
        perm = ToolPermission(
            id=generate_id(),
            tool_id=tool_id,
            user_id=user_id,
            permission=permission,
            granted_by=grantor_id,
            granted_at=get_timestamp(),
            is_hazardous=is_hazardous or tool_id in HAZARDOUS_TOOLS
        )
        
        if tool_id not in self.tool_permissions:
            self.tool_permissions[tool_id] = []
        self.tool_permissions[tool_id].append(perm)
        
        logger.info(f"Granted {permission} permission for tool {tool_id} to user {user_id}")
        return True
    
    def check_tool_permission(self, user_id: str, tool_id: str, permission: str) -> PermissionCheckResult:
        """检查工具权限"""
        role = self.user_roles.get(user_id)
        if not role:
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[permission],
                resource_type='tool',
                resource_id=tool_id
            )
        
        # 管理员拥有所有权限
        if role.role == 'admin':
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 危险工具需要特殊授权
        is_hazardous = tool_id in HAZARDOUS_TOOLS
        if is_hazardous:
            permissions = self.tool_permissions.get(tool_id, [])
            for perm in permissions:
                if perm.user_id == user_id and perm.permission == permission:
                    return PermissionCheckResult(allowed=True, missing_permissions=[])
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[permission],
                resource_type='tool',
                resource_id=tool_id
            )
        
        # 普通工具检查角色权限
        role_perms = ROLE_PERMISSIONS.get(role.role, {}).get('tool', [])
        if permission in role_perms:
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查直接授权
        permissions = self.tool_permissions.get(tool_id, [])
        for perm in permissions:
            if perm.user_id == user_id and perm.permission == permission:
                return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=[permission],
            resource_type='tool',
            resource_id=tool_id
        )
    
    # ==================== 记忆权限 ====================
    
    def grant_memory_permission(self, grantor_id: str, memory_type: str, user_id: str,
                               permission: str, scope: Optional[PermissionScope] = None) -> bool:
        """授予记忆权限"""
        if not self._check_grant_permission(grantor_id, 'memory'):
            logger.error(f"User {grantor_id} cannot grant memory permissions")
            return False
        
        perm = MemoryPermission(
            id=generate_id(),
            memory_type=memory_type,
            user_id=user_id,
            permission=permission,
            granted_by=grantor_id,
            granted_at=get_timestamp(),
            scope=scope
        )
        
        key = f"memory_{memory_type}"
        if key not in self.memory_permissions:
            self.memory_permissions[key] = []
        self.memory_permissions[key].append(perm)
        
        logger.info(f"Granted {permission} permission for {memory_type} memory to user {user_id}")
        return True
    
    def check_memory_permission(self, user_id: str, memory_type: str, permission: str) -> PermissionCheckResult:
        """检查记忆权限"""
        role = self.user_roles.get(user_id)
        if not role:
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[permission],
                resource_type='memory',
                resource_id=memory_type
            )
        
        # 管理员拥有所有权限
        if role.role == 'admin':
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查角色权限
        role_perms = ROLE_PERMISSIONS.get(role.role, {}).get('memory', [])
        if permission in role_perms:
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查直接授权
        key = f"memory_{memory_type}"
        permissions = self.memory_permissions.get(key, [])
        for perm in permissions:
            if perm.user_id == user_id and perm.permission == permission:
                return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=[permission],
            resource_type='memory',
            resource_id=memory_type
        )
    
    # ==================== API权限 ====================
    
    def grant_api_permission(self, grantor_id: str, endpoint: str, user_id: str) -> bool:
        """授予API权限"""
        if not self._is_admin(grantor_id):
            logger.error(f"Only admin can grant API permissions")
            return False
        
        perm = ApiPermission(
            id=generate_id(),
            endpoint=endpoint,
            user_id=user_id,
            permission='access',
            granted_by=grantor_id,
            granted_at=get_timestamp()
        )
        
        if endpoint not in self.api_permissions:
            self.api_permissions[endpoint] = []
        self.api_permissions[endpoint].append(perm)
        
        logger.info(f"Granted access to API endpoint {endpoint} for user {user_id}")
        return True
    
    def check_api_permission(self, user_id: str, endpoint: str) -> PermissionCheckResult:
        """检查API权限"""
        role = self.user_roles.get(user_id)
        if not role:
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=['access'],
                resource_type='api',
                resource_id=endpoint
            )
        
        # 管理员和开发人员拥有所有API权限
        if role.role in ['admin', 'developer']:
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查直接授权
        permissions = self.api_permissions.get(endpoint, [])
        for perm in permissions:
            if perm.user_id == user_id:
                return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=['access'],
            resource_type='api',
            resource_id=endpoint
        )
    
    def _check_grant_permission(self, user_id: str, resource_type: str) -> bool:
        """检查是否有授权权限"""
        role = self.user_roles.get(user_id)
        if not role:
            return False
        
        if role.role == 'admin':
            return True
        
        if role.role == 'developer' and resource_type in ['skill', 'tool']:
            return True
        
        return False
    
    # ==================== 部门权限 ====================
    
    def grant_department_permission(self, grantor_id: str, resource_type: str, resource_id: str,
                                   department: str, permissions: List[str]) -> bool:
        """为部门授予权限"""
        if not self._is_admin(grantor_id):
            logger.error(f"Only admin can grant department permissions")
            return False
        
        scope = PermissionScope(type='department', value=department)
        
        for user_id, user_role in self.user_roles.items():
            if user_role.department == department:
                if resource_type == 'skill':
                    for perm in permissions:
                        self.grant_skill_permission(grantor_id, resource_id, user_id, perm, scope)
                elif resource_type == 'tool':
                    for perm in permissions:
                        self.grant_tool_permission(grantor_id, resource_id, user_id, perm)
                elif resource_type == 'memory':
                    for perm in permissions:
                        self.grant_memory_permission(grantor_id, resource_id, user_id, perm, scope)
        
        logger.info(f"Granted permissions {permissions} for {resource_type} {resource_id} to department {department}")
        return True
    
    # ==================== 批量操作 ====================
    
    def revoke_all_permissions(self, revoker_id: str, user_id: str) -> bool:
        """撤销用户所有权限"""
        if not self._is_admin(revoker_id):
            logger.error(f"Only admin can revoke all permissions")
            return False
        
        # 撤销技能权限
        for skill_id, perms in self.skill_permissions.items():
            self.skill_permissions[skill_id] = [p for p in perms if p.user_id != user_id]
        
        # 撤销工具权限
        for tool_id, perms in self.tool_permissions.items():
            self.tool_permissions[tool_id] = [p for p in perms if p.user_id != user_id]
        
        # 撤销记忆权限
        for key, perms in self.memory_permissions.items():
            self.memory_permissions[key] = [p for p in perms if p.user_id != user_id]
        
        # 撤销API权限
        for endpoint, perms in self.api_permissions.items():
            self.api_permissions[endpoint] = [p for p in perms if p.user_id != user_id]
        
        logger.info(f"Revoked all permissions for user {user_id}")
        return True
    
    # ==================== 查询 ====================
    
    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有权限"""
        permissions = {
            'skill': [],
            'tool': [],
            'memory': [],
            'api': []
        }
        
        # 技能权限
        for skill_id, perms in self.skill_permissions.items():
            for perm in perms:
                if perm.user_id == user_id:
                    permissions['skill'].append({
                        'resource_id': skill_id,
                        'permission': perm.permission
                    })
        
        # 工具权限
        for tool_id, perms in self.tool_permissions.items():
            for perm in perms:
                if perm.user_id == user_id:
                    permissions['tool'].append({
                        'resource_id': tool_id,
                        'permission': perm.permission,
                        'is_hazardous': perm.is_hazardous
                    })
        
        # 记忆权限
        for key, perms in self.memory_permissions.items():
            for perm in perms:
                if perm.user_id == user_id:
                    permissions['memory'].append({
                        'resource_id': key.replace('memory_', ''),
                        'permission': perm.permission
                    })
        
        # API权限
        for endpoint, perms in self.api_permissions.items():
            for perm in perms:
                if perm.user_id == user_id:
                    permissions['api'].append({
                        'resource_id': endpoint,
                        'permission': perm.permission
                    })
        
        return permissions


# 全局实例
permission_service = FineGrainedPermissionService()
