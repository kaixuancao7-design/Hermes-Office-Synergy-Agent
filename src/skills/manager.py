"""技能管理器主类 - 提供技能的核心CRUD操作和权限管理"""

from typing import List, Dict, Any, Optional
from src.types import Skill, SkillVersion, SkillChangeLog, PermissionCheckResult
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.engine.memory_manager import memory_manager
from src.services.skill_management import skill_version_manager
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service
from .preset_skills import preset_skills_manager
from .custom_skills import custom_skills_manager
from .learned_skills import learned_skills_manager
from .triggers import trigger_matcher
from .validators import skill_validator

logger = get_logger("skill")


class SkillManager:
    """技能管理器 - 统一管理所有类型的技能"""

    def __init__(self):
        self._internal_skills_loaded = False
        self._external_skills_registered = False

    def _ensure_internal_skills(self):
        """确保内部预设技能已加载（延迟初始化）"""
        if self._internal_skills_loaded:
            return
        
        skills = db.get_all_skills()
        if not skills:
            preset_skills_manager.initialize_preset_skills()
        
        self._internal_skills_loaded = True
        logger.info("✅ 内部技能初始化完成")

    def register_external_skills(self):
        """
        注册外部适配器技能（延迟注册，避免循环依赖）
        
        此方法由外部按需调用，不在 __init__ 中自动执行，
        以避免初始化时的循环依赖风险。
        """
        if self._external_skills_registered:
            logger.info("⚠️ 外部技能已注册，跳过重复注册")
            return
        
        # 确保内部技能已加载
        self._ensure_internal_skills()
        
        # 尝试注册 anthropics 技能（如果可用）
        self._try_register_anthropics_skills()
        
        # 尝试注册 presentation-skill（如果可用）
        self._try_register_presentation_skill()
        
        self._external_skills_registered = True
        logger.info("✅ 外部技能注册完成")

    def _try_register_anthropics_skills(self):
        """尝试注册 anthropics/skills（如果安装了该模块）"""
        try:
            # 延迟导入以避免循环依赖
            from src.skills.adapters.anthropics_adapter import anthropics_adapter
            
            if anthropics_adapter.is_available():
                anthropics_adapter.register_skill(self, skill_type="pptx")
                logger.info("✅ Anthropics 技能注册成功")
            else:
                logger.info("⚠️ anthropics_skills 未安装，跳过注册")
                
        except ImportError:
            logger.info("⚠️ anthropics_adapter 模块未找到，跳过注册")
        except Exception as e:
            logger.error(f"❌ 注册 anthropics 技能失败: {str(e)}")

    def _try_register_presentation_skill(self):
        """尝试注册 presentation-skill（如果安装了该模块）"""
        try:
            # 延迟导入以避免循环依赖
            from src.skills.adapters.presentation_skill_adapter import presentation_skill_adapter
            
            if presentation_skill_adapter.is_available():
                presentation_skill_adapter.register_skill(self)
                logger.info("✅ presentation-skill 注册成功")
            else:
                logger.info("⚠️ presentation-skill 未安装，跳过注册")
                
        except ImportError:
            logger.info("⚠️ presentation_skill_adapter 模块未找到，跳过注册")
        except Exception as e:
            logger.error(f"❌ 注册 presentation-skill 失败: {str(e)}")

    # ==================== 基础CRUD ====================

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取单个技能"""
        self._ensure_internal_skills()
        return db.get_skill(skill_id)

    def get_all_skills(self, user_id: Optional[str] = None) -> List[Skill]:
        """获取用户有权限访问的所有技能"""
        self._ensure_internal_skills()
        all_skills = db.get_all_skills()

        if not user_id:
            return all_skills

        # 获取用户角色
        user_role = permission_service.get_user_role(user_id)

        # 管理员可以访问所有技能
        if user_role and user_role.role == "admin":
            return all_skills

        # 普通用户只能访问自己创建的或被授权的技能
        result = []
        for skill in all_skills:
            # 检查是否是自己创建的
            if skill.created_by == user_id:
                result.append(skill)
                continue

            # 检查是否有读取权限
            perm_result = permission_service.check_skill_permission(user_id, skill.id, 'read')
            if perm_result.allowed:
                result.append(skill)

        return result

    def save_skill(self, skill: Skill) -> None:
        """保存技能到数据库"""
        self._ensure_internal_skills()
        db.save_skill(skill)

    def delete_skill(self, user_id: str, skill_id: str) -> bool:
        """删除技能（需要检查权限）"""
        self._ensure_internal_skills()
        skill = db.get_skill(skill_id)
        if not skill:
            return False

        # 检查权限
        permission = permission_service.check_skill_permission(user_id, skill_id, "delete")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to delete skill {skill_id}")
            raise PermissionError("没有删除技能的权限")

        # 记录删除日志
        skill_version_manager._log_change(skill_id, skill.version, "delete", "技能已删除", user_id)

        # 记录审计日志
        audit_log_service.log_skill_delete(user_id, skill_id, skill.name)

        db.delete_skill(skill_id)
        logger.info(f"Deleted skill: {skill_id} by user {user_id}")
        return True

    # ==================== 分类技能管理 ====================

    def create_preset_skill(self, **kwargs) -> Skill:
        """创建预设技能"""
        return preset_skills_manager.create_preset_skill(**kwargs)

    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]]) -> Skill:
        """创建自定义技能"""
        return custom_skills_manager.create_custom_skill(user_id, name, description, steps)

    def create_learned_skill(self, user_id: str, draft_id: str) -> Optional[Skill]:
        """从草稿创建学习生成的技能"""
        return learned_skills_manager.create_from_draft(user_id, draft_id)

    # ==================== 触发匹配 ====================

    def find_relevant_skill(self, query: str, user_id: Optional[str] = None) -> Optional[Skill]:
        """查找用户有权限访问的相关技能"""
        return trigger_matcher.find_relevant_skill(query, user_id)

    def apply_user_preferences(self, skill: Skill, user_id: str) -> Skill:
        """应用用户偏好设置"""
        profile = memory_manager.get_user_profile(user_id)

        if profile and profile.writing_style:
            for step in skill.steps:
                if "instruction" in step.parameters:
                    step.parameters["instruction"] += f" (风格: {profile.writing_style})"

        return skill

    # ==================== 版本管理 ====================

    def get_skill_versions(self, skill_id: str) -> List[SkillVersion]:
        """获取技能的所有版本"""
        return skill_version_manager.get_versions(skill_id)

    def get_skill_version(self, skill_id: str, version: str) -> Optional[SkillVersion]:
        """获取指定版本的技能"""
        return skill_version_manager.get_version(skill_id, version)

    def rollback_to_version(self, user_id: str, skill_id: str, target_version: str) -> Optional[Skill]:
        """回滚到指定版本（需要检查权限）"""
        # 检查权限
        permission = permission_service.check_skill_permission(user_id, skill_id, "edit")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to rollback skill {skill_id}")
            raise PermissionError("没有回滚技能的权限")

        rolled_back = skill_version_manager.rollback(skill_id, target_version, user_id)
        if rolled_back:
            db.save_skill(rolled_back)

            # 记录审计日志
            audit_log_service.log_skill_edit(user_id, skill_id, rolled_back.name, f"Rolled back to version {target_version}")

            logger.info(f"Skill {skill_id} rolled back to version {target_version} by user {user_id}")

        return rolled_back

    def get_skill_change_logs(self, skill_id: str) -> List[SkillChangeLog]:
        """获取技能的修改日志"""
        return skill_version_manager.get_change_logs(skill_id)

    # ==================== 权限管理 ====================

    def set_user_role(self, admin_id: str, user_id: str, role: str, department: Optional[str] = None) -> bool:
        """设置用户角色（需要管理员权限）"""
        success = permission_service.set_user_role(admin_id, user_id, role, department)

        if success:
            # 记录审计日志
            old_role = permission_service.get_user_role(user_id)
            audit_log_service.log_role_change(admin_id, user_id, old_role.role if old_role else "guest", role)

        return success

    def grant_permission(self, grantor_id: str, skill_id: str, user_id: str, permission: str) -> bool:
        """授予用户技能权限"""
        success = permission_service.grant_skill_permission(grantor_id, skill_id, user_id, permission)

        if success:
            # 记录审计日志
            audit_log_service.log_permission_grant(grantor_id, 'skill', skill_id, user_id, permission)

        return success

    def revoke_permission(self, revoker_id: str, skill_id: str, user_id: str, permission: str) -> bool:
        """撤销用户技能权限"""
        success = permission_service.revoke_all_permissions(revoker_id, user_id)

        if success:
            # 记录审计日志
            audit_log_service.log_permission_revoke(revoker_id, 'skill', skill_id, user_id, permission)

        return success

    def check_permission(self, user_id: str, skill_id: str, permission: str) -> PermissionCheckResult:
        """检查用户是否有指定权限"""
        return permission_service.check_skill_permission(user_id, skill_id, permission)

    def can_execute_skill(self, user_id: str, skill_id: str) -> bool:
        """检查用户是否可以执行技能"""
        skill = db.get_skill(skill_id)
        if not skill:
            return False

        # 管理员可以执行所有技能
        user_role = permission_service.get_user_role(user_id)
        if user_role and user_role.role == "admin":
            return True

        # 技能创建者可以执行
        if skill.created_by == user_id:
            return True

        # 检查是否有执行权限
        permission = permission_service.check_skill_permission(user_id, skill_id, "execute")

        # 记录审计日志（仅记录执行权限检查，不记录每次调用）
        if permission.allowed:
            audit_log_service.log_skill_execute(user_id, skill_id, skill.name)

        return permission.allowed

    # ==================== 验证 ====================

    def check_complexity(self, skill: Skill) -> Dict[str, Any]:
        """检查技能复杂度"""
        return skill_validator.check_complexity(skill)

    def validate_skill_changes(self, original_skill: Skill, updated_skill: Skill,
                                user_request: str) -> Dict[str, Any]:
        """验证技能变更"""
        return skill_validator.validate_skill_changes(original_skill, updated_skill, user_request)

    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            return f"{major}.{minor}.{patch}"
        return f"{current_version}.1"


# 全局实例
skill_manager = SkillManager()