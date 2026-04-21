from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
from src.engine.demand_parser import demand_parser, PPTDemand
from src.utils import setup_logging, generate_id
from src.config import settings
import re

logger = setup_logging(settings.LOG_LEVEL)


class MessageContext(BaseModel):
    """消息上下文"""
    message_id: str
    user_id: str
    user_name: str
    content: str
    timestamp: str
    attachments: List[Dict[str, Any]] = []
    mentioned_users: List[str] = []
    chat_type: str = "group"  # group, private
    chat_id: str = ""
    reply_to_message_id: Optional[str] = None


class TriggerResult(BaseModel):
    """触发结果"""
    is_triggered: bool = False
    trigger_type: str = ""  # direct, passive, attachment
    demand: Optional[PPTDemand] = None
    response: str = ""
    context: Optional[MessageContext] = None


class IMTrigger:
    """IM端触发器 - 处理多模态触发和需求解析"""
    
    def __init__(self):
        # 机器人名称列表（用于识别@消息）
        self.bot_names = ["hermes", "hermes-bot", "智能助手", "@Hermes"]
        
        # 被动触发关键词
        self.passive_keywords = [
            "做个ppt", "做ppt", "制作ppt", "生成ppt",
            "汇报材料", "演示稿", "幻灯片",
            "需要一个演示", "帮我做个", "能不能做"
        ]
        
        # 支持的附件类型
        self.supported_attachments = [
            ".xlsx", ".xls", ".csv",
            ".docx", ".doc",
            ".pdf",
            ".pptx", ".ppt",
            ".txt", ".md"
        ]
    
    def process_message(self, message: Dict[str, Any]) -> TriggerResult:
        """
        处理IM消息，判断是否触发PPT生成流程
        
        Args:
            message: 消息字典，包含：
                - user_id: 用户ID
                - content: 消息内容
                - attachments: 附件列表
                - mentioned_users: @的用户列表
                - chat_type: 聊天类型
                - chat_id: 聊天ID
                - timestamp: 时间戳
        
        Returns:
            TriggerResult: 触发结果
        """
        # 构建消息上下文
        context = MessageContext(
            message_id=message.get("message_id", generate_id()),
            user_id=message.get("user_id", ""),
            user_name=message.get("user_name", ""),
            content=message.get("content", ""),
            timestamp=message.get("timestamp", ""),
            attachments=message.get("attachments", []),
            mentioned_users=message.get("mentioned_users", []),
            chat_type=message.get("chat_type", "group"),
            chat_id=message.get("chat_id", ""),
            reply_to_message_id=message.get("reply_to_message_id")
        )
        
        # 1. 检查是否@机器人（主动触发）
        if self._is_direct_mention(context):
            return self._handle_direct_trigger(context)
        
        # 2. 检查是否包含PPT需求关键词（被动触发）
        if self._is_passive_trigger(context):
            return self._handle_passive_trigger(context)
        
        # 3. 检查是否有相关附件
        if self._has_relevant_attachment(context):
            # 只有在群聊中且最近有PPT讨论时才触发
            if self._recent_ppt_discussion(context.chat_id):
                return self._handle_passive_trigger(context)
        
        return TriggerResult(is_triggered=False)
    
    def _is_direct_mention(self, context: MessageContext) -> bool:
        """检查是否直接@机器人"""
        content = context.content.lower()
        
        # 检查@列表中是否有机器人
        for mentioned in context.mentioned_users:
            mentioned_lower = mentioned.lower()
            for bot_name in self.bot_names:
                if bot_name.lower() in mentioned_lower or mentioned_lower in bot_name.lower():
                    return True
        
        # 检查消息内容中是否包含@机器人
        for bot_name in self.bot_names:
            if bot_name.lower() in content:
                return True
        
        return False
    
    def _is_passive_trigger(self, context: MessageContext) -> bool:
        """检查是否包含被动触发关键词"""
        content = context.content.lower()
        
        # 排除纯表情和简短消息
        if len(content.strip()) < 5:
            return False
        
        # 排除已@机器人的情况（已在主动触发中处理）
        if self._is_direct_mention(context):
            return False
        
        # 检查关键词
        for keyword in self.passive_keywords:
            if keyword in content:
                return True
        
        return False
    
    def _has_relevant_attachment(self, context: MessageContext) -> bool:
        """检查是否有相关附件"""
        for attachment in context.attachments:
            file_name = attachment.get("name", "")
            for ext in self.supported_attachments:
                if file_name.lower().endswith(ext):
                    return True
        return False
    
    def _recent_ppt_discussion(self, chat_id: str) -> bool:
        """检查最近是否有PPT相关讨论（简化实现）"""
        # TODO: 实际实现需要查询聊天历史
        # 这里简化为返回True，表示检查通过
        return True
    
    def _handle_direct_trigger(self, context: MessageContext) -> TriggerResult:
        """处理主动触发（@机器人）"""
        logger.info(f"Direct trigger from user {context.user_id}")
        
        # 提取指令（移除@机器人部分）
        instruction = self._clean_instruction(context.content)
        
        # 构建上下文信息
        context_data = {
            "attachments": [att.get("name", "") for att in context.attachments],
            "chat_history_ids": [],
            "document_links": self._extract_links(context.content)
        }
        
        # 解析需求
        demand = demand_parser.extract_demand(instruction, context_data)
        demand.user_id = context.user_id
        
        # 生成响应
        response = demand_parser.generate_confirmation_message(demand)
        
        return TriggerResult(
            is_triggered=True,
            trigger_type="direct",
            demand=demand,
            response=response,
            context=context
        )
    
    def _handle_passive_trigger(self, context: MessageContext) -> TriggerResult:
        """处理被动触发（关键词匹配）"""
        logger.info(f"Passive trigger from user {context.user_id}")
        
        # 构建上下文信息
        context_data = {
            "attachments": [att.get("name", "") for att in context.attachments],
            "chat_history_ids": [],
            "document_links": self._extract_links(context.content)
        }
        
        # 解析需求
        demand = demand_parser.extract_demand(context.content, context_data)
        demand.user_id = context.user_id
        
        # 生成被动响应（询问是否需要帮助）
        response = f"我注意到您可能需要制作PPT，需要我帮忙吗？\n\n{demand_parser.generate_confirmation_message(demand)}"
        
        return TriggerResult(
            is_triggered=True,
            trigger_type="passive",
            demand=demand,
            response=response,
            context=context
        )
    
    def _clean_instruction(self, content: str) -> str:
        """清理指令（移除@机器人部分）"""
        cleaned = content
        
        # 移除@符号和后面的用户名（包括机器人名称）
        cleaned = re.sub(r'@\S+\s*', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_links(self, content: str) -> List[str]:
        """从文本中提取链接"""
        # 简单的URL匹配
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, content)
    
    def handle_voice_input(self, voice_text: str, context: Dict[str, Any]) -> TriggerResult:
        """处理语音输入"""
        logger.info(f"Voice input received: {voice_text[:50]}...")
        
        # 将语音转文字后按普通文本处理
        message = {
            **context,
            "content": voice_text,
            "mentioned_users": []
        }
        
        return self.process_message(message)
    
    def handle_attachment_upload(self, attachment: Dict[str, Any], context: Dict[str, Any]) -> TriggerResult:
        """处理附件上传"""
        file_name = attachment.get("name", "")
        
        # 检查是否是支持的文件类型
        for ext in self.supported_attachments:
            if file_name.lower().endswith(ext):
                logger.info(f"Attachment trigger: {file_name}")
                
                # 构建消息上下文
                message = {
                    **context,
                    "content": f"用这份《{file_name}》生成PPT",
                    "attachments": [attachment]
                }
                
                return self.process_message(message)
        
        return TriggerResult(is_triggered=False)
    
    def handle_reply(self, reply_content: str, original_message: Dict[str, Any]) -> TriggerResult:
        """处理回复消息"""
        # 检查原始消息是否是PPT需求相关
        original_content = original_message.get("content", "")
        
        if demand_parser.detect_ppt_demand(original_content):
            logger.info(f"Reply to PPT demand detected")
            
            # 将回复内容合并到上下文中
            context = {
                **original_message,
                "content": f"{original_content}\n补充：{reply_content}",
                "reply_to_message_id": original_message.get("message_id")
            }
            
            return self.process_message(context)
        
        return TriggerResult(is_triggered=False)


# 单例实例
im_trigger = IMTrigger()
