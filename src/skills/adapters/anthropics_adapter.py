"""anthropics/skills 适配器 - 将外部技能系统转换为项目格式"""

from typing import Dict, Any, Optional
from src.logging_config import get_logger

logger = get_logger("anthropics_adapter")


class AnthropicsSkillAdapter:
    """
    anthropics/skills 适配器类
    
    提供统一接口，将 anthropics/skills 的技能转换为项目可识别的格式
    支持多种技能类型：pptx, docx, xlsx, pdf 等
    """

    def __init__(self):
        """初始化适配器"""
        self._skill_cache = {}
        self._load_anthropics_skills()

    def _load_anthropics_skills(self):
        """尝试加载 anthropics/skills 模块"""
        try:
            # 尝试导入 anthropics_skills
            global anthropics_skills
            import anthropics_skills
            logger.info("✅ anthropics_skills 模块加载成功")
        except ImportError:
            logger.warning("⚠️ anthropics_skills 模块未安装，将使用本地实现")
            anthropics_skills = None

    def is_available(self) -> bool:
        """检查 anthropics_skills 是否可用"""
        return anthropics_skills is not None

    def convert_skill(self, anthropics_skill) -> Dict[str, Any]:
        """
        将 anthropics 技能对象转换为项目格式
        
        Args:
            anthropics_skill: anthropics/skills 的技能对象
        
        Returns:
            项目格式的技能字典
        """
        return {
            "id": anthropics_skill.skill_id,
            "name": anthropics_skill.name,
            "description": anthropics_skill.description,
            "tool_name": f"anthropics_{anthropics_skill.skill_id}",
            "parameters": self._convert_parameters(anthropics_skill.parameters),
            "source": "anthropics"
        }

    def _convert_parameters(self, anthropics_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换参数格式
        
        Args:
            anthropics_params: anthropics 格式的参数
            
        Returns:
            项目格式的参数
        """
        converted = {}
        
        for key, value in anthropics_params.items():
            # 映射参数名称
            if key == "input_content":
                converted["content"] = value
            elif key == "output_file_path":
                converted["output_path"] = value
            elif key == "document_title":
                converted["title"] = value
            else:
                converted[key] = value
        
        return converted

    def execute_pptx_skill(self, params: Dict[str, Any]) -> str:
        """
        执行 PPTX 技能
        
        Args:
            params: 项目格式的参数，包含:
                - content: 文档内容
                - title: PPT标题（可选）
                - output_path: 输出路径（可选）
        
        Returns:
            生成的PPT文件路径
        """
        if not self.is_available():
            logger.warning("anthropics_skills 不可用，回退到本地实现")
            return self._fallback_pptx_generation(params)

        try:
            # 导入 anthropics_skills 的 PPTX 技能
            from anthropics_skills import pptx_skill
            
            # 转换参数格式
            anthropics_params = self._to_anthropics_format(params)
            
            # 执行技能
            result = pptx_skill.generate(anthropics_params)
            
            # 返回结果
            if hasattr(result, 'output_path'):
                logger.info(f"✅ anthropics PPTX 技能执行成功: {result.output_path}")
                return result.output_path
            else:
                logger.info(f"✅ anthropics PPTX 技能执行成功")
                return str(result)
                
        except Exception as e:
            logger.error(f"❌ anthropics PPTX 技能执行失败: {str(e)}")
            # 回退到本地实现
            return self._fallback_pptx_generation(params)

    def _to_anthropics_format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        将项目参数格式转换为 anthropics 格式
        
        Args:
            params: 项目格式的参数
            
        Returns:
            anthropics 格式的参数
        """
        return {
            "input_content": params.get("content", ""),
            "document_title": params.get("title", "文档总结"),
            "output_file_path": params.get("output_path", ""),
            "slide_count": params.get("slide_count", 10)
        }

    def _fallback_pptx_generation(self, params: Dict[str, Any]) -> str:
        """
        回退到本地 PPT 生成实现
        
        Args:
            params: 项目格式的参数
            
        Returns:
            生成的PPT文件路径
        """
        from src.tools.tool_executor import PPTGenerator
        
        try:
            # 使用本地实现生成PPT
            generator = PPTGenerator()
            
            # 简单生成演示文稿
            slides = self._generate_slides_from_content(params.get("content", ""))
            
            output_path = generator.generate_ppt(
                title=params.get("title", "文档总结"),
                slides=slides
            )
            
            logger.info(f"✅ 本地PPT生成成功: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ 本地PPT生成失败: {str(e)}")
            raise

    def _generate_slides_from_content(self, content: str) -> list:
        """
        从内容生成幻灯片结构
        
        Args:
            content: 文档内容
            
        Returns:
            幻灯片列表
        """
        slides = []
        
        # 简单处理：按段落分割
        paragraphs = content.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs[:8]):  # 最多8页
            if paragraph.strip():
                slides.append({
                    "type": "content",
                    "title": f"第 {i+1} 节",
                    "content": paragraph.strip()[:200]  # 限制长度
                })
        
        return slides

    def register_skill(self, skill_manager, skill_type: str = "pptx") -> bool:
        """
        在技能管理器中注册 anthropics 技能
        
        Args:
            skill_manager: 技能管理器实例
            skill_type: 技能类型（pptx, docx, xlsx, pdf）
            
        Returns:
            是否注册成功
        """
        try:
            skill_info = {
                "id": f"anthropics_{skill_type}",
                "name": f"PPT生成(Anthropics)",
                "description": f"使用 Anthropics {skill_type.upper()} 技能生成文档",
                "tool_name": f"anthropics_{skill_type}_generator",
                "parameters": {
                    "content": "string",
                    "title": "string",
                    "output_path": "string"
                },
                "created_by": "system",
                "version": "1.0.0"
            }
            
            # 检查技能是否已存在
            existing_skill = skill_manager.get_skill(skill_info["id"])
            if existing_skill:
                logger.info(f"技能 {skill_info['id']} 已存在，跳过注册")
                return True
            
            # 创建技能对象并保存
            from src.types import Skill
            
            skill = Skill(
                id=skill_info["id"],
                name=skill_info["name"],
                description=skill_info["description"],
                steps=[],
                triggers=[],
                parameters=skill_info["parameters"],
                created_by=skill_info["created_by"],
                version=skill_info["version"],
                is_active=True,
                is_preset=True,
                metadata={"source": "anthropics"}
            )
            
            skill_manager.save_skill(skill)
            logger.info(f"✅ 成功注册 anthropics {skill_type} 技能")
            return True
            
        except Exception as e:
            logger.error(f"❌ 注册 anthropics 技能失败: {str(e)}")
            return False


# 全局实例
anthropics_adapter = AnthropicsSkillAdapter()
