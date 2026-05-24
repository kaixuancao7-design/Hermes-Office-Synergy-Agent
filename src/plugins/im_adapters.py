"""IM适配器插件实现"""
from typing import Dict, Any, Optional, List
from src.plugins.base import IMAdapterBase
from src.types import Message, Session, Intent
from src.config import settings
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("im")


class FeishuAdapter(IMAdapterBase):
    """飞书IM适配器"""
    
    def __init__(self):
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self.verification_token = settings.FEISHU_VERIFICATION_TOKEN
    
    async def start(self) -> bool:
        """启动适配器"""
        logger.info("飞书适配器启动")
        return True
    
    async def stop(self) -> bool:
        """停止适配器"""
        logger.info("飞书适配器停止")
        return True
    
    def send_message(self, user_id: str, content: str, metadata: dict = None) -> bool:
        """发送消息到飞书"""
        try:
            logger.info(f"发送消息到飞书: user_id={user_id}, content_length={len(content)}")
            # 简化实现：实际应该调用飞书API
            return True
        except Exception as e:
            logger.error(f"发送飞书消息失败: {str(e)}")
            return False
    
    def receive_message(self, raw_message: dict) -> Optional[Message]:
        """解析飞书消息"""
        try:
            # 飞书消息结构解析
            event = raw_message.get("event", {})
            message = event.get("message", {})
            
            return Message(
                id=message.get("message_id", generate_id()),
                user_id=message.get("sender", {}).get("sender_id", {}).get("user_id", "unknown"),
                content=self._parse_content(message.get("content", "{}")),
                role="user",
                timestamp=message.get("create_time", get_timestamp()),
                metadata={
                    "message_type": message.get("message_type"),
                    "chat_type": event.get("chat_type"),
                    "chat_id": event.get("chat_id"),
                    "group": event.get("chat_type") == "group",
                    "group_id": event.get("chat_id"),
                    "group_name": event.get("chat_name"),
                    "file_key": self._extract_file_key(message),
                    "file_name": self._extract_file_name(message)
                }
            )
        except Exception as e:
            logger.error(f"解析飞书消息失败: {str(e)}")
            return None
    
    def _parse_content(self, content_str: str) -> str:
        """解析消息内容"""
        try:
            import json
            content = json.loads(content_str)
            return content.get("text", content_str)
        except:
            return content_str
    
    def _extract_file_key(self, message: dict) -> Optional[str]:
        """提取文件key"""
        message_type = message.get("message_type")
        if message_type == "file":
            content = message.get("content", "{}")
            try:
                import json
                data = json.loads(content)
                return data.get("file_key")
            except:
                pass
        return None
    
    def _extract_file_name(self, message: dict) -> Optional[str]:
        """提取文件名"""
        message_type = message.get("message_type")
        if message_type == "file":
            content = message.get("content", "{}")
            try:
                import json
                data = json.loads(content)
                return data.get("file_name")
            except:
                pass
        return None
    
    def get_adapter_type(self) -> str:
        return "feishu"


class WeChatAdapter(IMAdapterBase):
    """微信IM适配器"""
    
    def __init__(self):
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
    
    async def start(self) -> bool:
        """启动适配器"""
        logger.info("微信适配器启动")
        return True
    
    async def stop(self) -> bool:
        """停止适配器"""
        logger.info("微信适配器停止")
        return True
    
    def send_message(self, user_id: str, content: str, metadata: dict = None) -> bool:
        """发送消息到微信"""
        try:
            logger.info(f"发送消息到微信: user_id={user_id}, content_length={len(content)}")
            return True
        except Exception as e:
            logger.error(f"发送微信消息失败: {str(e)}")
            return False
    
    def receive_message(self, raw_message: dict) -> Optional[Message]:
        """解析微信消息"""
        try:
            return Message(
                id=raw_message.get("MsgId", generate_id()),
                user_id=raw_message.get("FromUserName", "unknown"),
                content=raw_message.get("Content", ""),
                role="user",
                timestamp=get_timestamp(),
                metadata={
                    "message_type": raw_message.get("MsgType"),
                    "to_user_name": raw_message.get("ToUserName"),
                    "create_time": raw_message.get("CreateTime")
                }
            )
        except Exception as e:
            logger.error(f"解析微信消息失败: {str(e)}")
            return None
    
    def get_adapter_type(self) -> str:
        return "wechat"


class ConsoleAdapter(IMAdapterBase):
    """控制台适配器（用于测试）"""
    
    def __init__(self):
        pass
    
    async def start(self) -> bool:
        """启动适配器"""
        logger.info("控制台适配器启动")
        return True
    
    async def stop(self) -> bool:
        """停止适配器"""
        logger.info("控制台适配器停止")
        return True
    
    def send_message(self, user_id: str, content: str, metadata: dict = None) -> bool:
        """打印消息到控制台"""
        print(f"[Console Output] [{user_id}] {content}")
        return True
    
    def receive_message(self, raw_message: dict) -> Optional[Message]:
        """解析控制台消息"""
        try:
            return Message(
                id=raw_message.get("id", generate_id()),
                user_id=raw_message.get("user_id", "console_user"),
                content=raw_message.get("content", ""),
                role="user",
                timestamp=raw_message.get("timestamp", get_timestamp()),
                metadata=raw_message.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"解析控制台消息失败: {str(e)}")
            return None
    
    def get_adapter_type(self) -> str:
        return "console"


# IM适配器注册表
IM_ADAPTER_REGISTRY = {
    "feishu": FeishuAdapter,
    "wechat": WeChatAdapter,
    "console": ConsoleAdapter
}
