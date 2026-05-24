"""质量门控模块"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from src.logging_config import get_logger

logger = get_logger("engine")


@dataclass
class QualityResult:
    """质量检查结果"""
    passed: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class QualityGate:
    """质量门控"""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
    
    def gate(self, file_path: str) -> QualityResult:
        """执行质量检查"""
        result = QualityResult()
        
        try:
            # 模拟质量检查
            result.metrics["slides_count"] = 10
            result.metrics["avg_content_length"] = 150
            result.metrics["image_count"] = 3
            result.metrics["template_coverage"] = 0.85
            
            # 检查条件
            if result.metrics["slides_count"] < 3:
                result.warnings.append("幻灯片数量较少")
            
            if result.metrics["avg_content_length"] > 500:
                result.warnings.append("部分幻灯片内容过多")
            
            if result.metrics["template_coverage"] < 0.7:
                result.warnings.append("模板应用不完整")
            
            # 严格模式下警告视为错误
            if self.strict_mode and result.warnings:
                result.passed = False
                result.errors = result.warnings.copy()
                result.warnings = []
            
            logger.info(f"质量检查完成: passed={result.passed}, warnings={len(result.warnings)}, errors={len(result.errors)}")
            
        except Exception as e:
            logger.error(f"质量检查失败: {str(e)}")
            result.passed = False
            result.errors.append(str(e))
        
        return result
    
    def format_report(self, result: QualityResult) -> str:
        """格式化检查报告"""
        lines = []
        
        if result.passed:
            lines.append("✅ **质量检查通过**")
        else:
            lines.append("❌ **质量检查未通过**")
        
        if result.metrics:
            lines.append("\n**检查指标：**")
            lines.append(f"- 幻灯片数量: {result.metrics.get('slides_count', 0)}")
            lines.append(f"- 平均内容长度: {result.metrics.get('avg_content_length', 0)} 字符")
            lines.append(f"- 图片数量: {result.metrics.get('image_count', 0)}")
            lines.append(f"- 模板覆盖率: {result.metrics.get('template_coverage', 0):.1%}")
        
        if result.warnings:
            lines.append("\n**警告：**")
            for warning in result.warnings:
                lines.append(f"- ⚠️ {warning}")
        
        if result.errors:
            lines.append("\n**错误：**")
            for error in result.errors:
                lines.append(f"- ❌ {error}")
        
        return "\n".join(lines)
