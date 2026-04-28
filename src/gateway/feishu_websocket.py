import asyncio
import json
import time
from typing import Dict, Any, Optional

from lark_oapi import LogLevel
from lark_oapi import Client as ApiClient
from lark_oapi.ws import Client as WsClient

from src.config import settings
from src.gateway.message_router import message_router
from src.types import Message
from src.utils import generate_id, get_timestamp, safe_log_string
from src.data.database import db
from src.logging_config import get_logger

logger = get_logger("gateway")

class FeishuEventHandler:
    """飞书事件处理器"""
    
    def __init__(self):
        self.processing_message_ids = set()  # 正在处理中的消息ID（内存中，用于防止并发）
        self.last_message_time = {}  # 每个用户的最后消息时间
        self.MESSAGE_INTERVAL = 1  # 同一用户消息最小间隔（秒）
    
    def do_without_validation(self, payload: bytes) -> Any:
        """处理事件（不验证签名）"""
        try:
            payload_str = payload.decode('utf-8')
            
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
        """处理消息事件 - 使用异步模式避免飞书重试"""
        try:
            message = event_data.get('event', {}).get('message', {})
            sender = event_data.get('event', {}).get('sender', {})
            
            # 1. 检查发送者类型，忽略机器人自己发送的消息
            sender_type = sender.get('sender_type', '')
            if sender_type == 'app':
                logger.debug("忽略机器人自己发送的消息")
                return
            
            # 2. 获取消息ID（必须有ID才能去重）
            message_id = message.get('message_id')
            if not message_id:
                logger.warning("消息没有 message_id，跳过处理")
                return
            
            # 3. 检查消息是否正在处理中（防止并发处理）
            if message_id in self.processing_message_ids:
                logger.info(f"消息正在处理中，跳过: {message_id}")
                return
            
            # 4. 检查消息是否已处理过（使用数据库持久化去重，服务重启后仍有效）
            if db.is_message_processed(message_id):
                logger.info(f"忽略重复消息(数据库): {message_id}")
                return
            
            # 5. 获取用户ID
            user_id = sender.get('sender_id', {}).get('user_id', 'unknown')
            
            # 6. 检查用户消息频率（防止刷屏）
            current_time = time.time()
            last_time = self.last_message_time.get(user_id, 0)
            if current_time - last_time < self.MESSAGE_INTERVAL:
                logger.info(f"用户 {user_id} 消息过于频繁，跳过")
                return
            self.last_message_time[user_id] = current_time
            
            # 7. 立即标记消息为已处理（写入数据库，防止服务重启后重复处理）
            db.mark_message_processed(message_id, user_id, source="feishu")
            
            # 8. 标记消息为处理中（内存中，用于并发控制）
            self.processing_message_ids.add(message_id)
            
            # 9. 提取消息内容用于异步处理
            content = message.get('content', '{}')
            chat_type = message.get('chat_type', 'p2p')
            
            # 10. 异步处理消息（立即返回，避免飞书超时重试）
            asyncio.create_task(
                self._process_message_async(
                    message_id=message_id,
                    user_id=user_id,
                    content=content,
                    chat_type=chat_type
                )
            )
            
            # 设置请求上下文（用于日志追踪）
            from src.logging_config import set_request_context
            set_request_context(request_id=message_id, user_id=user_id)
            
            logger.info(f"[REQUEST_START] 消息已接收并进入异步处理: message_id={message_id}, user_id={user_id}")

        except Exception as e:
            # 清理处理中状态
            message_id = message.get('message_id')
            if message_id:
                self.processing_message_ids.discard(message_id)
            logger.error(f"消息事件处理失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    async def _process_message_async(self, message_id: str, user_id: str, content: str, chat_type: str):
        """异步处理消息 - 在后台执行，不阻塞事件循环"""
        try:
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
            
            logger.info(f"开始处理消息: user_id={user_id}, message_id={message_id}, content={text[:50]}")
            
            # 构建元数据（包含关键的文件下载参数）
            metadata = {
                "source": "feishu",
                "group": chat_type == "group",
                "message_id": message_id,
                "user_id": user_id
            }
            
            # 如果是文件消息，提取 file_key 和 file_name
            if isinstance(content_json, dict):
                if content_json.get('file_key'):
                    metadata['file_key'] = content_json['file_key']
                if content_json.get('file_name'):
                    metadata['file_name'] = content_json['file_name']
                if content_json.get('file_url'):
                    metadata['file_url'] = content_json['file_url']
            
            logger.debug(f"构建的元数据: {metadata}")
            
            # 创建消息对象
            msg = Message(
                id=str(message_id),
                user_id=str(user_id),
                content=text,
                role="user",
                timestamp=get_timestamp(),
                metadata=metadata
            )
            
            # 使用消息路由处理
            response = message_router.route(msg)
            # 使用 safe_log_string 避免 emoji 编码问题
            logger.info(f"生成响应: {safe_log_string(response[:50])}")
            
            # 发送回复
            FeishuWebSocketService._send_message_static(user_id, response)
            
        except Exception as e:
            logger.error(f"异步消息处理失败: message_id={message_id}, error={str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
        finally:
            # 清理处理中状态
            self.processing_message_ids.discard(message_id)
            
            # 清理请求上下文
            from src.logging_config import clear_request_context
            clear_request_context()
            
            logger.info(f"[REQUEST_END] 消息处理完成: message_id={message_id}")
            
            # 限制处理中消息ID的数量（内存保护）
            if len(self.processing_message_ids) > 100:
                self.processing_message_ids = set(list(self.processing_message_ids)[-50:])

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