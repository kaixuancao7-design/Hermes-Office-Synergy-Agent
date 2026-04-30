"""规格锁定器 - 锁定设计参数防止上下文漂移"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from src.logging_config import get_logger

logger = get_logger("engine.spec_lock")


@dataclass
class Violation:
    """违规项"""
    field: str
    expected: Any
    actual: Any
    severity: str  # "error" or "warning"


@dataclass
class VerificationResult:
    """验证结果"""
    passed: bool
    violations: List[Violation] = field(default_factory=list)

    def add_violation(self, field: str, expected: Any, actual: Any, severity: str = "error"):
        self.violations.append(Violation(field, expected, actual, severity))
        self.passed = False


class SpecLock:
    """规格锁定器 - 锁定设计参数防止上下文漂移

    在PPT生成过程中锁定设计规格，确保生成的每一页都遵循统一的设计规范，
    防止模型在生成长内容时出现上下文漂移（颜色、字体、风格不一致）。
    """

    def __init__(self, spec: Dict[str, Any]):
        """
        初始化规格锁定器

        Args:
            spec: 设计规格字典，包含:
                - canvas: 画布格式
                - color_scheme: 配色方案
                - font_family: 字体方案
                - icon_approach: 图标策略
                - image_approach: 图片策略
                - page_style: 页面风格
        """
        self._spec = spec
        self._locked = True
        self._generation_history: List[Dict[str, Any]] = []

        self.canvas = spec.get("canvas", "16:9")
        self.color_scheme = spec.get("color_scheme", {})
        self.font_family = spec.get("font_family", {})
        self.icon_approach = spec.get("icon_approach", "outline")
        self.image_approach = spec.get("image_approach", "realistic")
        self.page_style = spec.get("page_style", "professional")

        logger.info(f"SpecLock initialized: canvas={self.canvas}, style={self.page_style}")

    def re_read(self) -> Dict[str, Any]:
        """每次生成页面时重新读取，确保参数一致"""
        return {
            "canvas": self.canvas,
            "color_scheme": self.color_scheme,
            "font_family": self.font_family,
            "icon_approach": self.icon_approach,
            "image_approach": self.image_approach,
            "page_style": self.page_style
        }

    def verify(self, actual: Dict[str, Any]) -> VerificationResult:
        """
        验证实际使用的参数是否符合规格

        Args:
            actual: 实际使用的参数

        Returns:
            验证结果
        """
        result = VerificationResult(passed=True)

        if self._locked:
            if actual.get("color") and actual["color"] != self.color_scheme.get("primary"):
                result.add_violation(
                    "color",
                    self.color_scheme.get("primary"),
                    actual.get("color"),
                    "error"
                )

            if actual.get("font") and actual["font"] != self.font_family.get("heading"):
                result.add_violation(
                    "font",
                    self.font_family.get("heading"),
                    actual.get("font"),
                    "warning"
                )

            if actual.get("icon_style") and actual["icon_style"] != self.icon_approach:
                result.add_violation(
                    "icon_style",
                    self.icon_approach,
                    actual.get("icon_style"),
                    "warning"
                )

        return result

    def record_page(self, page_params: Dict[str, Any]):
        """记录已生成的页面参数，用于后续审计"""
        self._generation_history.append({
            "params": page_params,
            "spec_snapshot": self.re_read()
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """获取生成历史"""
        return self._generation_history

    def check_consistency(self) -> VerificationResult:
        """检查所有已生成页面的一致性"""
        result = VerificationResult(passed=True)

        if not self._generation_history:
            return result

        first_spec = self._generation_history[0]["spec_snapshot"]
        for i, record in enumerate(self._generation_history[1:], 1):
            current_spec = record["spec_snapshot"]

            if current_spec["color_scheme"] != first_spec["color_scheme"]:
                result.add_violation(
                    f"page_{i}_color",
                    first_spec["color_scheme"],
                    current_spec["color_scheme"],
                    "error"
                )

            if current_spec["font_family"] != first_spec["font_family"]:
                result.add_violation(
                    f"page_{i}_font",
                    first_spec["font_family"],
                    current_spec["font_family"],
                    "error"
                )

        return result

    def unlock(self):
        """解锁规格，允许临时变更"""
        self._locked = False
        logger.info("SpecLock unlocked - temporary changes allowed")

    def lock(self):
        """重新锁定规格"""
        self._locked = True
        logger.info("SpecLock re-locked")

    @classmethod
    def from_template(cls, template_id: str, template_data: Dict[str, Any]) -> "SpecLock":
        """
        从模板创建规格锁定器

        Args:
            template_id: 模板ID
            template_data: 模板数据

        Returns:
            SpecLock实例
        """
        spec = {
            "canvas": template_data.get("canvas", "16:9"),
            "color_scheme": template_data.get("color_scheme", {}),
            "font_family": template_data.get("font_family", {}),
            "icon_approach": template_data.get("icon_style", "outline"),
            "image_approach": "realistic",
            "page_style": template_id
        }

        logger.info(f"SpecLock created from template: {template_id}")
        return cls(spec)

    def to_spec_lock_file(self) -> Dict[str, Any]:
        """导出为规格锁定文件格式（机器可读）"""
        return {
            "version": "1.0",
            "canvas": self.canvas,
            "color_scheme": self.color_scheme,
            "font_family": self.font_family,
            "icon_approach": self.icon_approach,
            "image_approach": self.image_approach,
            "page_style": self.page_style
        }


class SpecLockManager:
    """规格锁定管理器 - 管理多个项目的规格锁定"""

    def __init__(self):
        self._locks: Dict[str, SpecLock] = {}

    def create_lock(self, project_id: str, spec: Dict[str, Any]) -> SpecLock:
        """为项目创建规格锁定"""
        lock = SpecLock(spec)
        self._locks[project_id] = lock
        logger.info(f"SpecLock created for project: {project_id}")
        return lock

    def get_lock(self, project_id: str) -> Optional[SpecLock]:
        """获取项目的规格锁定"""
        return self._locks.get(project_id)

    def remove_lock(self, project_id: str):
        """移除项目的规格锁定"""
        if project_id in self._locks:
            del self._locks[project_id]
            logger.info(f"SpecLock removed for project: {project_id}")

    def verify_project(self, project_id: str, page_params: Dict[str, Any]) -> VerificationResult:
        """验证项目页面参数"""
        lock = self.get_lock(project_id)
        if not lock:
            logger.warning(f"No SpecLock found for project: {project_id}")
            return VerificationResult(passed=True)

        result = lock.verify(page_params)
        if not result.passed:
            logger.warning(f"SpecLock violations found: {result.violations}")

        return result


spec_lock_manager = SpecLockManager()
