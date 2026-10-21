"""PPT原子工具集 - 提供PPT生成相关的原子操作"""

import json
from dataclasses import asdict
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from src.tools.base import BaseTool
from src.tools.registry import register_tool
from src.logging_config import get_logger

logger = get_logger("tool.ppt")


class TemplateMatchSchema(BaseModel):
    content: str = Field(description="PPT内容", default="")
    style_hint: Optional[str] = Field(description="风格提示", default=None)


@register_tool("ppt_template_match")
class TemplateMatchTool(BaseTool):
    name = "ppt_template_match"
    description = "根据内容匹配合适的PPT模板"
    schema = TemplateMatchSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            content = params.get("content", "")
            style_hint = params.get("style_hint")
            
            from src.services.template_matcher import template_matcher
            matches = template_matcher.match_layout(content, style_hint)

            return {
                "success": True,
                "templates": [
                    {
                        "id": match.template_id,
                        "name": match.name,
                        "score": match.score,
                        "style": match.metadata.get("style", "")
                    } for match in matches
                ]
            }
        except Exception as e:
            logger.error(f"模板匹配失败: {str(e)}")
            return {"success": False, "error": str(e)}


class SpecLockSchema(BaseModel):
    template_id: str = Field(description="模板ID")
    style_config: Optional[Dict[str, Any]] = Field(description="风格配置", default={})


@register_tool("ppt_spec_lock")
class SpecLockTool(BaseTool):
    name = "ppt_spec_lock"
    description = "锁定PPT的设计规格"
    schema = SpecLockSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            template_id = params.get("template_id")
            style_config = params.get("style_config", {})

            from src.engine.spec_lock import spec_lock_manager
            from src.services.template_matcher import template_matcher
            template = template_matcher.get_template_by_id(template_id)
            if template is None:
                raise ValueError("Unknown template")
            lock = spec_lock_manager.create_lock(params["user_id"], template_id, template)
            lock.update(style_config)
            return {"success": True, "spec_lock": asdict(lock)}

        except Exception as e:
            logger.error(f"规格锁定失败: {str(e)}")
            return {"success": False, "error": str(e)}


class GenerateOutlineSchema(BaseModel):
    title: str = Field(description="PPT标题")
    content: str = Field(description="内容文本")
    style_config: Optional[Dict[str, Any]] = Field(description="风格配置", default=None)


@register_tool("ppt_generate_outline")
class GenerateOutlineTool(BaseTool):
    name = "ppt_generate_outline"
    description = "根据内容生成PPT大纲"
    schema = GenerateOutlineSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            title = params.get("title", "")
            content = params.get("content", "")
            style_config = params.get("style_config")

            outline = _model_list(f"Generate a PPT outline as a JSON array of objects with title and content. Title: {title}\nSource: {content}")
            return {"success": True, "outline": outline, "format": "structured"}

        except Exception as e:
            logger.error(f"大纲生成失败: {str(e)}")
            return {"success": False, "error": str(e)}


class GenerateContentSchema(BaseModel):
    outline: List[Dict[str, Any]] = Field(description="PPT大纲")
    template_id: str = Field(description="模板ID")
    style_config: Optional[Dict[str, Any]] = Field(description="风格配置", default=None)


@register_tool("ppt_generate_content")
class GenerateContentTool(BaseTool):
    name = "ppt_generate_content"
    description = "根据大纲生成PPT幻灯片内容"
    schema = GenerateContentSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            outline = params.get("outline", [])
            template_id = params.get("template_id", "")
            style_config = params.get("style_config")

            slides = _model_list("Generate slide objects as a JSON array. Each object must have type (title, content or bullet), title, and content. "
                                 + json.dumps(outline, ensure_ascii=False))
            return {"success": True, "slides": slides, "count": len(slides)}

        except Exception as e:
            logger.error(f"内容生成失败: {str(e)}")
            return {"success": False, "error": str(e)}


class GeneratePPTToolSchema(BaseModel):
    title: str = Field(description="PPT标题")
    slides: List[Dict[str, Any]] = Field(description="幻灯片内容")
    output_path: Optional[str] = Field(description="输出路径", default=None)


