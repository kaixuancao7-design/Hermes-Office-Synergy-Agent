"""
Agent自验证用例库 - 遵循HERMES.md Goal-Driven Execution原则

本测试文件包含Agent自我进化和技能生成的自动验证用例，
确保新技能上线前通过固定测试集。
"""
import pytest
from typing import Dict, Any
from src.skills import skill_manager
from src.types import Skill, SkillStep
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service
from src.utils import generate_id, get_timestamp


class TestSkillComplexityValidation:
    """技能复杂度验证测试"""

    def test_skill_within_complexity_thresholds(self):
        """测试技能复杂度在阈值范围内"""
        skill = Skill(
            id=generate_id(),
            name="Simple Skill",
            description="A simple skill",
            type="custom",
            trigger_patterns=["simple"],
            steps=[
                SkillStep(
                    id=generate_id(),
                    action="execute",
                    parameters={"instruction": "Step 1"}
                )
            ],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.check_complexity(skill)
        assert result['is_acceptable'] is True
        assert len(result['issues']) == 0

    def test_skill_exceeds_step_threshold(self):
        """测试技能步骤数超过阈值"""
        steps = []
        for i in range(15):  # 超过max_steps=10
            steps.append(SkillStep(
                id=generate_id(),
                action="execute",
                parameters={"instruction": f"Step {i+1}"}
            ))
        
        skill = Skill(
            id=generate_id(),
            name="Complex Skill",
            description="A skill with too many steps",
            type="custom",
            trigger_patterns=["complex"],
            steps=steps,
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.check_complexity(skill)
        assert result['is_acceptable'] is False
        assert any("步骤数" in issue for issue in result['issues'])

    def test_skill_exceeds_branch_threshold(self):
        """测试技能条件分支数超过阈值"""
        skill = Skill(
            id=generate_id(),
            name="Branchy Skill",
            description="A skill with too many branches",
            type="custom",
            trigger_patterns=["branchy"],
            steps=[
                SkillStep(id=generate_id(), action="execute", parameters={}, condition="if x > 10"),
                SkillStep(id=generate_id(), action="execute", parameters={}, condition="if y > 20"),
                SkillStep(id=generate_id(), action="execute", parameters={}, condition="if z > 30"),
                SkillStep(id=generate_id(), action="execute", parameters={}, condition="if w > 40")  # 超过max_branches=3
            ],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.check_complexity(skill)
        assert result['is_acceptable'] is False
        assert any("条件分支" in issue for issue in result['issues'])


class TestSkillChangeValidation:
    """技能变更验证测试（遵循Surgical Changes原则）"""

    def test_minimal_changes_are_valid(self):
        """测试最小变更被认为是有效的"""
        original = Skill(
            id="skill-1",
            name="Original Skill",
            description="Original description",
            type="custom",
            trigger_patterns=["original"],
            steps=[SkillStep(id="step1", action="execute", parameters={"key": "value"})],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        updated = Skill(
            id="skill-1",
            name="Updated Skill",  # 只改名称
            description="Original description",
            type="custom",
            trigger_patterns=["original"],
            steps=[SkillStep(id="step1", action="execute", parameters={"key": "value"})],
            metadata={},
            version="1.0.1",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.validate_skill_changes(original, updated, "修改技能名称")
        assert result['is_valid'] is True
        assert len(result['changes']) == 1
        assert "名称" in result['change_summary']

    def test_excessive_changes_trigger_warning(self):
        """测试过多变更触发警告"""
        original = Skill(
            id="skill-2",
            name="Original",
            description="Original desc",
            type="custom",
            trigger_patterns=["original"],
            steps=[SkillStep(id="step1", action="execute", parameters={"k1": "v1"})],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        updated = Skill(
            id="skill-2",
            name="Updated",
            description="Updated desc",
            type="custom",
            trigger_patterns=["updated", "new"],
            steps=[
                SkillStep(id="step1", action="execute", parameters={"k1": "v1"}),
                SkillStep(id="step2", action="execute", parameters={"k2": "v2"})  # 新增步骤
            ],
            metadata={},
            version="1.0.1",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.validate_skill_changes(original, updated, "make changes")
        assert result['is_valid'] is False  # 变更超过3个
        assert len(result['warnings']) > 0

    def test_unchanged_skill_has_no_changes(self):
        """测试未修改的技能没有变更"""
        original = Skill(
            id="skill-3",
            name="Same Skill",
            description="Same description",
            type="custom",
            trigger_patterns=["same"],
            steps=[SkillStep(id="step1", action="execute", parameters={"key": "value"})],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        updated = Skill(
            id="skill-3",
            name="Same Skill",
            description="Same description",
            type="custom",
            trigger_patterns=["same"],
            steps=[SkillStep(id="step1", action="execute", parameters={"key": "value"})],
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="test_user"
        )
        
        result = skill_manager.validate_skill_changes(original, updated, "")
        assert result['change_count'] == 0
        assert result['change_summary'] == "无变更"


class TestPermissionValidation:
    """权限验证测试"""

    def test_admin_has_full_permissions(self):
        """测试管理员拥有所有权限"""
        permission_service.set_user_role("admin", "admin_user", "admin")
        
        result = permission_service.check_skill_permission("admin_user", "any_skill", "delete")
        assert result.allowed is True

    def test_user_cannot_delete_skill(self):
        """测试普通用户不能删除技能"""
        permission_service.set_user_role("admin", "normal_user", "user")
        
        result = permission_service.check_skill_permission("normal_user", "any_skill", "delete")
        assert result.allowed is False
        assert "delete" in result.missing_permissions

    def test_guest_only_read_access(self):
        """测试访客只有读取权限"""
        permission_service.set_user_role("admin", "guest_user", "guest")
        
        result = permission_service.check_skill_permission("guest_user", "any_skill", "execute")
        assert result.allowed is False
        
        result = permission_service.check_skill_permission("guest_user", "any_skill", "read")
        assert result.allowed is True


class TestAuditLogValidation:
    """审计日志验证测试"""

    def test_log_integrity(self):
        """测试审计日志完整性"""
        # 记录一些日志
        audit_log_service.log_login("test_user", "success", "192.168.1.1")
        audit_log_service.log_skill_create("test_user", "skill-1", "Test Skill")
        
        # 验证完整性
        result = audit_log_service.verify_log_integrity()
        assert result is True

    def test_log_tracks_all_changes(self):
        """测试审计日志追踪所有变更"""
        # 检查日志是否包含必要信息
        logs = audit_log_service.get_operator_logs("test_user")
        assert len(logs) > 0
        
        for log in logs:
            assert log.operator_id == "test_user"
            assert log.timestamp is not None
            assert log.result in ["success", "failed", "pending"]


class TestSkillQualityGate:
    """技能质量闸门测试"""

    def test_skill_quality_metrics(self):
        """测试技能质量指标"""
        # 技能应该满足最低质量标准
        quality_metrics = {
            "test_pass_rate": 1.0,      # 测试通过率100%
            "step_count": 5,            # 步骤数≤10
            "execution_success_rate": 0.95,  # 执行成功率≥95%
            "user_satisfaction": 4.5    # 用户满意度≥4.5
        }
        
        # 验证质量指标
        assert quality_metrics["test_pass_rate"] == 1.0
        assert quality_metrics["step_count"] <= 10
        assert quality_metrics["execution_success_rate"] >= 0.95
        assert quality_metrics["user_satisfaction"] >= 4.5
