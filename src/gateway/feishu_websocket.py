import asyncio
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

from lark_oapi import LogLevel
from lark_oapi import Client as ApiClient
from lark_oapi.ws import Client as WsClient

from src.config import settings
from src.gateway.message_router import message_router
from src.types import Message
from src.utils import generate_id, get_timestamp, safe_log_string
from src.data.database import db
from src.logging_config import get_logger, set_request_context, clear_request_context, log_event

logger = get_logger("gateway")


class FeishuEventHandler:
    """飞书事件处理器"""
    
    def __init__(self):
        self.processing_message_ids = set()  # 正在处理中的消息ID（内存中，用于防止并发）
        self.last_message_time = {}  # 每个用户的最后消息时间
        self.MESSAGE_INTERVAL = 1  # 同一用户消息最小间隔（秒）
        self.message_count = 0  # 消息计数
        self.error_count = 0  # 错误计数
        logger.info("[INIT] FeishuEventHandler 初始化完成")
    
    def do_without_validation(self, payload: bytes) -> Any:
        """处理事件（不验证签名）"""
        start_time = datetime.now()
        
        try:
            payload_str = payload.decode('utf-8')
            payload_len = len(payload_str)
            
            # 解析事件
            event_data = json.loads(payload_str)
            
            # 获取事件类型
            event_type = event_data.get('header', {}).get('event_type', '')
            event_id = event_data.get('header', {}).get('event_id', '')
            
            logger.debug(f"[EVENT_RECEIVE] 收到事件 | event_type={event_type} | event_id={event_id} | payload_len={payload_len}")
            
            if event_type == 'im.message.receive_v1':
                self._handle_message_event(event_data)
            elif event_type:
                logger.debug(f"[EVENT_IGNORE] 忽略未知事件类型 | event_type={event_type}")
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_event(logger, "feishu_event_received",
                     event_id=event_id,
                     elapsed_ms=elapsed_ms)
            
        except Exception as e:
            self.error_count += 1
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[EVENT_ERROR] 事件处理失败 | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "feishu_event_error",
                     error=str(e),
                     elapsed_ms=elapsed_ms)
        
        return None
    
    def _handle_message_event(self, event_data: Dict):
        """处理消息事件 - 使用异步模式避免飞书重试"""
        try:
            message = event_data.get('event', {}).get('message', {})
            sender = event_data.get('event', {}).get('sender', {})
            
            # 1. 检查发送者类型，忽略机器人自己发送的消息
            sender_type = sender.get('sender_type', '')
            if sender_type == 'app':
                logger.debug("[MESSAGE_FILTER] 忽略机器人自己发送的消息")
                return
            
            # 2. 获取消息ID（必须有ID才能去重）
            message_id = message.get('message_id')
            if not message_id:
                logger.warning("[MESSAGE_ERROR] 消息没有 message_id，跳过处理")
                return
            
            # 3. 检查消息是否正在处理中（防止并发处理）
            if message_id in self.processing_message_ids:
                logger.info(f"[MESSAGE_DUPLICATE] 消息正在处理中，跳过 | message_id={message_id}")
                return
            
            # 4. 检查消息是否已处理过（使用数据库持久化去重）
            if db.is_message_processed(message_id):
                logger.info(f"[MESSAGE_DUPLICATE] 忽略重复消息(数据库) | message_id={message_id}")
                return
            
            # 5. 获取用户ID
            user_id = sender.get('sender_id', {}).get('user_id', 'unknown')
            
            # 6. 检查用户消息频率（防止刷屏）
            current_time = time.time()
            last_time = self.last_message_time.get(user_id, 0)
            if current_time - last_time < self.MESSAGE_INTERVAL:
                logger.warning(f"[MESSAGE_RATE_LIMIT] 用户消息过于频繁 | user_id={user_id} | interval={current_time - last_time:.2f}s")
                return
            self.last_message_time[user_id] = current_time
            
            # 7. 立即标记消息为已处理（写入数据库）
            db.mark_message_processed(message_id, user_id, source="feishu")
            
            # 8. 标记消息为处理中（内存中，用于并发控制）
            self.processing_message_ids.add(message_id)
            
            # 9. 提取消息内容用于异步处理
            content = message.get('content', '{}')
            chat_type = message.get('chat_type', 'p2p')
            
            # 10. 异步处理消息
            asyncio.create_task(
                self._process_message_async(
                    message_id=message_id,
                    user_id=user_id,
                    content=content,
                    chat_type=chat_type
                )
            )
            
            # 设置请求上下文（用于日志追踪）
            set_request_context(request_id=message_id, user_id=user_id)
            
            self.message_count += 1
            logger.info(f"[REQUEST_START] 消息已接收并进入异步处理 | message_id={message_id} | user_id={user_id} | total_received={self.message_count}")

        except Exception as e:
            # 清理处理中状态
            message_id = message.get('message_id')
            if message_id:
                self.processing_message_ids.discard(message_id)
            
            self.error_count += 1
            logger.error(f"[MESSAGE_EVENT_ERROR] 消息事件处理失败 | message_id={message_id} | error={str(e)}", exc_info=True)
    
    async def _process_message_async(self, message_id: str, user_id: str, content: str, chat_type: str):
        """异步处理消息 - 在后台执行，不阻塞事件循环"""
        start_time = datetime.now()
        
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
            
            text_preview = text[:50] if len(text) > 50 else text
            logger.info(f"[MESSAGE_PROCESS] 开始处理消息 | message_id={message_id} | user_id={user_id} | content={text_preview}")
            
            # 构建元数据
            metadata = {
                "source": "feishu",
                "group": chat_type == "group",
                "message_id": message_id,
                "user_id": user_id
            }
            
            # 如果是文件消息，提取文件信息
            if isinstance(content_json, dict):
                if content_json.get('file_key'):
                    metadata['file_key'] = content_json['file_key']
                    logger.debug(f"[FILE_UPLOAD] 检测到文件上传 | file_key={content_json['file_key']}")
                if content_json.get('file_name'):
                    metadata['file_name'] = content_json['file_name']
                if content_json.get('file_url'):
                    metadata['file_url'] = content_json['file_url']
            
            logger.debug(f"[METADATA] 构建的元数据 | {json.dumps(metadata, ensure_ascii=False)}")
            
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
            response = await message_router.route(msg)
            
            response_preview = safe_log_string(response[:50]) if response else ""
            logger.info(f"[MESSAGE_RESPONSE] 生成响应 | message_id={message_id} | response={response_preview}")
            
            # 发送回复
            send_result = FeishuWebSocketService._send_message_static(user_id, response)
            if send_result:
                logger.debug(f"[MESSAGE_SEND] 消息发送成功 | user_id={user_id}")
            else:
                logger.warning(f"[MESSAGE_SEND] 消息发送失败 | user_id={user_id}")
            
            # 记录消息处理事件
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_event(logger, "feishu_message_processed",
                     message_id=message_id,
                     user_id=user_id,
                     chat_type=chat_type,
                     response_length=len(response),
                     elapsed_ms=elapsed_ms)
            
        except Exception as e:
            self.error_count += 1
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MESSAGE_PROCESS_ERROR] 异步消息处理失败 | message_id={message_id} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "feishu_message_error",
                     message_id=message_id,
                     user_id=user_id,
                     error=str(e),
                     elapsed_ms=elapsed_ms)
        finally:
            # 清理处理中状态
            self.processing_message_ids.discard(message_id)
            
            # 清理请求上下文
            clear_request_context()
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"[REQUEST_END] 消息处理完成 | message_id={message_id} | elapsed={elapsed_ms:.2f}ms")
            
            # 限制处理中消息ID的数量（内存保护）
            if len(self.processing_message_ids) > 100:
                self.processing_message_ids = set(list(self.processing_message_ids)[-50:])


