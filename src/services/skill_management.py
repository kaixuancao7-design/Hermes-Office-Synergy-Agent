"""技能版本管理和权限控制服务"""
from typing import List, Dict, Any, Optional
from src.types import (
    Skill, SkillVersion, SkillChangeLog, UserRole, 
    SkillPermission, PermissionCheckResult, SkillStep
)
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("services")


class SkillVersionManager:
    """技能版本管理"""
    
    def __init__(self):
        self.skill_versions: Dict[str, List[SkillVersion]] = {}  # skill_id -> versions
        self.change_logs: Dict[str, List[SkillChangeLog]] = {}   # skill_id -> logs
    
    def save_version(self, skill: Skill, change_type: str = "update", change_note: str = "") -> SkillVersion:
        """保存技能版本"""
        version = SkillVersion(
            id=generate_id(),
            skill_id=skill.id,
            version=skill.version,
            name=skill.name,
            description=skill.description,
            type=skill.type,
            trigger_patterns=skill.trigger_patterns.copy(),
            steps=[SkillStep(**s.dict()) for s in skill.steps],
            metadata=skill.metadata.copy(),
            created_by=skill.created_by,
            created_at=get_timestamp(),
            change_type=change_type,
            change_note=change_note
        )
        
        if skill.id not in self.skill_versions:
            self.skill_versions[skill.id] = []
        self.skill_versions[skill.id].append(version)
        
        # 记录修改日志
        self._log_change(skill.id, skill.version, change_type, change_note, skill.created_by)
        
        logger.info(f"Saved skill version: {skill.name} v{skill.version}")
        return version
    
    def _log_change(self, skill_id: str, version: str, change_type: str, description: str, changed_by: str):
        """记录修改日志"""
        log = SkillChangeLog(
            id=generate_id(),
            skill_id=skill_id,
            version=version,
            changed_by=changed_by or "system",
            changed_at=get_timestamp(),
            change_type=change_type,
            change_description=description
        )
        
        if skill_id not in self.change_logs:
            self.change_logs[skill_id] = []
        self.change_logs[skill_id].append(log)
    
    def get_versions(self, skill_id: str) -> List[SkillVersion]:
        """获取技能的所有版本"""
        return self.skill_versions.get(skill_id, [])
    
    def get_version(self, skill_id: str, version: str) -> Optional[SkillVersion]:
        """获取指定版本的技能"""
        versions = self.skill_versions.get(skill_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None
    
    def rollback(self, skill_id: str, target_version: str, user_id: str) -> Optional[Skill]:
        """回滚到指定版本"""
        version = self.get_version(skill_id, target_version)
        if not version:
            logger.error(f"Version {target_version} not found for skill {skill_id}")
            return None
        
        # 获取当前版本
        current_versions = self.skill_versions.get(skill_id, [])
        if current_versions:
            current_version = current_versions[-1]
        else:
            current_version = None
        
        # 创建回滚后的技能
        rolled_back_skill = Skill(
            id=skill_id,
            name=version.name,
            description=version.description,
            type=version.type,
            trigger_patterns=version.trigger_patterns.copy(),
            steps=[SkillStep(**s.dict()) for s in version.steps],
            metadata=version.metadata.copy(),
            version=self._increment_version(target_version),
            created_at=version.created_at,
            updated_at=get_timestamp(),
            created_by=version.created_by
        )
        
        # 保存新版本（回滚）
        self.save_version(rolled_back_skill, "rollback", f"Rolled back from {current_version.version if current_version else 'unknown'} to {target_version}")
        
        logger.info(f"Skill {skill_id} rolled back to version {target_version} by user {user_id}")
        return rolled_back_skill
    
    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            return f"{major}.{minor}.{patch}"
        return f"{current_version}.1"
    
    def get_change_logs(self, skill_id: str) -> List[SkillChangeLog]:
        """获取技能的修改日志"""
        return self.change_logs.get(skill_id, [])
    
    def get_latest_version(self, skill_id: str) -> Optional[SkillVersion]:
        """获取最新版本"""
        versions = self.skill_versions.get(skill_id, [])
        return versions[-1] if versions else None


class SkillPermissionManager:
    """技能权限管理"""
    
    def __init__(self):
        self.user_roles: Dict[str, UserRole] = {}  # user_id -> role
        self.skill_permissions: Dict[str, List[SkillPermission]] = {}  # skill_id -> permissions
        
        # 默认管理员角色（系统初始化）
        self._initialize_default_roles()
    
    def _initialize_default_roles(self):
        """初始化默认角色"""
        # 创建默认管理员
        self.user_roles["admin"] = UserRole(
            user_id="admin",
            role="admin",
            created_at=get_timestamp()
        )
    
    def set_user_role(self, user_id: str, role: str) -> bool:
        """设置用户角色"""
        if role not in ['admin', 'user', 'guest']:
            logger.error(f"Invalid role: {role}")
            return False
        
        self.user_roles[user_id] = UserRole(
            user_id=user_id,
            role=role,
            created_at=get_timestamp()
        )
        logger.info(f"Set role '{role}' for user {user_id}")
        return True
    
    def get_user_role(self, user_id: str) -> Optional[str]:
        """获取用户角色"""
        role = self.user_roles.get(user_id)
        return role.role if role else None
    
    def grant_permission(self, skill_id: str, user_id: str, permission: str, granted_by: str) -> bool:
        """授予用户技能权限"""
        if permission not in ['read', 'execute', 'edit', 'delete', 'grant']:
            logger.error(f"Invalid permission: {permission}")
            return False
        
        # 检查授权者是否有授权权限
        if not self._check_permission(granted_by, skill_id, 'grant'):
            logger.error(f"User {granted_by} does not have grant permission for skill {skill_id}")
            return False
        
        perm = SkillPermission(
            id=generate_id(),
            skill_id=skill_id,
            user_id=user_id,
            permission=permission,
            granted_by=granted_by,
            granted_at=get_timestamp()
        )
        
        if skill_id not in self.skill_permissions:
            self.skill_permissions[skill_id] = []
        
        # 检查是否已存在相同权限
        existing = [p for p in self.skill_permissions[skill_id] 
                    if p.user_id == user_id and p.permission == permission]
        if not existing:
            self.skill_permissions[skill_id].append(perm)
            logger.info(f"Granted {permission} permission for skill {skill_id} to user {user_id}")
        
        return True
    
    def revoke_permission(self, skill_id: str, user_id: str, permission: str, revoked_by: str) -> bool:
        """撤销用户技能权限"""
        # 检查撤销者是否有授权权限
        if not self._check_permission(revoked_by, skill_id, 'grant'):
            logger.error(f"User {revoked_by} does not have grant permission for skill {skill_id}")
            return False
        
        permissions = self.skill_permissions.get(skill_id, [])
        self.skill_permissions[skill_id] = [
            p for p in permissions 
            if not (p.user_id == user_id and p.permission == permission)
        ]
        
        logger.info(f"Revoked {permission} permission for skill {skill_id} from user {user_id}")
        return True
    
    def check_permission(self, user_id: str, skill_id: str, required_permission: str) -> PermissionCheckResult:
        """检查用户是否有指定权限"""
        # 管理员拥有所有权限
        role = self.get_user_role(user_id)
        if role == 'admin':
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        # 检查直接授权
        permissions = self.skill_permissions.get(skill_id, [])
        user_permissions = [p.permission for p in permissions if p.user_id == user_id]
        
        if required_permission in user_permissions:
            return PermissionCheckResult(allowed=True, missing_permissions=[])
        
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=[required_permission]
        )
    
    def _check_permission(self, user_id: str, skill_id: str, required_permission: str) -> bool:
        """内部权限检查"""
        result = self.check_permission(user_id, skill_id, required_permission)
        return result.allowed
    
    def get_user_permissions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有权限"""
        permissions = []
        
        for skill_id, perms in self.skill_permissions.items():
            for perm in perms:
                if perm.user_id == user_id:
                    permissions.append({
                        "skill_id": skill_id,
                        "permission": perm.permission,
                        "granted_at": perm.granted_at
                    })
        
        return permissions
    
    def get_skill_permissions(self, skill_id: str) -> List[SkillPermission]:
        """获取技能的所有权限"""
        return self.skill_permissions.get(skill_id, [])
    
    def has_any_permission(self, user_id: str, skill_id: str) -> bool:
        """检查用户是否对技能有任何权限"""
        permissions = self.skill_permissions.get(skill_id, [])
        return any(p.user_id == user_id for p in permissions)


# 全局实例
skill_version_manager = SkillVersionManager()
skill_permission_manager = SkillPermissionManager()
