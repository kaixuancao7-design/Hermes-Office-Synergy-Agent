from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep, UserProfile, SkillVersion, SkillChangeLog, PermissionCheckResult
from src.data.database import db
from src.utils import generate_id, get_timestamp, setup_logging
from src.engine.memory_manager import memory_manager
from src.config import settings
from src.services.skill_management import skill_version_manager
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service

logger = setup_logging(settings.LOG_LEVEL)


class SkillManager:
    # 复杂度阈值（遵循HERMES.md原则）
    COMPLEXITY_THRESHOLDS = {
        'max_steps': 10,
        'max_branches': 3,
        'max_nesting': 2,
        'max_tools': 5
    }
    
    def __init__(self):
        self._load_skills()
    
    def _load_skills(self):
        skills = db.get_all_skills()
        if not skills:
            self._initialize_preset_skills()
    
    def _initialize_preset_skills(self):
        preset_skills = [
            Skill(
                id=generate_id(),
                name="会议纪要生成",
                description="自动生成会议纪要",
                type="preset",
                trigger_patterns=["会议纪要", "meeting minutes", "会议记录"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "提取会议要点"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "整理讨论内容"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成会议纪要文档"}
                    )
                ],
                metadata={},
                version="1.0.0",
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            ),
            Skill(
                id=generate_id(),
                name="数据图表绘制",
                description="根据数据生成图表",
                type="preset",
                trigger_patterns=["图表", "chart", "graph", "可视化"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "分析数据需求"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "选择合适的图表类型"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成图表"}
                    )
                ],
                metadata={},
                version="1.0.0",
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            ),
            Skill(
                id=generate_id(),
                name="竞品分析",
                description="分析竞争对手信息",
                type="preset",
                trigger_patterns=["竞品分析", "competitive analysis", "竞争对手"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "收集竞品信息"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "分析竞品优势劣势"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成分析报告"}
                    )
                ],
                metadata={},
                version="1.0.0",
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            ),
            Skill(
                id=generate_id(),
                name="周报生成",
                description="自动生成工作周报",
                type="preset",
                trigger_patterns=["周报", "weekly report", "工作汇报"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "收集本周工作内容"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "整理工作成果"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成周报文档"}
                    )
                ],
                metadata={},
                version="1.0.0",
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            ),
            Skill(
                id=generate_id(),
                name="PPT大纲生成",
                description="生成PPT大纲",
                type="preset",
                trigger_patterns=["ppt", "演示文稿", "presentation"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "分析演示主题"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "确定内容结构"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成PPT大纲"}
                    )
                ],
                metadata={},
                version="1.0.0",
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            )
        ]
        
        for skill in preset_skills:
            db.save_skill(skill)
            # 保存初始版本
            skill_version_manager.save_version(skill, "create", "初始版本")
        logger.info("Initialized preset skills")
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return db.get_skill(skill_id)
    
    def get_all_skills(self, user_id: Optional[str] = None) -> List[Skill]:
        """获取用户有权限访问的所有技能"""
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
    
    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]]) -> Skill:
        """创建自定义技能（需要检查权限）"""
        # 检查用户是否有权限创建技能
        user_role = permission_service.get_user_role(user_id)
        if not user_role or user_role.role not in ["admin", "developer", "user"]:
            logger.error(f"User {user_id} does not have permission to create skills")
            raise PermissionError("没有创建技能的权限")
        
        skill_steps = [
            SkillStep(
                id=generate_id(),
                action=step.get("action", "execute"),
                parameters=step.get("parameters", {}),
                next_step_id=step.get("next_step_id"),
                condition=step.get("condition")
            ) for step in steps
        ]
        
        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type="custom",
            trigger_patterns=[name],
            steps=skill_steps,
            metadata={"user_id": user_id},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id
        )
        
        db.save_skill(skill)
        # 保存初始版本
        skill_version_manager.save_version(skill, "create", "初始版本")
        
        # 记录审计日志
        audit_log_service.log_skill_create(user_id, skill.id, skill.name)
        
        logger.info(f"Created custom skill: {name} by user {user_id}")
        return skill
    
    def update_skill(self, user_id: str, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        """更新技能（需要检查权限）"""
        skill = db.get_skill(skill_id)
        if not skill:
            return None
        
        # 检查权限
        permission = permission_service.check_skill_permission(user_id, skill_id, "edit")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to edit skill {skill_id}")
            raise PermissionError("没有编辑技能的权限")
        
        # 更新字段
        if "name" in updates:
            skill.name = updates["name"]
        if "description" in updates:
            skill.description = updates["description"]
        if "trigger_patterns" in updates:
            skill.trigger_patterns = updates["trigger_patterns"]
        if "steps" in updates:
            skill.steps = [SkillStep(**s) for s in updates["steps"]]
        if "metadata" in updates:
            skill.metadata.update(updates["metadata"])
        
        # 递增版本号
        skill.version = self._increment_version(skill.version)
        skill.updated_at = get_timestamp()
        
        db.save_skill(skill)
        # 保存新版本
        change_note = updates.get("change_note", "技能更新")
        skill_version_manager.save_version(skill, "update", change_note)
        
        # 记录审计日志
        audit_log_service.log_skill_edit(user_id, skill_id, skill.name, change_note)
        
        logger.info(f"Updated skill: {skill_id} v{skill.version} by user {user_id}")
        return skill
    
    def delete_skill(self, user_id: str, skill_id: str) -> bool:
        """删除技能（需要检查权限）"""
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
    
    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            return f"{major}.{minor}.{patch}"
        return f"{current_version}.1"
    
    def find_relevant_skill(self, query: str, user_id: Optional[str] = None) -> Optional[Skill]:
        """查找用户有权限访问的相关技能"""
        skills = self.get_all_skills(user_id)
        
        for skill in skills:
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query.lower():
                    return skill
        
        return None
    
    def apply_user_preferences(self, skill: Skill, user_id: str) -> Skill:
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
    
    def check_complexity(self, skill: Skill) -> Dict[str, Any]:
        """
        技能复杂度检查 - 遵循HERMES.md Simplicity First原则
        
        检查技能的复杂度是否在允许范围内，超过阈值需要人工审核
        
        Args:
            skill: 技能对象
        
        Returns:
            检查结果，包含是否通过、问题列表和各项指标
        """
        issues = []
        steps = skill.steps or []
        
        # 检查步骤数
        step_count = len(steps)
        if step_count > self.COMPLEXITY_THRESHOLDS['max_steps']:
            issues.append(f"步骤数({step_count})超过阈值({self.COMPLEXITY_THRESHOLDS['max_steps']})")
        
        # 检查条件分支数
        branch_count = sum(1 for step in steps if step.condition is not None)
        if branch_count > self.COMPLEXITY_THRESHOLDS['max_branches']:
            issues.append(f"条件分支数({branch_count})超过阈值({self.COMPLEXITY_THRESHOLDS['max_branches']})")
        
        # 检查嵌套深度（通过next_step_id链估算）
        nesting_count = 0
        step_map = {s.id: s for s in steps}
        for step in steps:
            current_depth = 0
            current_id = step.next_step_id
            while current_id and current_depth < 10:
                current_depth += 1
                current_id = step_map.get(current_id, None).next_step_id
            nesting_count = max(nesting_count, current_depth)
        
        if nesting_count > self.COMPLEXITY_THRESHOLDS['max_nesting']:
            issues.append(f"嵌套深度({nesting_count})超过阈值({self.COMPLEXITY_THRESHOLDS['max_nesting']})")
        
        # 检查工具调用数
        tool_count = sum(1 for step in steps if step.action == 'execute')
        if tool_count > self.COMPLEXITY_THRESHOLDS['max_tools']:
            issues.append(f"工具调用数({tool_count})超过阈值({self.COMPLEXITY_THRESHOLDS['max_tools']})")
        
        return {
            'is_acceptable': len(issues) == 0,
            'issues': issues,
            'step_count': step_count,
            'branch_count': branch_count,
            'nesting_count': nesting_count,
            'tool_count': tool_count,
            'thresholds': self.COMPLEXITY_THRESHOLDS
        }
    
    def validate_skill_changes(self, original_skill: Skill, updated_skill: Skill, 
                                user_request: str) -> Dict[str, Any]:
        """
        技能变更验证 - 遵循HERMES.md Surgical Changes原则
        
        检查技能变更是否符合"最小diff"原则，拒绝无关变更
        
        Args:
            original_skill: 原始技能
            updated_skill: 更新后的技能
            user_request: 用户的修改请求
        
        Returns:
            验证结果，包含是否通过、变更摘要、警告信息
        """
        changes = []
        warnings = []
        
        # 检查名称变更
        if original_skill.name != updated_skill.name:
            changes.append(f"名称: '{original_skill.name}' -> '{updated_skill.name}'")
        
        # 检查描述变更
        if original_skill.description != updated_skill.description:
            changes.append("描述已修改")
        
        # 检查触发模式变更
        if set(original_skill.trigger_patterns) != set(updated_skill.trigger_patterns):
            changes.append(f"触发模式: {original_skill.trigger_patterns} -> {updated_skill.trigger_patterns}")
        
        # 检查步骤变更
        original_step_ids = {s.id for s in original_skill.steps}
        updated_step_ids = {s.id for s in updated_skill.steps}
        
        added_steps = updated_step_ids - original_step_ids
        removed_steps = original_step_ids - updated_step_ids
        
        if added_steps:
            changes.append(f"新增步骤: {len(added_steps)}个")
        
        if removed_steps:
            changes.append(f"删除步骤: {len(removed_steps)}个")
        
        # 检查步骤内容变更
        for step in updated_skill.steps:
            original_step = next((s for s in original_skill.steps if s.id == step.id), None)
            if original_step:
                if original_step.action != step.action:
                    changes.append(f"步骤{step.id}动作变更: {original_step.action} -> {step.action}")
                if original_step.parameters != step.parameters:
                    changes.append(f"步骤{step.id}参数变更")
        
        # 检查无关变更警告（遵循Surgical Changes原则）
        if len(changes) > 3:
            warnings.append("变更较多，请确认是否都为用户请求所需")
        
        # 检查是否有未请求的变更
        if not user_request and len(changes) > 0:
            warnings.append("没有用户请求，但技能发生了变更")
        
        return {
            'is_valid': len(warnings) == 0,
            'changes': changes,
            'warnings': warnings,
            'change_count': len(changes),
            'change_summary': '; '.join(changes) if changes else '无变更'
        }


skill_manager = SkillManager()
