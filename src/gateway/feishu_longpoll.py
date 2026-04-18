import asyncio
import json
import logging
from typing import Dict, Any, Optional
import requests

from src.config import settings
from src.gateway.message_router import message_router
from src.types import Message
from src.utils import generate_id, get_timestamp

logger = logging.getLogger("hermes_office_agent")

class FeishuLongPollService:
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0
        self.is_running = False
        self.polling_url = None
        self.subscription_id = None
        
    def _get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        if self.access_token and get_timestamp() < self.token_expires_at:
            return self.access_token
            
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.error("飞书配置未完成：FEISHU_APP_ID 或 FEISHU_APP_SECRET 为空")
            return None
            
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": settings.FEISHU_APP_ID,
                "app_secret": settings.FEISHU_APP_SECRET
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.access_token = result.get("tenant_access_token")
                self.token_expires_at = get_timestamp() + (result.get("expires_in", 7200) - 100)
                logger.info("飞书 access token 获取成功")
                return self.access_token
            else:
                logger.error(f"获取 access token 失败: {result.get('msg')}")
                return None
                
        except Exception as e:
            logger.error(f"获取 access token 异常: {str(e)}")
            return None
    
    def _create_subscription(self) -> bool:
        """创建事件订阅"""
        token = self._get_access_token()
        if not token:
            return False
            
        try:
            url = "https://open.feishu.cn/open-apis/im/v1/events/subscriptions"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # 创建订阅请求
            payload = {
                "subscription": {
                    "event_key": "im.message.receive_v1",
                    "subscriber": {
                        "subscriber_type": "application"
                    },
                    "config": {
                        "filter": {
                            "message_type": "text",
                            "chat_type": ["p2p", "group"]
                        }
                    }
                }
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.subscription_id = result.get("data", {}).get("subscription", {}).get("subscription_id")
                logger.info(f"创建事件订阅成功: subscription_id={self.subscription_id}")
                return True
            else:
                # 如果订阅已存在，获取现有订阅
                if result.get("code") == 99991603:  # 订阅已存在
                    logger.info("事件订阅已存在，尝试获取现有订阅")
                    return self._get_existing_subscription()
                logger.error(f"创建事件订阅失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"创建事件订阅异常: {str(e)}")
            return False
    
    def _get_existing_subscription(self) -> bool:
        """获取现有事件订阅"""
        token = self._get_access_token()
        if not token:
            return False
            
        try:
            url = "https://open.feishu.cn/open-apis/im/v1/events/subscriptions"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                subscriptions = result.get("data", {}).get("items", [])
                if subscriptions:
                    self.subscription_id = subscriptions[0].get("subscription_id")
                    logger.info(f"获取现有订阅成功: subscription_id={self.subscription_id}")
                    return True
                else:
                    logger.error("未找到现有订阅")
                    return False
            else:
                logger.error(f"获取订阅失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"获取订阅异常: {str(e)}")
            return False
    
    def _get_long_poll_url(self) -> bool:
        """获取长连接 URL"""
        if not self.subscription_id:
            if not self._create_subscription():
                return False
                
        token = self._get_access_token()
        if not token:
            return False
            
        try:
            url = f"https://open.feishu.cn/open-apis/im/v1/events/subscriptions/{self.subscription_id}/long_polling_url"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.post(url, headers=headers, json={})
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.polling_url = result.get("data", {}).get("url")
                logger.info(f"获取长连接 URL 成功: {self.polling_url[:50]}...")
                return True
            else:
                logger.error(f"获取长连接 URL 失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"获取长连接 URL 异常: {str(e)}")
            return False
    
    def _parse_message(self, event: dict) -> Optional[Message]:
        """解析飞书消息事件"""
        try:
            message = event.get("message", {})
            sender = event.get("sender", {})
            
            message_id = message.get("message_id", generate_id())
            user_id = sender.get("sender_id", {}).get("user_id", "unknown")
            content = message.get("content", "{}")
            chat_type = message.get("chat_type", "p2p")
            
            # 解析内容
            try:
                content_json = json.loads(content)
                text = content_json.get("text", content)
            except:
                text = content
            
            # 去除 @提及
            bot_name = settings.FEISHU_BOT_NAME
            if bot_name and f"@{bot_name}" in text:
                text = text.replace(f"@{bot_name}", "").strip()
            
            return Message(
                id=str(message_id),
                user_id=str(user_id),
                content=text,
                role="user",
                timestamp=get_timestamp(),
                metadata={
                    "source": "feishu",
                    "group": chat_type == "group",
                    "original_event": event
                }
            )
        except Exception as e:
            logger.error(f"消息解析失败: {str(e)}")
            return None
    
    def _send_message(self, user_id: str, content: str) -> bool:
        """发送消息到飞书用户"""
        token = self._get_access_token()
        if not token:
            logger.error("无法发送消息：没有 access token")
            return False
            
        try:
            url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
            payload = {
                "receive_id": user_id,
                "content": json.dumps({"text": content}),
                "msg_type": "text"
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                logger.info(f"消息发送成功: user_id={user_id}")
                return True
            else:
                logger.error(f"消息发送失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"发送消息异常: {str(e)}")
            return False
    
    def _handle_event(self, event: dict):
        """处理飞书事件"""
        event_type = event.get("type")
        
        if event_type == "message":
            message = self._parse_message(event)
            if message:
                logger.info(f"收到消息: user_id={message.user_id}, content={message.content[:50]}")
                
                try:
                    # 使用消息路由处理
                    response = message_router.route(message)
                    logger.info(f"生成响应: {response[:50]}")
                    
                    # 发送回复
                    self._send_message(message.user_id, response)
                except Exception as e:
                    logger.error(f"消息处理失败: {str(e)}")
                    
                    # 发送错误提示
                    error_msg = "抱歉，处理您的消息时发生错误，请稍后重试。"
                    self._send_message(message.user_id, error_msg)
    
    async def _start_long_polling(self):
        """启动长连接轮询"""
        logger.info("启动飞书长连接服务...")
        
        while self.is_running:
            try:
                token = self._get_access_token()
                if not token:
                    await asyncio.sleep(5)
                    continue
                
                # 获取长连接 URL
                if not self.polling_url:
                    if not self._get_long_poll_url():
                        await asyncio.sleep(5)
                        continue
                
                # 轮询事件
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(self.polling_url, headers=headers, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 0:
                        events = result.get("data", {}).get("events", [])
                        if events:
                            logger.info(f"收到 {len(events)} 个事件")
                            for event in events:
                                self._handle_event(event)
                        else:
                            # 没有事件，继续轮询
                            pass
                    else:
                        # URL 可能过期，重新获取
                        self.polling_url = None
                        logger.error(f"轮询失败: {result.get('msg')}")
                else:
                    # 连接异常，重新获取 URL
                    self.polling_url = None
                    await asyncio.sleep(1)
                    
            except requests.exceptions.Timeout:
                # 长连接超时是正常的，继续轮询
                pass
            except Exception as e:
                logger.error(f"长连接轮询异常: {str(e)}")
                self.polling_url = None
                await asyncio.sleep(5)
    
    def start(self):
        """启动长连接服务（同步方式）"""
        self.is_running = True
        
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._start_long_polling())
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭长连接服务...")
            self.stop()
        except Exception as e:
            logger.error(f"启动长连接服务失败: {str(e)}")
            return False
            
        return True
    
    def stop(self):
        """停止长连接服务"""
        self.is_running = False
        logger.info("飞书长连接服务已停止")
    
    async def start_async(self):
        """启动长连接服务（异步方式）"""
        self.is_running = True
        await self._start_long_polling()
        return True

# 全局实例
feishu_longpoll_service = FeishuLongPollService()