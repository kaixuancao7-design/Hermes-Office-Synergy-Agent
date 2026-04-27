from typing import Dict, Any
from src.logging_config import get_logger
from src.tools.base import BaseTool, ToolSchema
from src.tools.registry import register_tool
from src.tools.ppt_generator import PPTGeneratorBase
from pydantic import Field

logger = get_logger("tool.content")


class GenerateOutlineSchema(ToolSchema):
    """生成大纲工具参数Schema"""
    content: str = Field(description="文件内容", default="")
    title: str = Field(description="PPT标题", default="文档总结")


class GeneratePPTFromContentSchema(ToolSchema):
    """根据内容生成PPT工具参数Schema"""
    content: str = Field(description="文件内容", default="")
    file_key: str = Field(description="飞书文件Key", default="")
    title: str = Field(description="PPT标题", default="文档总结")
    user_id: str = Field(description="用户ID", default="")


@register_tool("generate_outline")
class GenerateOutline(BaseTool):
    """根据内容生成PPT大纲工具"""
    
    description = "根据文档内容生成结构化的PPT大纲"
    schema = GenerateOutlineSchema
    
    def execute(self, params: Dict[str, Any]) -> str:
        content = params.get("content", "")
        title = params.get("title", "文档总结")
        
        if not content:
            return "Error: content is required"
        
        try:
            from src.plugins.model_routers import select_model, call_model
            
            model = select_model("summarization", "complex")
            if not model:
                model = select_model("document_analysis", "complex")
            
            if not model:
                return "Error: No suitable model available for outline generation"
            
            prompt = f"""根据以下文档内容，生成一个结构化的PPT大纲：

文档内容：
{content}

要求：
1. 分析文档核心内容，提取关键章节
2. 每个章节包含：章节标题 + 主要要点（3-5个）
3. 大纲结构清晰，逻辑连贯
4. 使用中文输出

PPT标题：{title}

请输出JSON格式，结构如下：
[
  {{"title": "章节1标题", "content": ["要点1", "要点2", "要点3"]}},
  {{"title": "章节2标题", "content": ["要点1", "要点2"]}}
]
"""
            result = call_model(model, [{"role": "user", "content": prompt}])
            
            import json
            try:
                outline = json.loads(result)
                if isinstance(outline, list) and len(outline) > 0:
                    logger.info(f"大纲生成成功，共 {len(outline)} 个章节")
                    return json.dumps(outline, ensure_ascii=False, indent=2)
                else:
                    return f"Error: Invalid outline format: {result}"
            except json.JSONDecodeError:
                return f"Error: Failed to parse outline: {result[:200]}..."
                
        except Exception as e:
            logger.error(f"Outline generation failed: {str(e)}")
            return f"大纲生成失败: {str(e)}"


@register_tool("generate_ppt_from_content")
class GeneratePPTFromContent(BaseTool):
    """根据文件内容生成PPT工具（完整流程：内容→大纲→PPT）"""
    
    description = "根据文件内容直接生成PPT，包含大纲生成和PPT生成两个步骤"
    schema = GeneratePPTFromContentSchema
    
    def _get_content_from_vector_db(self, file_key: str, user_id: str = None) -> str:
        """从向量数据库中获取文件内容"""
        try:
            from src.data.database import db
            
            memories = db.get_memories_by_tag(file_key, user_id)
            
            if memories:
                memories.sort(key=lambda m: m.timestamp, reverse=True)
                return memories[0].content
            
            return ""
            
        except Exception as e:
            logger.error(f"从向量数据库获取文件内容失败: {str(e)}")
            return ""
    
    def execute(self, params: Dict[str, Any]) -> str:
        content = params.get("content", "")
        title = params.get("title", "文档总结")
        file_key = params.get("file_key", "")
        user_id = params.get("user_id", "")
        
        # 如果没有直接提供content，但提供了file_key，则先从本地存储获取文件内容
        if not content and file_key:
            logger.info(f"通过file_key从本地存储获取文件内容: {file_key}")
            
            content = self._get_content_from_vector_db(file_key, user_id)
            
            if not content:
                logger.info(f"本地存储未找到，尝试从飞书下载: {file_key}")
                from src.plugins.im_adapters import FeishuAdapter
                feishu_adapter = FeishuAdapter()
                try:
                    content = feishu_adapter.read_file(file_key)
                    if not content:
                        return "Error: Failed to read file content"
                    logger.info(f"从飞书下载文件成功，内容长度: {len(content)}")
                except Exception as e:
                    logger.error(f"从飞书读取文件失败: {str(e)}")
                    return f"Error: Failed to read file: {str(e)}"
            else:
                logger.info(f"从本地存储获取文件内容成功，内容长度: {len(content)}")
        
        if not content:
            return "Error: content is required"
        
        try:
            logger.info(f"开始根据内容生成PPT，内容长度: {len(content)}")
            
            # 步骤1：根据内容生成大纲
            outline_tool = GenerateOutline()
            outline_result = outline_tool.execute({"content": content, "title": title})
            
            import json
            try:
                outline = json.loads(outline_result)
                if not isinstance(outline, list) or len(outline) == 0:
                    return f"Error: Failed to generate outline: {outline_result}"
            except json.JSONDecodeError:
                return f"Error: Invalid outline: {outline_result[:100]}..."
            
            logger.info(f"大纲生成成功，共 {len(outline)} 个章节")
            
            # 步骤2：根据大纲生成PPT
            generator = PPTGeneratorBase()
            output_path = generator.generate_from_outline(title, outline)
            
            logger.info(f"PPT生成成功: {output_path}")
            return f"PPT生成成功！\n\n大纲章节: {len(outline)} 个\n文件路径: {output_path}"
            
        except Exception as e:
            logger.error(f"Generate PPT from content failed: {str(e)}")
            return f"根据内容生成PPT失败: {str(e)}"
