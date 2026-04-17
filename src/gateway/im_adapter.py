from typing import Dict, Any, Optional, List
from src.types import IMAdapterConfig, Message
from src.utils import generate_id, get_timestamp, setup_logging
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class IMAdapter:
    def __init__(self, config: IMAdapterConfig):
        self.config = config
        self.type = config.type
        self.enabled = config.enabled
    
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
        return Message(
            id=str(raw_message.get("message_id", generate_id())),
            user_id=str(raw_message.get("sender", {}).get("sender_id", {}).get("user_id", "unknown")),
            content=raw_message.get("content", ""),
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
        logger.info(f"Sending message via {self.type}: {message.content}")
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