@register_tool("ppt_generate_file")
class GeneratePPTTool(BaseTool):
    name = "ppt_generate_file"
    description = "根据幻灯片内容生成PPTX文件"
    schema = GeneratePPTToolSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            title = params.get("title", "演示文稿")
            slides = params.get("slides", [])
            output_path = params.get("output_path")
            # 导入PPT生成器
            from src.tools.ppt_generator import PPTGeneratorBase
            generator = PPTGeneratorBase()
            result_path = generator.generate_ppt(
                title=title,
                slides=slides,
                output_path=output_path
            )

            return {
                "success": True,
                "file_path": result_path,
                "slides_count": len(slides)
            }
        except Exception as e:
            logger.error(f"PPT文件生成失败: {str(e)}")
            return {"success": False, "error": str(e)}


class QualityCheckSchema(BaseModel):
    file_path: str = Field(description="PPT文件路径")


@register_tool("ppt_quality_check")
class QualityCheckTool(BaseTool):
    name = "ppt_quality_check"
    description = "检查生成的PPT质量"
    schema = QualityCheckSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            file_path = params.get("file_path")

            from src.engine.quality_gate import QualityGate
            from src.tools.runtime import within
            if not within(file_path, ["output"]):
                raise PermissionError("PPT quality check path must be inside output")
            quality_gate = QualityGate(strict_mode=False)
            result = quality_gate.gate(file_path)
            return {"success": result.passed, "passed": result.passed,
                    "report": quality_gate.format_report(result), "issues": result.errors + result.warnings,
                    "metrics": result.metrics, "error": "; ".join(result.errors) if not result.passed else ""}

        except Exception as e:
            logger.error(f"质量检查失败: {str(e)}")
            return {"success": False, "error": str(e)}


class FeishuSendFileSchema(BaseModel):
    file_path: str = Field(description="文件路径")
    user_id: str = Field(description="用户ID")
    message: Optional[str] = Field(description="附带消息", default=None)


@register_tool("ppt_feishu_send")
class FeishuSendFileTool(BaseTool):
    name = "ppt_feishu_send"
    description = "发送PPT文件到飞书"
    schema = FeishuSendFileSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.plugins import get_im_adapter
            from src.tools.runtime import run_sync, within
            import inspect
            file_path = params["file_path"]
            if not within(file_path, ["output"]):
                raise PermissionError("Only generated output files may be sent")
            adapter = get_im_adapter()
            if adapter is None:
                raise RuntimeError("IM adapter is unavailable")
            result = adapter.send_file(params["user_id"], file_path)
            if inspect.isawaitable(result):
                result = run_sync(result)
            return result if isinstance(result, dict) else {"success": bool(result)}

        except Exception as e:
            logger.error(f"飞书发送失败: {str(e)}")
            return {"success": False, "error": str(e)}


class ContextStoreSchema(BaseModel):
    key: str = Field(description="存储键")
    value: Any = Field(description="存储值")
    user_id: Optional[str] = Field(description="用户ID", default=None)


@register_tool("ppt_context_store")
class ContextStoreTool(BaseTool):
    name = "ppt_context_store"
    description = "存储和检索PPT工作流上下文数据"
    schema = ContextStoreSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.plugins import get_memory_store
            key = params["key"]
            store = get_memory_store()
            if store is None:
                raise RuntimeError("Memory store is unavailable")
            success = store.store(f"{params['user_id']}:{key}", params["value"])
            return {"success": bool(success), "key": key}

        except Exception as e:
            logger.error(f"上下文存储失败: {str(e)}")
            return {"success": False, "error": str(e)}


def get_all_ppt_tools() -> List[type]:
    """获取所有PPT工具类"""
    return [
        TemplateMatchTool,
        SpecLockTool,
        GenerateOutlineTool,
        GenerateContentTool,
        GeneratePPTTool,
        QualityCheckTool,
        FeishuSendFileTool,
        ContextStoreTool
    ]

def _model_list(prompt):
    from src.plugins.model_routers import call_model
    from src.tools.runtime import run_sync
    response = run_sync(call_model(prompt)).strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1].rsplit("```", 1)[0]
    value = json.loads(response)
    if not isinstance(value, list) or not value or any(not isinstance(x, dict) for x in value):
        raise ValueError("Model must return a nonempty JSON array of objects")
    return value
