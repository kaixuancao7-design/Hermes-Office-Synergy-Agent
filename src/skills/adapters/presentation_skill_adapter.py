"""presentation-skill 适配器 - 将外部PPT生成技能转换为项目格式"""

import os
import json
import subprocess
from typing import Dict, Any, Optional, List
from src.logging_config import get_logger

logger = get_logger("presentation_skill_adapter")


class PresentationSkillAdapter:
    """
    presentation-skill 适配器类
    
    将 https://github.com/sirilsengolraj-source/presentation-skill 集成到项目中
    支持从大纲生成PPT、工作区模式、QA验证等功能
    """

    def __init__(self):
        """初始化适配器"""
        self.skill_path = None
        self._detect_skill_path()
        self._check_dependencies()

    def _detect_skill_path(self):
        """检测 presentation-skill 的安装路径"""
        # 检查常见安装位置
        possible_paths = [
            os.path.join(os.environ.get('CODEX_HOME', ''), 'skills', 'presentation-skill'),
            os.path.join(os.path.expanduser('~'), '.codex', 'skills', 'presentation-skill'),
            os.path.join(os.getcwd(), 'presentation-skill'),
            '/opt/presentation-skill'
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                self.skill_path = path
                logger.info(f"✅ 找到 presentation-skill: {path}")
                return
        
        logger.warning("⚠️ 未找到 presentation-skill，将使用本地实现")

    def _check_dependencies(self):
        """检查依赖是否安装"""
        # 检查 npm
        try:
            subprocess.run(['npm', '--version'], capture_output=True, check=True)
            logger.info("✅ npm 已安装")
        except:
            logger.warning("⚠️ npm 未安装，pptxgenjs 渲染器不可用")
        
        # 检查 python-pptx
        try:
            import pptx
            logger.info("✅ python-pptx 已安装")
        except ImportError:
            logger.warning("⚠️ python-pptx 未安装")

    def is_available(self) -> bool:
        """检查 presentation-skill 是否可用"""
        return self.skill_path is not None

    def generate_from_outline(self, content: str, title: str = "演示文稿", 
                              style_preset: str = "executive-clinical") -> str:
        """
        从内容生成PPT（通过 outline.json）
        
        Args:
            content: 文档内容
            title: PPT标题
            style_preset: 样式预设（executive-clinical, corporate, academic等）
        
        Returns:
            生成的PPT文件路径
        """
        if not self.is_available():
            logger.warning("presentation-skill 不可用，回退到本地实现")
            return self._fallback_generation(content, title)

        try:
            # 生成临时工作区
            workspace_dir = self._create_temp_workspace(title)
            
            # 生成 outline.json
            outline = self._content_to_outline(content, title)
            outline_path = os.path.join(workspace_dir, 'outline.json')
            with open(outline_path, 'w', encoding='utf-8') as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)
            
            # 构建PPT
            output_path = self._build_deck(workspace_dir, style_preset)
            
            logger.info(f"✅ presentation-skill PPT生成成功: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ presentation-skill 执行失败: {str(e)}")
            return self._fallback_generation(content, title)

    def _create_temp_workspace(self, title: str) -> str:
        """创建临时工作区目录"""
        import tempfile
        
        # 清理标题中的特殊字符
        safe_title = ''.join(c for c in title if c.isalnum() or c in ' -_').strip()
        workspace_dir = os.path.join(tempfile.gettempdir(), f"deck_{safe_title}")
        
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir

    def _content_to_outline(self, content: str, title: str) -> dict:
        """
        将文本内容转换为 outline.json 格式
        
        Args:
            content: 文档内容
            title: PPT标题
        
        Returns:
            outline.json 格式的字典
        """
        # 按段落分割内容
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        slides = []
        
        # 添加封面页
        slides.append({
            "variant": "title",
            "title": title,
            "subtitle": "自动生成的演示文稿"
        })
        
        # 添加内容页
        for i, paragraph in enumerate(paragraphs[:10]):  # 最多10页
            slides.append({
                "variant": "content",
                "title": f"第 {i+1} 节",
                "content": paragraph[:300]  # 限制长度
            })
        
        return {
            "title": title,
            "slides": slides
        }

    def _build_deck(self, workspace_dir: str, style_preset: str) -> str:
        """
        使用 presentation-skill 构建PPT
        
        Args:
            workspace_dir: 工作区目录（包含 outline.json）
            style_preset: 样式预设
        
        Returns:
            生成的PPT文件路径
        """
        # 使用 pptxgenjs 渲染器
        build_script = os.path.join(self.skill_path, 'scripts', 'build_deck_pptxgenjs.js')
        
        if not os.path.exists(build_script):
            logger.warning(f"pptxgenjs 脚本不存在: {build_script}")
            return self._build_with_python(workspace_dir, style_preset)
        
        output_path = os.path.join(workspace_dir, 'output.pptx')
        
        # 构建命令
        command = [
            'node', build_script,
            '--outline', os.path.join(workspace_dir, 'outline.json'),
            '--output', output_path,
            '--style-preset', style_preset
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            return output_path
        else:
            logger.error(f"pptxgenjs 构建失败: {result.stderr}")
            return self._build_with_python(workspace_dir, style_preset)

    def _build_with_python(self, workspace_dir: str, style_preset: str) -> str:
        """
        使用 python-pptx 回退构建
        
        Args:
            workspace_dir: 工作区目录
            style_preset: 样式预设
        
        Returns:
            生成的PPT文件路径
        """
        try:
            from src.tools.tool_executor import PPTGenerator
            
            # 读取 outline.json
            outline_path = os.path.join(workspace_dir, 'outline.json')
            with open(outline_path, 'r', encoding='utf-8') as f:
                outline = json.load(f)
            
            # 转换为内部格式
            slides = []
            for slide_data in outline.get('slides', []):
                slides.append({
                    "type": "content",
                    "title": slide_data.get('title', ''),
                    "content": slide_data.get('content', '')
                })
            
            # 使用本地生成器
            generator = PPTGenerator()
            output_path = generator.generate_ppt(
                title=outline.get('title', '演示文稿'),
                slides=slides
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"Python 回退构建失败: {str(e)}")
            raise

    def _fallback_generation(self, content: str, title: str) -> str:
        """
        完全回退到本地 PPT 生成实现
        
        Args:
            content: 文档内容
            title: PPT标题
        
        Returns:
            生成的PPT文件路径
        """
        from src.tools.tool_executor import PPTGenerator
        
        # 简单生成演示文稿
        slides = []
        
        # 按段落分割
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        # 添加封面页
        slides.append({
            "type": "title",
            "title": title,
            "content": ""
        })
        
        # 添加内容页
        for i, paragraph in enumerate(paragraphs[:8]):
            slides.append({
                "type": "content",
                "title": f"第 {i+1} 节",
                "content": paragraph[:200]
            })
        
        generator = PPTGenerator()
        output_path = generator.generate_ppt(title=title, slides=slides)
        
        logger.info(f"✅ 本地PPT生成成功: {output_path}")
        return output_path

    def register_skill(self, skill_manager) -> bool:
        """
        在技能管理器中注册 presentation-skill
        
        Args:
            skill_manager: 技能管理器实例
        
        Returns:
            是否注册成功
        """
        try:
            skill_info = {
                "id": "presentation_skill",
                "name": "PPT生成(Presentation Skill)",
                "description": "使用 presentation-skill 生成专业PPT演示文稿",
                "tool_name": "presentation_skill_generator",
                "parameters": {
                    "content": "string",
                    "title": "string",
                    "style_preset": "string"
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
                metadata={"source": "presentation-skill", "path": self.skill_path}
            )
            
            skill_manager.save_skill(skill)
            logger.info(f"✅ 成功注册 presentation-skill")
            return True
            
        except Exception as e:
            logger.error(f"❌ 注册 presentation-skill 失败: {str(e)}")
            return False


# 全局实例
presentation_skill_adapter = PresentationSkillAdapter()
