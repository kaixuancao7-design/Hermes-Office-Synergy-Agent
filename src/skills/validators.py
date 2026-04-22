"""技能验证模块 - 验证技能的复杂度和变更合理性"""

from typing import Dict, Any, List
from src.types import Skill
from src.logging_config import get_logger

logger = get_logger("skill")


class SkillValidator:
    """技能验证器 - 验证技能的复杂度和变更合理性"""

    # 复杂度阈值
    COMPLEXITY_THRESHOLDS = {
        "max_steps": 10,           # 最大步骤数
        "max_branches": 3,         # 最大条件分支数
        "max_nesting": 2,          # 最大嵌套深度
        "max_tools": 5             # 最大工具调用数
    }

    def check_complexity(self, skill: Skill) -> Dict[str, Any]:
        """检查技能复杂度"""
        analysis = {
            "is_complex": False,
            "violations": [],
            "warnings": [],
            "metrics": {}
        }

        # 检查步骤数
        steps_count = len(skill.steps)
        analysis["metrics"]["steps_count"] = steps_count
        if steps_count > self.COMPLEXITY_THRESHOLDS["max_steps"]:
            analysis["is_complex"] = True
            analysis["violations"].append(
                f"步骤数({steps_count})超过最大限制({self.COMPLEXITY_THRESHOLDS['max_steps']})"
            )
        elif steps_count > self.COMPLEXITY_THRESHOLDS["max_steps"] * 0.8:
            analysis["warnings"].append(
                f"步骤数({steps_count})接近最大限制"
            )

        # 检查条件分支数
        branch_count = sum(1 for step in skill.steps if step.condition)
        analysis["metrics"]["branch_count"] = branch_count
        if branch_count > self.COMPLEXITY_THRESHOLDS["max_branches"]:
            analysis["is_complex"] = True
            analysis["violations"].append(
                f"条件分支数({branch_count})超过最大限制({self.COMPLEXITY_THRESHOLDS['max_branches']})"
            )

        # 检查嵌套深度（简化版：通过next_step_id引用次数计算）
        nesting_depth = self._calculate_nesting_depth(skill.steps)
        analysis["metrics"]["nesting_depth"] = nesting_depth
        if nesting_depth > self.COMPLEXITY_THRESHOLDS["max_nesting"]:
            analysis["is_complex"] = True
            analysis["violations"].append(
                f"嵌套深度({nesting_depth})超过最大限制({self.COMPLEXITY_THRESHOLDS['max_nesting']})"
            )

        # 检查工具调用数
        tool_count = self._count_tool_calls(skill.steps)
        analysis["metrics"]["tool_count"] = tool_count
        if tool_count > self.COMPLEXITY_THRESHOLDS["max_tools"]:
            analysis["is_complex"] = True
            analysis["violations"].append(
                f"工具调用数({tool_count})超过最大限制({self.COMPLEXITY_THRESHOLDS['max_tools']})"
            )

        # 设置建议
        if analysis["is_complex"]:
            analysis["suggestion"] = "建议拆分技能或进入人工审核流程"
        else:
            analysis["suggestion"] = "技能复杂度在可接受范围内"

        logger.debug(f"Skill complexity check: {skill.name} -> {analysis}")
        return analysis

    def _calculate_nesting_depth(self, steps: List) -> int:
        """计算嵌套深度"""
        # 简化的嵌套深度计算：统计有多少步骤有next_step_id指向其他步骤
        next_step_ids = set()
        for step in steps:
            if step.next_step_id:
                next_step_ids.add(step.next_step_id)

        # 深度至少为1（如果有步骤）
        if not steps:
            return 0

        # 简单估算：如果有循环引用或多个分支，深度增加
        depth = 1
        if len(next_step_ids) >= 2:
            depth += 1
        if len(next_step_ids) >= len(steps) * 0.5:
            depth += 1

        return depth

    def _count_tool_calls(self, steps: List) -> int:
        """计算工具调用数"""
        count = 0
        for step in steps:
            if step.action == "execute" and "tool_id" in step.parameters:
                count += 1
        return count

    def validate_skill_changes(self, original_skill: Skill, updated_skill: Skill,
                                user_request: str) -> Dict[str, Any]:
        """验证技能变更的合理性"""
        validation = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "changes": []
        }

        # 检查变更是否符合最小diff原则
        changes = self._detect_changes(original_skill, updated_skill)
        validation["changes"] = changes

        # 检查变更数量（同一版本不超过3处）
        total_changes = sum(len(v) for v in changes.values())
        if total_changes > 3:
            validation["is_valid"] = False
            validation["issues"].append(f"变更数量({total_changes})超过限制(3)，请分批更新")

        # 检查变更是否与用户请求相关
        relevance = self._check_relevance(changes, user_request)
        if not relevance:
            validation["is_valid"] = False
            validation["issues"].append("变更内容与用户请求不相关")

        # 检查是否有危险变更
        dangerous_changes = self._check_dangerous_changes(original_skill, updated_skill)
        if dangerous_changes:
            validation["warnings"].extend(dangerous_changes)

        # 再次检查复杂度
        complexity = self.check_complexity(updated_skill)
        if complexity["is_complex"]:
            validation["warnings"].append("更新后的技能复杂度较高")
            validation["complexity_analysis"] = complexity

        logger.debug(f"Skill change validation: {original_skill.name} -> {validation}")
        return validation

    def _detect_changes(self, original: Skill, updated: Skill) -> Dict[str, List[str]]:
        """检测技能变更"""
        changes = {}

        if original.name != updated.name:
            changes["name"] = [f"从 '{original.name}' 改为 '{updated.name}'"]

        if original.description != updated.description:
            changes["description"] = ["描述已更新"]

        if original.trigger_patterns != updated.trigger_patterns:
            changes["trigger_patterns"] = [
                f"从 {original.trigger_patterns} 改为 {updated.trigger_patterns}"
            ]

        original_steps = {s.id: s for s in original.steps}
        updated_steps = {s.id: s for s in updated.steps}

        # 检测新增步骤
        new_steps = [s for s in updated.steps if s.id not in original_steps]
        if new_steps:
            changes["added_steps"] = [f"新增步骤: {s.id}" for s in new_steps]

        # 检测删除步骤
        deleted_steps = [s for s in original.steps if s.id not in updated_steps]
        if deleted_steps:
            changes["deleted_steps"] = [f"删除步骤: {s.id}" for s in deleted_steps]

        # 检测修改的步骤
        modified_steps = []
        for step_id, original_step in original_steps.items():
            if step_id in updated_steps:
                updated_step = updated_steps[step_id]
                if original_step != updated_step:
                    modified_steps.append(f"修改步骤: {step_id}")
        if modified_steps:
            changes["modified_steps"] = modified_steps

        return changes

    def _check_relevance(self, changes: Dict[str, List[str]], user_request: str) -> bool:
        """检查变更是否与用户请求相关"""
        # 简单的相关性检查：检查变更描述是否包含用户请求中的关键词
        request_lower = user_request.lower()

        for change_list in changes.values():
            for change in change_list:
                change_lower = change.lower()
                # 如果变更描述中的关键词在用户请求中，认为相关
                if any(word in request_lower for word in change_lower.split()[:3]):
                    return True

        # 如果只有名称变更，认为相关
        if len(changes) == 1 and "name" in changes:
            return True

        # 如果变更很少（1处），默认认为相关
        total_changes = sum(len(v) for v in changes.values())
        if total_changes <= 1:
            return True

        return False

    def _check_dangerous_changes(self, original: Skill, updated: Skill) -> List[str]:
        """检查是否有危险变更"""
        warnings = []

        # 检查是否从预设技能变为其他类型
        if original.type == "preset" and updated.type != "preset":
            warnings.append("不建议将预设技能转换为其他类型")

        # 检查步骤数量大幅增加
        original_steps = len(original.steps)
        updated_steps = len(updated.steps)
        if updated_steps > original_steps * 2:
            warnings.append(f"步骤数量增加超过100% ({original_steps} -> {updated_steps})")

        return warnings


# 全局实例
skill_validator = SkillValidator()