class FeishuWebSocketService:
    _api_client = None
    
    def __init__(self):
        self.ws_client = None
        self.is_running = False
        self.event_handler = FeishuEventHandler()
        self.connection_attempts = 0
        logger.info("[INIT] FeishuWebSocketService 初始化完成")
    
    @staticmethod
    def _send_message_static(user_id: str, content: str) -> bool:
        """发送消息到飞书用户（静态方法）"""
        start_time = datetime.now()
        
        if FeishuWebSocketService._api_client is None:
            logger.error("[SEND_ERROR] 飞书 API 客户端未初始化")
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
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.success():
                logger.info(f"[SEND_SUCCESS] 消息发送成功 | user_id={user_id} | elapsed={elapsed_ms:.2f}ms")
                return True
            else:
                logger.error(f"[SEND_FAILED] 消息发送失败 | user_id={user_id} | code={response.code} | msg={response.msg}")
                return False
                
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[SEND_EXCEPTION] 发送消息异常 | user_id={user_id} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            return False
    
    def initialize(self):
        """初始化飞书 WebSocket 客户端"""
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.error("[INIT_ERROR] 飞书配置未完成：FEISHU_APP_ID 或 FEISHU_APP_SECRET 为空")
            return False
            
        logger.info("[INIT_START] 初始化飞书 WebSocket 客户端...")
        
        try:
            # 创建 API 客户端（用于发送消息）
            FeishuWebSocketService._api_client = ApiClient.builder() \
                .app_id(settings.FEISHU_APP_ID) \
                .app_secret(settings.FEISHU_APP_SECRET) \
                .build()
            
            logger.info("[API_CLIENT] 飞书 API 客户端创建成功")
            
            # 创建 WebSocket 客户端（用于接收事件）
            self.ws_client = WsClient(
                app_id=settings.FEISHU_APP_ID,
                app_secret=settings.FEISHU_APP_SECRET,
                log_level=LogLevel.INFO,
                event_handler=self.event_handler,
                domain="https://open.feishu.cn",
                auto_reconnect=True
            )
            
            logger.info("[WS_CLIENT] 飞书 WebSocket 客户端初始化成功")
            return True
        except Exception as e:
            logger.error(f"[INIT_FAILED] 飞书客户端初始化失败 | error={str(e)}", exc_info=True)
            return False
    
    async def start(self):
        """启动 WebSocket 服务"""
        if not self.initialize():
            return False
            
        self.is_running = True
        self.connection_attempts += 1
        
        logger.info(f"[START] 启动飞书 WebSocket 长连接服务 | attempt={self.connection_attempts}")
        
        try:
            # 使用线程运行同步的 start 方法
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.ws_client.start)
            
            logger.info("[CONNECTED] 飞书 WebSocket 连接成功")
            log_event(logger, "feishu_ws_connected",
                     attempt=self.connection_attempts)
                     
        except Exception as e:
            logger.error(f"[START_FAILED] WebSocket 服务启动失败 | error={str(e)}", exc_info=True)
            self.is_running = False
            log_event(logger, "feishu_ws_connection_failed",
                     attempt=self.connection_attempts,
                     error=str(e))
            return False
            
        return True
    
    def stop(self):
        """停止 WebSocket 服务"""
        self.is_running = False
        logger.info("[STOP] 飞书 WebSocket 长连接服务已停止")
        log_event(logger, "feishu_ws_stopped")


# 全局实例
feishu_websocket_service = FeishuWebSocketService()