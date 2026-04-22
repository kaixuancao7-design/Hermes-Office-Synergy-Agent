from typing import Dict, Any, Optional, List
from src.types import IMAdapterConfig, Message
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
import requests
import json

logger = get_logger("im")


class IMAdapter:
    def __init__(self, config: IMAdapterConfig):
        self.config = config
        self.type = config.type
        self.enabled = config.enabled
        self.access_token = None
        self.token_expires_at = 0
    
    def _get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        if self.type != "feishu":
            return None
            
        # 检查令牌是否过期
        if self.access_token and get_timestamp() < self.token_expires_at:
            return self.access_token
            
        app_id = self.config.config.get("app_id")
        app_secret = self.config.config.get("app_secret")
        
        if not app_id or not app_secret:
            logger.error("Feishu app_id or app_secret not configured")
            return None
            
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": app_id,
                "app_secret": app_secret
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.access_token = result.get("tenant_access_token")
                self.token_expires_at = get_timestamp() + (result.get("expires_in", 7200) - 100)
                logger.info("Feishu access token refreshed successfully")
                return self.access_token
            else:
                logger.error(f"Failed to get Feishu token: {result.get('msg')}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting Feishu access token: {str(e)}")
            return None
    
    def receive_message(self, raw_message: Dict[str, Any]) -> Optional[Message]:
        if not self.enabled:
            return None
        
        try:
            return self._parse_message(raw_message)
        except Exception as e:
            logger.error(f"Failed to parse message from {self.type}: {str(e)}")
            return None
    
    def _parse_message(self, raw_message: Dict[str, Any]) -> Message:
        message_map = {
            "feishu": self._parse_feishu_message,
            "dingtalk": self._parse_dingtalk_message,
            "wecom": self._parse_wecom_message,
            "wechat": self._parse_wechat_message,
            "slack": self._parse_slack_message,
            "discord": self._parse_discord_message
        }
        
        parser = message_map.get(self.type)
        if parser:
            return parser(raw_message)
        
        return Message(
            id=generate_id(),
            user_id=raw_message.get("user_id", "unknown"),
            content=raw_message.get("content", ""),
            role="user",
            timestamp=get_timestamp(),
            metadata={"source": self.type}
        )
    
    def _parse_feishu_message(self, raw_message: Dict[str, Any]) -> Message:
        # 解析飞书 Webhook 消息
        msg_type = raw_message.get("type", "")
        
        def _parse_content(content: str) -> str:
            """解析飞书消息内容（JSON格式）"""
            if not content:
                return ""
            try:
                content_json = json.loads(content)
                return content_json.get("text", content)
            except:
                return content
        
        if msg_type == "event":
            # 飞书事件回调格式
            event = raw_message.get("event", {})
            content = event.get("message", {}).get("content", "")
            return Message(
                id=str(event.get("message", {}).get("message_id", generate_id())),
                user_id=str(event.get("sender", {}).get("sender_id", {}).get("user_id", "unknown")),
                content=_parse_content(content),
                role="user",
                timestamp=event.get("event_time", get_timestamp()),
                metadata={"source": "feishu", "group": event.get("message", {}).get("chat_type") == "group"}
            )
        else:
            # 普通消息格式
            content = raw_message.get("content", "")
            return Message(
                id=str(raw_message.get("message_id", generate_id())),
                user_id=str(raw_message.get("sender", {}).get("sender_id", {}).get("user_id", "unknown")),
                content=_parse_content(content),
                role="user",
                timestamp=raw_message.get("create_time", get_timestamp()),
                metadata={"source": "feishu"}
            )
    
    def _parse_dingtalk_message(self, raw_message: Dict[str, Any]) -> Message:
        return Message(
            id=str(raw_message.get("msgId", generate_id())),
            user_id=str(raw_message.get("senderId", "unknown")),
            content=raw_message.get("text", ""),
            role="user",
            timestamp=raw_message.get("createTime", get_timestamp()),
            metadata={"source": "dingtalk"}
        )
    
    def _parse_wecom_message(self, raw_message: Dict[str, Any]) -> Message:
        return Message(
            id=str(raw_message.get("MsgId", generate_id())),
            user_id=str(raw_message.get("FromUserName", "unknown")),
            content=raw_message.get("Content", ""),
            role="user",
            timestamp=raw_message.get("CreateTime", get_timestamp()),
            metadata={"source": "wecom"}
        )
    
    def _parse_wechat_message(self, raw_message: Dict[str, Any]) -> Message:
        return Message(
            id=str(raw_message.get("MsgId", generate_id())),
            user_id=str(raw_message.get("FromUserName", "unknown")),
            content=raw_message.get("Content", ""),
            role="user",
            timestamp=raw_message.get("CreateTime", get_timestamp()),
            metadata={"source": "wechat"}
        )
    
    def _parse_slack_message(self, raw_message: Dict[str, Any]) -> Message:
        return Message(
            id=str(raw_message.get("ts", generate_id())),
            user_id=str(raw_message.get("user", "unknown")),
            content=raw_message.get("text", ""),
            role="user",
            timestamp=int(float(raw_message.get("ts", get_timestamp()))),
            metadata={"source": "slack"}
        )
    
    def _parse_discord_message(self, raw_message: Dict[str, Any]) -> Message:
        return Message(
            id=str(raw_message.get("id", generate_id())),
            user_id=str(raw_message.get("author", {}).get("id", "unknown")),
            content=raw_message.get("content", ""),
            role="user",
            timestamp=raw_message.get("timestamp", get_timestamp()),
            metadata={"source": "discord"}
        )
    
    def send_message(self, message: Message) -> bool:
        """发送消息到 IM 平台"""
        send_map = {
            "feishu": self._send_feishu_message,
            "dingtalk": self._send_dingtalk_message,
            "wecom": self._send_wecom_message,
            "wechat": self._send_wechat_message,
            "slack": self._send_slack_message,
            "discord": self._send_discord_message
        }
        
        sender = send_map.get(self.type)
        if sender:
            return sender(message)
        
        logger.info(f"Sending message via {self.type}: {message.content}")
        return True
    
    def _send_feishu_message(self, message: Message) -> bool:
        """发送消息到飞书"""
        token = self._get_access_token()
        if not token:
            logger.error("Cannot send Feishu message: no access token")
            return False
            
        try:
            # 解析消息内容（飞书消息内容是 JSON 字符串）
            content = message.content
            try:
                content_json = json.loads(message.content)
                text = content_json.get("text", message.content)
            except:
                text = message.content
            
            # 构建消息
            payload = {
                "receive_id": message.user_id,
                "content": json.dumps({
                    "text": text
                }),
                "msg_type": "text"
            }
            
            # 飞书 API 需要在 URL 中指定 receive_id_type
            url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                logger.info(f"Message sent to Feishu successfully")
                return True
            else:
                logger.error(f"Failed to send Feishu message: {result.get('msg')}")
                return False
                
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json()
                logger.error(f"Feishu API error: {error_detail.get('msg', str(e))} (code: {error_detail.get('code')})")
            except:
                logger.error(f"Feishu HTTP error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending Feishu message: {str(e)}")
            return False
    
    def _send_dingtalk_message(self, message: Message) -> bool:
        """发送消息到钉钉"""
        logger.info(f"Sending message via dingtalk: {message.content}")
        return True
    
    def _send_wecom_message(self, message: Message) -> bool:
        """发送消息到企业微信"""
        logger.info(f"Sending message via wecom: {message.content}")
        return True
    
    def _send_wechat_message(self, message: Message) -> bool:
        """发送消息到微信"""
        logger.info(f"Sending message via wechat: {message.content}")
        return True
    
    def _send_slack_message(self, message: Message) -> bool:
        """发送消息到 Slack"""
        logger.info(f"Sending message via slack: {message.content}")
        return True
    
    def _send_discord_message(self, message: Message) -> bool:
        """发送消息到 Discord"""
        logger.info(f"Sending message via discord: {message.content}")
        return True


class IMAdapterManager:
    def __init__(self):
        self.adapters: Dict[str, IMAdapter] = {}
    
    def register_adapter(self, config: IMAdapterConfig) -> None:
        adapter = IMAdapter(config)
        self.adapters[config.type] = adapter
        logger.info(f"Registered {config.type} adapter")
    
    def get_adapter(self, adapter_type: str) -> Optional[IMAdapter]:
        return self.adapters.get(adapter_type)
    
    def process_raw_message(self, raw_message: Dict[str, Any], source: str) -> Optional[Message]:
        adapter = self.adapters.get(source)
        if adapter:
            return adapter.receive_message(raw_message)
        return None


im_adapter_manager = IMAdapterManager()
