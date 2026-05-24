"""PPT原子工具集 - 提供PPT生成相关的原子操作"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from tools.base import BaseTool
from tools.registry import register_tool
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
                        "id": match.get("id", ""),
                        "name": match.get("name", ""),
                        "score": match.get("score", 0),
                        "style": match.get("style", "")
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

            from src.services.spec_lock_manager import spec_lock_manager
            spec_lock = spec_lock_manager.lock_spec(
                template_id=template_id,
                user_preferences=style_config
            )

            return {
                "success": True,
                "spec_lock": {
                    "template_id": template_id,
                    "design_spec": spec_lock.get("design_spec", {}),
                    "locked_at": spec_lock.get("locked_at")
                }
            }
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

            from src.services.strategist_planner import StrategistPlanner
            planner = StrategistPlanner()
            outline = planner.generate_outline(
                title=title,
                content=content,
                style_config=style_config
            )

            return {
                "success": True,
                "outline": outline,
                "format": "structured"
            }
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

            from src.services.strategist_planner import StrategistPlanner
            planner = StrategistPlanner()
            slides = planner.generate_slides(
                outline=outline,
                template_id=template_id,
                style_config=style_config
            )

            return {
                "success": True,
                "slides": slides,
                "count": len(slides)
            }
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

            from tools.ppt_generator import GeneratePPT
            generator = GeneratePPT()
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

            from src.services.quality_gate import QualityGate
            quality_gate = QualityGate(strict_mode=False)
            result = quality_gate.gate(file_path)

            return {
                "success": True,
                "passed": result.get("passed", False),
                "score": result.get("score", 0),
                "report": result.get("report", ""),
                "issues": result.get("issues", [])
            }
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
            from src.gateway.im_adapter import get_im_adapter

            file_path = params.get("file_path")
            user_id = params.get("user_id")
            message = params.get("message", "")

            im_adapter = get_im_adapter()
            result = im_adapter.send_file(user_id, file_path, message)

            return {
                "success": result.get("success", False),
                "message_id": result.get("message_id"),
                "sent_at": result.get("sent_at")
            }
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
            from src.data.vector_store import get_memory_store

            key = params.get("key")
            value = params.get("value")
            user_id = params.get("user_id")

            memory_store = get_memory_store()
            memory_store.store(key, value, user_id)

            return {"success": True, "key": key}
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