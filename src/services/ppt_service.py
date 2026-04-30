"""PPT服务 - 整合PPT生成和IM发送功能"""

from typing import Dict, Any, List, Optional
from src.tools.ppt_generator import PPTGeneratorBase as PPTGenerator
from src.plugins import get_im_adapter
from src.utils import generate_id
from src.logging_config import get_logger
from src.services.template_matcher import template_matcher, TemplateMatch
import os

logger = get_logger("services")


class PPTService:
    """PPT服务类"""
    
    def __init__(self):
        self.ppt_generator = PPTGenerator()
    
    async def generate_and_send_ppt(
        self,
        user_id: str,
        title: str,
        slides: List[Dict[str, Any]],
        im_adapter_type: str = "feishu",
        message_before: str = "",
        message_after: str = ""
    ) -> Dict[str, Any]:
        """
        生成PPT并通过IM发送给用户
        
        Args:
            user_id: 用户ID
            title: PPT标题
            slides: 幻灯片列表
            im_adapter_type: IM适配器类型（feishu, dingtalk, wecom等）
            message_before: 发送文件前的消息
            message_after: 发送文件后的消息
        
        Returns:
            结果字典，包含success, message, file_path等
        """
        result = {
            "success": False,
            "message": "",
            "file_path": None,
            "sent": False
        }
        
        try:
            # 生成PPT
            logger.info(f"开始生成PPT: user_id={user_id}, title={title}")
            file_path = self.ppt_generator.generate_ppt(title, slides)
            result["file_path"] = file_path
            logger.info(f"PPT生成成功: {file_path}")
            
            # 获取IM适配器
            adapter = get_im_adapter(im_adapter_type)
            if not adapter:
                result["message"] = f"未找到IM适配器: {im_adapter_type}"
                logger.error(result["message"])
                return result
            
            # 发送前置消息
            if message_before:
                await adapter.send_message(user_id, message_before)
                logger.info(f"发送前置消息成功: user_id={user_id}")
            
            # 发送PPT文件
            file_name = os.path.basename(file_path)
            send_success = await adapter.send_file(user_id, file_path, file_name)
            
            if send_success:
                result["sent"] = True
                result["success"] = True
                result["message"] = f"PPT已发送给用户: {file_name}"
                logger.info(result["message"])
            else:
                result["message"] = "PPT生成成功，但发送失败"
                logger.error(result["message"])
            
            # 发送后置消息
            if message_after and send_success:
                await adapter.send_message(user_id, message_after)
                logger.info(f"发送后置消息成功: user_id={user_id}")
            
        except Exception as e:
            result["message"] = f"处理失败: {str(e)}"
            logger.error(f"PPT生成发送失败: {str(e)}", exc_info=True)
        
        return result
    
    async def generate_from_outline_and_send(
        self,
        user_id: str,
        title: str,
        outline: List[Dict[str, Any]],
        im_adapter_type: str = "feishu",
        message_before: str = "",
        message_after: str = ""
    ) -> Dict[str, Any]:
        """
        从大纲生成PPT并发送
        
        Args:
            user_id: 用户ID
            title: PPT标题
            outline: 大纲结构
            im_adapter_type: IM适配器类型
            message_before: 发送前消息
            message_after: 发送后消息
        
        Returns:
            结果字典
        """
        result = {
            "success": False,
            "message": "",
            "file_path": None,
            "sent": False
        }
        
        try:
            # 从大纲生成PPT
            logger.info(f"从大纲生成PPT: user_id={user_id}, title={title}")
            file_path = self.ppt_generator.generate_from_outline(title, outline)
            result["file_path"] = file_path
            logger.info(f"PPT生成成功: {file_path}")
            
            # 获取IM适配器
            adapter = get_im_adapter(im_adapter_type)
            if not adapter:
                result["message"] = f"未找到IM适配器: {im_adapter_type}"
                logger.error(result["message"])
                return result
            
            # 发送前置消息
            if message_before:
                await adapter.send_message(user_id, message_before)
            
            # 发送文件
            file_name = os.path.basename(file_path)
            send_success = await adapter.send_file(user_id, file_path, file_name)
            
            if send_success:
                result["sent"] = True
                result["success"] = True
                result["message"] = f"PPT已发送给用户: {file_name}"
                logger.info(result["message"])
                
                # 发送后置消息
                if message_after:
                    await adapter.send_message(user_id, message_after)
            else:
                result["message"] = "PPT生成成功，但发送失败"
                logger.error(result["message"])
            
        except Exception as e:
            result["message"] = f"处理失败: {str(e)}"
            logger.error(f"PPT生成发送失败: {str(e)}", exc_info=True)
        
        return result
    
    def generate_ppt_only(
        self,
        title: str,
        slides: List[Dict[str, Any]]
    ) -> str:
        """
        仅生成PPT（不发送）

        Args:
            title: PPT标题
            slides: 幻灯片列表

        Returns:
            生成的文件路径
        """
        return self.ppt_generator.generate_ppt(title, slides)

    async def generate_with_template_match(
        self,
        user_id: str,
        content: str,
        title: str = None,
        slides: List[Dict[str, Any]] = None,
        style_hint: str = None,
        im_adapter_type: str = "feishu",
        message_before: str = "",
        message_after: str = ""
    ) -> Dict[str, Any]:
        """
        模板匹配生成PPT - 根据内容自动匹配模板后生成

        Args:
            user_id: 用户ID
            content: 用户内容/描述（用于匹配模板）
            title: PPT标题（可选，从content提取）
            slides: 幻灯片列表（可选）
            style_hint: 风格提示
            im_adapter_type: IM适配器类型
            message_before: 发送前消息
            message_after: 发送后消息

        Returns:
            结果字典，包含success, message, file_path, matched_template等
        """
        result = {
            "success": False,
            "message": "",
            "file_path": None,
            "sent": False,
            "matched_template": None,
            "template_recommendations": []
        }

        try:
            matches = template_matcher.match_layout(content, style_hint)

            if not matches:
                logger.warning("未找到匹配的模板，使用默认样式")
                result["template_recommendations"] = []
            else:
                result["template_recommendations"] = [
                    {"id": m.template_id, "name": m.name, "score": m.score}
                    for m in matches
                ]
                best_match = matches[0]
                result["matched_template"] = best_match.template_id
                logger.info(f"模板匹配成功: {best_match.name}, score={best_match.score}")

            if slides is None:
                slides = self._generate_slides_from_content(content, title)

            if title is None:
                title = self._extract_title_from_content(content)

            styled_slides = []
            if result["matched_template"]:
                styled_slides = template_matcher.apply_template_style(
                    result["matched_template"], slides
                )
            else:
                styled_slides = slides

            logger.info(f"开始生成PPT: user_id={user_id}, title={title}")
            file_path = self.ppt_generator.generate_ppt(title, styled_slides)
            result["file_path"] = file_path
            logger.info(f"PPT生成成功: {file_path}")

            adapter = get_im_adapter(im_adapter_type)
            if not adapter:
                result["message"] = f"未找到IM适配器: {im_adapter_type}"
                logger.error(result["message"])
                return result

            if message_before:
                await adapter.send_message(user_id, message_before)

            file_name = os.path.basename(file_path)
            send_success = await adapter.send_file(user_id, file_path, file_name)

            if send_success:
                result["sent"] = True
                result["success"] = True
                result["message"] = f"PPT已发送给用户: {file_name}"
                logger.info(result["message"])
            else:
                result["message"] = "PPT生成成功，但发送失败"

            if message_after and send_success:
                await adapter.send_message(user_id, message_after)

        except Exception as e:
            result["message"] = f"处理失败: {str(e)}"
            logger.error(f"模板匹配PPT生成失败: {str(e)}", exc_info=True)

        return result

    def _generate_slides_from_content(self, content: str, title: str = None) -> List[Dict[str, Any]]:
        """从内容生成幻灯片结构"""
        slides = []
        title = title or "PPT演示"

        slides.append({
            "type": "title",
            "title": title,
            "content": ""
        })

        sections = content.split("\n\n")
        for i, section in enumerate(sections[:8]):
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            slide_title = lines[0][:50] if lines else f"第{i+1}页"

            slides.append({
                "type": "content",
                "title": slide_title,
                "content": "\n".join(lines[1:]) if len(lines) > 1 else section
            })

        slides.append({
            "type": "closing",
            "title": "谢谢",
            "content": ""
        })

        return slides

    def _extract_title_from_content(self, content: str) -> str:
        """从内容中提取标题"""
        lines = content.strip().split("\n")
        first_line = lines[0] if lines else "PPT演示"

        if len(first_line) > 50:
            first_line = first_line[:47] + "..."

        return first_line


# 单例实例
ppt_service = PPTService()
