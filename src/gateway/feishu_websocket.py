import asyncio
import json
import logging
from typing import Dict, Any, Optional

from lark_oapi import LogLevel
from lark_oapi import Client as ApiClient
from lark_oapi.ws import Client as WsClient

from src.config import settings
from src.gateway.message_router import message_router
from src.types import Message
from src.utils import generate_id, get_timestamp

logger = logging.getLogger("hermes_office_agent")

class FeishuEventHandler:
    """飞书事件处理器"""
    
    def do_without_validation(self, payload: bytes) -> Any:
        """处理事件（不验证签名）"""
        try:
            payload_str = payload.decode('utf-8')
            logger.info(f"收到飞书事件 payload: {payload_str[:200]}")
            
            # 解析事件
            event_data = json.loads(payload_str)
            
            # 获取事件类型
            event_type = event_data.get('header', {}).get('event_type', '')
            
            if event_type == 'im.message.receive_v1':
                self._handle_message_event(event_data)
            
        except Exception as e:
            logger.error(f"事件处理失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
        
        return None
    
    def _handle_message_event(self, event_data: Dict):
        """处理消息事件"""
        try:
            message = event_data.get('event', {}).get('message', {})
            sender = event_data.get('event', {}).get('sender', {})
            
            message_id = message.get('message_id', generate_id())
            user_id = sender.get('sender_id', {}).get('user_id', 'unknown')
            
            # 解析消息内容
            content = message.get('content', '{}')
            chat_type = message.get('chat_type', 'p2p')
            
            # 解析内容
            try:
                content_json = json.loads(content)
                text = content_json.get('text', content)
            except:
                text = content
            
            # 去除 @提及
            bot_name = settings.FEISHU_BOT_NAME
            if bot_name and f"@{bot_name}" in text:
                text = text.replace(f"@{bot_name}", "").strip()
            
            logger.info(f"收到消息: user_id={user_id}, content={text[:50]}")
            
            # 创建消息对象
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
            
            # 使用消息路由处理
            response = message_router.route(msg)
            logger.info(f"生成响应: {response[:50]}")
            
            # 发送回复
            FeishuWebSocketService._send_message_static(user_id, response)
            
        except Exception as e:
            logger.error(f"消息事件处理失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

class FeishuWebSocketService:
    _api_client = None
    
    def __init__(self):
        self.ws_client = None
        self.is_running = False
        self.event_handler = FeishuEventHandler()
        
    @staticmethod
    def _send_message_static(user_id: str, content: str) -> bool:
        """发送消息到飞书用户（静态方法）"""
        if FeishuWebSocketService._api_client is None:
            logger.error("飞书 API 客户端未初始化")
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
            
            response = FeishuWebSocketService._api_client.im.v1.message.create(request)
            
            if response.success():
                logger.info(f"消息发送成功: user_id={user_id}")
                return True
            else:
                logger.error(f"消息发送失败: {response.code}, {response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"发送消息异常: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def initialize(self):
        """初始化飞书 WebSocket 客户端"""
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.error("飞书配置未完成：FEISHU_APP_ID 或 FEISHU_APP_SECRET 为空")
            return False
            
        logger.info("初始化飞书 WebSocket 客户端...")
        
        try:
            # 创建 API 客户端（用于发送消息）
            FeishuWebSocketService._api_client = ApiClient.builder() \
                .app_id(settings.FEISHU_APP_ID) \
                .app_secret(settings.FEISHU_APP_SECRET) \
                .build()
            
            # 创建 WebSocket 客户端（用于接收事件）
            self.ws_client = WsClient(
                app_id=settings.FEISHU_APP_ID,
                app_secret=settings.FEISHU_APP_SECRET,
                log_level=LogLevel.INFO,
                event_handler=self.event_handler,
                domain="https://open.feishu.cn",
                auto_reconnect=True
            )
            
            logger.info("飞书 WebSocket 客户端初始化成功")
            return True
        except Exception as e:
            logger.error(f"飞书客户端初始化失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    async def start(self):
        """启动 WebSocket 服务"""
        if not self.initialize():
            return False
            
        self.is_running = True
        
        logger.info("启动飞书 WebSocket 长连接服务...")
        
        try:
            # 使用线程运行同步的 start 方法
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.ws_client.start)
        except Exception as e:
            logger.error(f"WebSocket 服务启动失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            self.is_running = False
            return False
            
        return True
    
    def stop(self):
        """停止 WebSocket 服务"""
        self.is_running = False
        logger.info("飞书 WebSocket 长连接服务已停止")

# 全局实例
feishu_websocket_service = FeishuWebSocketService()