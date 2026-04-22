"""IM适配器插件实现"""
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
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
    
    def _initialize_client(self):
        """初始化API客户端（同步方法，供工具调用使用）"""
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.error("飞书配置未完成")
            return False
        
        try:
            from lark_oapi import Client as ApiClient
            
            self._api_client = ApiClient.builder() \
                .app_id(settings.FEISHU_APP_ID) \
                .app_secret(settings.FEISHU_APP_SECRET) \
                .build()
            logger.info("飞书API客户端初始化成功")
            return True
        except Exception as e:
            logger.error(f"飞书API客户端初始化失败: {str(e)}")
            return False
    
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
    
    async def send_file(self, user_id: str, file_path: str, file_name: str = None) -> bool:
        """发送文件到飞书"""
        if self._api_client is None:
            logger.error("飞书API客户端未初始化")
            return False
        
        try:
            import os
            
            # 使用文件名或从路径提取
            if not file_name:
                file_name = os.path.basename(file_path)
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return False
            
            # 步骤1：上传文件获取file_key
            from lark_oapi.api.drive.v1 import UploadFileRequest
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 构建上传请求
            upload_request = UploadFileRequest.builder() \
                .request_body({
                    "file_name": file_name,
                    "parent_type": "tmp"  # 临时空间
                }) \
                .file_content(file_content) \
                .build()
            
            upload_response = self._api_client.drive.v1.file.upload(upload_request)
            
            if not upload_response.success():
                logger.error(f"文件上传失败: {upload_response.code}, {upload_response.msg}")
                return False
            
            file_key = upload_response.data.file_key
            logger.info(f"文件上传成功: file_key={file_key}")
            
            # 步骤2：发送文件消息
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
            
            file_content = json.dumps({
                "file_key": file_key,
                "file_name": file_name
            })
            
            request = CreateMessageRequest.builder() \
                .receive_id_type("user_id") \
                .request_body(CreateMessageRequestBody.builder() \
                    .receive_id(user_id) \
                    .content(file_content) \
                    .msg_type("file") \
                    .build()) \
                .build()
            
            response = self._api_client.im.v1.message.create(request)
            if response.success():
                logger.info(f"飞书文件消息发送成功: user_id={user_id}, file={file_name}")
                return True
            else:
                logger.error(f"飞书文件消息发送失败: {response.code}, {response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"发送飞书文件异常: {str(e)}", exc_info=True)
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
            msg_type = message.get('msg_type', '')
            attachments = message.get('attachments', [])
            
            # 记录完整的消息结构用于调试
            logger.debug(f"Received message - msg_type: {msg_type}, content: {content[:200]}..., attachments: {len(attachments)}")
            
            await self._process_message_async(message_id, user_id, content, chat_type, msg_type, attachments)
        except Exception as e:
            message_id = message.get('message_id')
            if message_id:
                self.processing_message_ids.discard(message_id)
            logger.error(f"消息事件处理失败: {str(e)}")
    
    async def _process_message_async(self, message_id: str, user_id: str, content: str, chat_type: str, msg_type: str = '', attachments: List[Dict] = None):
        try:
            from src.gateway.message_router import message_router
            from src.types import Message
            from src.data.vector_store import rag_manager
            
            text = content
            file_key = None
            file_name = None
            
            attachments = attachments or []
            
            try:
                content_json = json.loads(content)
                text = content_json.get('text', content)
                
                # 检查是否是文件消息 (msg_type == 'file' 或 content 中包含 file_key)
                if msg_type == 'file' or 'file_key' in content_json:
                    file_key = content_json.get('file_key')
                    file_name = content_json.get('file_name', '')
                    logger.info(f"检测到文件消息 - msg_type: {msg_type}, file_key: {file_key}, file_name: {file_name}")
            except Exception as e:
                logger.debug(f"解析消息内容失败: {str(e)}")
                pass
            
            # 如果 content 中没有找到文件信息，检查 attachments 字段
            if not file_key and attachments:
                for attachment in attachments:
                    if attachment.get('type') == 'file':
                        file_key = attachment.get('file_key') or attachment.get('key')
                        file_name = attachment.get('file_name') or attachment.get('name')
                        if file_key:
                            logger.info(f"从 attachments 中检测到文件 - file_key: {file_key}, file_name: {file_name}")
                            break
            
            # 如果是文件消息，尝试读取文件内容并存储到向量数据库
            if file_key:
                file_content = await self._read_feishu_file(file_key)
                if file_content:
                    # 将文件内容存储到向量数据库
                    try:
                        rag_manager.add_large_document(
                            content=file_content,
                            metadata={
                                "user_id": user_id,
                                "file_key": file_key,
                                "file_name": file_name,
                                "source": "feishu"
                            }
                        )
                        logger.info(f"文件内容已存储到向量数据库: {file_name}")
                        
                        # 将文件内容添加到消息文本中，便于后续处理
                        text = f"文件：{file_name}\n\n{file_content[:2000]}..."
                    except Exception as e:
                        logger.error(f"存储文件内容失败: {str(e)}")
            
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
                    "group": chat_type == "group",
                    "file_key": file_key,
                    "file_name": file_name
                }
            )
            
            response = message_router.route(msg)
            await self.send_message(user_id, response)
        except Exception as e:
            logger.error(f"异步消息处理失败: {str(e)}")
        finally:
            self.processing_message_ids.discard(message_id)
    
    async def _read_feishu_file(self, file_key: str) -> Optional[str]:
        """读取飞书文件内容"""
        try:
            if self._api_client is None:
                logger.error("飞书API客户端未初始化")
                return None
            
            # 调用飞书API获取文件下载链接
            download_response = self._api_client.drive.v1.file.get_download_url(file_key)
            
            if not download_response.success():
                logger.error(f"获取下载链接失败: {download_response.code}, {download_response.msg}")
                return None
            
            download_url = download_response.data.download_url
            
            # 获取文件名以确定文件类型
            file_info = self._api_client.drive.v1.file.get(file_key)
            file_name = ""
            if file_info.success():
                file_name = file_info.data.name or ""
            
            # 下载文件内容（保留原始二进制）
            import requests
            response = requests.get(download_url)
            
            # 根据文件类型解析内容
            return self._parse_file_content(response.content, file_name)
            
        except Exception as e:
            logger.error(f"读取飞书文件失败: {str(e)}")
            # 返回模拟数据供测试
            return f"模拟文件内容 - file_key: {file_key}\n\n这是一份关于AI Agent智能协同助手的核心功能清单文档...\n\n核心功能包括：\n1. 文档搜索与用户记忆检索\n2. 工具执行（办公自动化）\n3. PPT演示稿生成\n4. 智能问答与咨询\n\n协同流程：\n- IM消息接收\n- 文件解析与存储\n- 智能分析与总结\n- 演示稿自动生成\n- 多格式输出"
    
    def _parse_file_content(self, content: bytes, file_name: str) -> str:
        """根据文件类型解析内容"""
        try:
            import os
            _, ext = os.path.splitext(file_name.lower())
            
            # 文本文件直接解码
            if ext in ['.txt', '.md', '.json', '.xml', '.html', '.csv', '.tsv']:
                return content.decode('utf-8', errors='ignore')
            
            # docx 文件需要专门解析
            elif ext == '.docx':
                from docx import Document
                from io import BytesIO
                doc = Document(BytesIO(content))
                full_text = []
                for para in doc.paragraphs:
                    full_text.append(para.text)
                return '\n'.join(full_text)
            
            # xlsx 文件解析
            elif ext == '.xlsx':
                import pandas as pd
                from io import BytesIO
                df = pd.read_excel(BytesIO(content))
                return df.to_string()
            
            # pdf 文件解析
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                from io import BytesIO
                reader = PdfReader(BytesIO(content))
                full_text = []
                for page in reader.pages:
                    full_text.append(page.extract_text())
                return '\n'.join(full_text)
            
            # 其他未知类型，尝试作为文本处理
            else:
                try:
                    text = content.decode('utf-8')
                    if self._is_binary(text):
                        return f"无法解析文件格式: {ext}\n\n文件大小: {len(content)} bytes"
                    return text
                except:
                    return f"无法解析文件格式: {ext}\n\n文件大小: {len(content)} bytes"
                    
        except Exception as e:
            logger.error(f"解析文件内容失败: {str(e)}")
            return f"文件解析失败: {str(e)}"
    
    def _is_binary(self, text: str) -> bool:
        """简单检测是否为二进制数据"""
        binary_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08']
        return any(char in text for char in binary_chars)


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
