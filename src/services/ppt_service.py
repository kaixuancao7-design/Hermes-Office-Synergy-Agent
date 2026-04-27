"""PPT服务 - 整合PPT生成和IM发送功能"""

from typing import Dict, Any, List, Optional
from src.tools.ppt_generator import PPTGeneratorBase as PPTGenerator
from src.plugins import get_im_adapter
from src.utils import generate_id
from src.logging_config import get_logger
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


# 单例实例
ppt_service = PPTService()
