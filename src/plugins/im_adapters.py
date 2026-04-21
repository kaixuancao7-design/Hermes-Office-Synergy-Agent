"""IM适配器插件实现"""
import asyncio
import json
import time
from typing import Dict, Any, Optional
from abc import ABC

from src.plugins.base import IMAdapterBase
from src.config import settings
from src.utils import generate_id, get_timestamp, safe_log_string
from src.data.database import db
from src.logging_config import get_logger

logger = get_logger("im")


class FeishuAdapter(IMAdapterBase):
    """飞书IM适配器"""
    
    def __init__(self):
        self.processing_message_ids = set()
        self.last_message_time = {}
        self.MESSAGE_INTERVAL = 1
        self._api_client = None
        self.ws_client = None
        self.is_running = False
    
    async def start(self) -> bool:
        """启动飞书适配器"""
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.error("飞书配置未完成")
            return False
        
        try:
            from lark_oapi import LogLevel
            from lark_oapi import Client as ApiClient
            from lark_oapi.ws import Client as WsClient
            
            self._api_client = ApiClient.builder() \
                .app_id(settings.FEISHU_APP_ID) \
                .app_secret(settings.FEISHU_APP_SECRET) \
                .build()
            
            self.ws_client = WsClient(
                app_id=settings.FEISHU_APP_ID,
                app_secret=settings.FEISHU_APP_SECRET,
                log_level=LogLevel.INFO,
                event_handler=self,
                domain="https://open.feishu.cn",
                auto_reconnect=True
            )
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.ws_client.start)
            self.is_running = True
            logger.info("飞书适配器启动成功")
            return True
        except Exception as e:
            logger.error(f"飞书适配器启动失败: {str(e)}")
            return False
    
    async def stop(self) -> bool:
        """停止飞书适配器"""
        self.is_running = False
        logger.info("飞书适配器已停止")
        return True
    
    async def send_message(self, user_id: str, content: str) -> bool:
        """发送消息到飞书"""
        if self._api_client is None:
            logger.error("飞书API客户端未初始化")
            return False
        
        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
            
            request = CreateMessageRequest.builder() \
                .receive_id_type("user_id") \
                .request_body(CreateMessageRequestBody.builder() \
                    .receive_id(user_id) \
                    .content(json.dumps({"text": content})) \
                    .msg_type("text") \
                    .build()) \
                .build()
            
            response = self._api_client.im.v1.message.create(request)
            if response.success():
                logger.info(f"飞书消息发送成功: user_id={user_id}")
                return True
            else:
                logger.error(f"飞书消息发送失败: {response.code}, {response.msg}")
                return False
        except Exception as e:
            logger.error(f"发送飞书消息异常: {str(e)}")
            return False
    
    def get_adapter_type(self) -> str:
        return "feishu"
    
    # 飞书事件处理器接口
    def do_without_validation(self, payload: bytes) -> Any:
        try:
            payload_str = payload.decode('utf-8')
            event_data = json.loads(payload_str)
            event_type = event_data.get('header', {}).get('event_type', '')
            
            if event_type == 'im.message.receive_v1':
                asyncio.create_task(self._handle_message_event(event_data))
        except Exception as e:
            logger.error(f"飞书事件处理失败: {str(e)}")
        
        return None
    
    async def _handle_message_event(self, event_data: Dict):
        try:
            message = event_data.get('event', {}).get('message', {})
            sender = event_data.get('event', {}).get('sender', {})
            
            sender_type = sender.get('sender_type', '')
            if sender_type == 'app':
                return
            
            message_id = message.get('message_id')
            if not message_id:
                return
            
            if message_id in self.processing_message_ids:
                return
            
            if db.is_message_processed(message_id):
                return
            
            user_id = sender.get('sender_id', {}).get('user_id', 'unknown')
            
            current_time = time.time()
            last_time = self.last_message_time.get(user_id, 0)
            if current_time - last_time < self.MESSAGE_INTERVAL:
                return
            self.last_message_time[user_id] = current_time
            
            db.mark_message_processed(message_id, user_id, source="feishu")
            self.processing_message_ids.add(message_id)
            
            content = message.get('content', '{}')
            chat_type = message.get('chat_type', 'p2p')
            
            await self._process_message_async(message_id, user_id, content, chat_type)
        except Exception as e:
            message_id = message.get('message_id')
            if message_id:
                self.processing_message_ids.discard(message_id)
            logger.error(f"消息事件处理失败: {str(e)}")
    
    async def _process_message_async(self, message_id: str, user_id: str, content: str, chat_type: str):
        try:
            from src.gateway.message_router import message_router
            from src.types import Message
            
            try:
                content_json = json.loads(content)
                text = content_json.get('text', content)
            except:
                text = content
            
            bot_name = settings.FEISHU_BOT_NAME
            if bot_name and f"@{bot_name}" in text:
                text = text.replace(f"@{bot_name}", "").strip()
            
            msg = Message(
                id=str(message_id),
                user_id=str(user_id),
                content=text,
                role="user",
                timestamp=get_timestamp(),
                metadata={
                    "source": "feishu",
                    "group": chat_type == "group"
                }
            )
            
            response = message_router.route(msg)
            await self.send_message(user_id, response)
        except Exception as e:
            logger.error(f"异步消息处理失败: {str(e)}")
        finally:
            self.processing_message_ids.discard(message_id)


class DingTalkAdapter(IMAdapterBase):
    """钉钉IM适配器"""
    
    def __init__(self):
        self.is_running = False
    
    async def start(self) -> bool:
        logger.info("钉钉适配器启动")
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        logger.info("钉钉适配器已停止")
        return True
    
    async def send_message(self, user_id: str, content: str) -> bool:
        logger.info(f"发送钉钉消息: user_id={user_id}, content={content[:50]}")
        return True
    
    def get_adapter_type(self) -> str:
        return "dingtalk"


class WeComAdapter(IMAdapterBase):
    """企业微信IM适配器"""
    
    def __init__(self):
        self.is_running = False
    
    async def start(self) -> bool:
        logger.info("企业微信适配器启动")
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        logger.info("企业微信适配器已停止")
        return True
    
    async def send_message(self, user_id: str, content: str) -> bool:
        logger.info(f"发送企业微信消息: user_id={user_id}, content={content[:50]}")
        return True
    
    def get_adapter_type(self) -> str:
        return "wecom"


class SlackAdapter(IMAdapterBase):
    """Slack适配器"""
    
    def __init__(self):
        self.is_running = False
    
    async def start(self) -> bool:
        logger.info("Slack适配器启动")
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        logger.info("Slack适配器已停止")
        return True
    
    async def send_message(self, user_id: str, content: str) -> bool:
        logger.info(f"发送Slack消息: user_id={user_id}, content={content[:50]}")
        return True
    
    def get_adapter_type(self) -> str:
        return "slack"


class DiscordAdapter(IMAdapterBase):
    """Discord适配器"""
    
    def __init__(self):
        self.is_running = False
    
    async def start(self) -> bool:
        logger.info("Discord适配器启动")
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        logger.info("Discord适配器已停止")
        return True
    
    async def send_message(self, user_id: str, content: str) -> bool:
        logger.info(f"发送Discord消息: user_id={user_id}, content={content[:50]}")
        return True
    
    def get_adapter_type(self) -> str:
        return "discord"


# 适配器注册表
IM_ADAPTER_REGISTRY = {
    "feishu": FeishuAdapter,
    "dingtalk": DingTalkAdapter,
    "wecom": WeComAdapter,
    "slack": SlackAdapter,
    "discord": DiscordAdapter
}
