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
from src.plugins.tool_executors import decode_filename

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
        """发送文件到飞书（符合 im/v1/files API 规范）"""
        # 自动初始化 API 客户端（如果尚未初始化）
        if self._api_client is None:
            logger.info("飞书API客户端未初始化，尝试自动初始化")
            if not self._initialize_client():
                logger.error("飞书API客户端初始化失败")
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
            
            # 检查文件大小（文档限制：最大30MB）
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(f"❌ 文件大小为0，不允许上传")
                return False
            if file_size > 30 * 1024 * 1024:
                logger.error(f"❌ 文件大小超出限制: {file_size/1024/1024:.2f}MB > 30MB")
                return False
            
            # 推断文件类型（根据文档要求）
            file_ext = os.path.splitext(file_name)[1].lower()
            file_type_map = {
                '.docx': 'doc', '.doc': 'doc',
                '.pdf': 'pdf',
                '.xlsx': 'xls', '.xls': 'xls',
                '.mp4': 'mp4',
                '.opus': 'opus'
            }
            file_type = file_type_map.get(file_ext, 'file')
            logger.info(f"📄 文件信息: name={file_name}, type={file_type}, size={file_size/1024/1024:.2f}MB")
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 步骤1：上传文件获取file_key（使用新版本API）
            from lark_oapi.api.drive.v1 import UploadAllFileRequest, UploadAllFileRequestBody
            
            # 构建上传请求
            upload_request = UploadAllFileRequest.builder() \
                .request_body(UploadAllFileRequestBody.builder() \
                    .file_name(file_name) \
                    .parent_type("tmp") \
                    .build()) \
                .file_content(file_content) \
                .build()
            
            upload_response = self._api_client.drive.v1.file.upload_all(upload_request)
            
            if not upload_response.success():
                # 根据文档错误码提供更详细的错误信息
                self._handle_upload_error(upload_response.code, upload_response.msg)
                return False
            
            file_key = upload_response.data.file_key
            logger.info(f"✅ 文件上传成功: file_key={file_key}")
            
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
                logger.info(f"✅ 飞书文件消息发送成功: user_id={user_id}, file={file_name}")
                return True
            else:
                logger.error(f"❌ 飞书文件消息发送失败: {response.code}, {response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送飞书文件异常: {str(e)}", exc_info=True)
            return False
    
    def _handle_upload_error(self, code: int, msg: str):
        """处理文件上传错误（根据飞书API文档错误码）"""
        error_messages = {
            232096: "应用信息被停写，请稍后重试",
            234001: "请求参数无效，请检查请求参数是否正确",
            234002: "接口鉴权失败，请检查tenant_access_token是否有效",
            234006: "文件大小超出限制（最大30MB）",
            234007: "应用没有启用机器人能力，请在飞书开放平台开启",
            234010: "文件大小为0，不允许上传",
            234041: "租户加密密钥被删除，请联系租户管理员",
            234042: "租户存储空间已满或存在存储错误，请联系租户管理员"
        }
        
        if code in error_messages:
            logger.error(f"❌ 文件上传失败 [{code}]: {error_messages[code]}")
        else:
            logger.error(f"❌ 文件上传失败 [{code}]: {msg}")
    
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
                file_content = await self._read_feishu_file(file_key, message_id)
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
                        
                        # 将文件内容添加到消息文本中，便于后续处理（保留完整内容）
                        text = f"文件：{file_name}\n\n{file_content}"
                    except Exception as e:
                        logger.error(f"存储文件内容失败: {str(e)}")
                else:
                    # 文件读取失败，向用户返回错误消息
                    error_message = f"文件读取失败，请检查飞书配置或联系管理员。\n\n文件名: {file_name}\n错误原因: 飞书API客户端未初始化或配置不正确"
                    await self.send_message(user_id, error_message)
                    logger.error(f"文件读取失败，已向用户发送错误消息: user_id={user_id}, file_name={file_name}")
                    self.processing_message_ids.discard(message_id)
                    return
            
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
                    "file_name": file_name,
                    "message_id": str(message_id)
                }
            )
            
            response = message_router.route(msg)
            await self.send_message(user_id, response)
        except Exception as e:
            logger.error(f"异步消息处理失败: {str(e)}")
        finally:
            self.processing_message_ids.discard(message_id)
    
    async def _read_feishu_file(self, file_key: str, message_id: str = None) -> Optional[str]:
        """读取飞书文件内容（支持 file_v3 新版API）
        
        Args:
            file_key: 文件的唯一标识（支持 file_v3_xxx 格式）
            message_id: 消息ID（可选），有message_id时优先使用推荐的消息资源接口
        
        Returns:
            文件内容字符串，失败返回None
        """
        try:
            if self._api_client is None:
                logger.error(f"读取飞书文件失败：file_key={file_key}, 飞书API客户端未初始化，请检查.env文件配置")
                return None
            
            # 检查 file_key 是否为 file_v3 格式
            is_file_v3 = file_key.startswith("file_v3_")
            
            # ======================
            # 方法 1：官方标准接口（唯一支持 file_v3）
            # ======================
            if message_id:
                try:
                    from lark_oapi.api.im.v1 import GetMessageResourceRequest, GetMessageResourceResponse
                    
                    req = GetMessageResourceRequest.builder() \
                        .message_id(message_id) \
                        .file_key(file_key) \
                        .type("file") \
                        .build()
                    
                    response: GetMessageResourceResponse = self._api_client.im.v1.message_resource.get(req)
                    
                    if response.success() and response.raw.content:
                        logger.info(f"使用 message resource 接口下载文件成功: {file_key}")
                        
                        # 尝试从响应头获取文件名
                        file_name = ""
                        if hasattr(response.raw, 'headers'):
                            content_disposition = response.raw.headers.get('Content-Disposition', '')
                            file_name = decode_filename(content_disposition)
                        
                        # 解析文件内容
                        return self._parse_file_content(response.raw.content, file_name)
                    
                    logger.debug(f"message resource 接口未返回内容: code={response.code}, msg={response.msg}")
                except Exception as e:
                    logger.error(f"方法1(message resource)失败: {str(e)}")
            elif is_file_v3:
                # file_v3 格式必须有 message_id
                logger.error(f"读取飞书文件失败：file_v3 格式文件需要有效的 message_id，当前 message_id 为空")
                return None
            
            # ======================
            # 方法 2：云文档 API（兼容旧版，不支持 file_v3）
            # ======================
            if not is_file_v3:
                try:
                    from lark_oapi.api.drive.v1 import DownloadFileRequest
                    
                    req = DownloadFileRequest.builder().file_token(file_key).build()
                    response = self._api_client.drive.v1.file.download(req)
                    
                    if response.success() and response.raw.content:
                        logger.info(f"使用 drive API 下载文件成功: {file_key}")
                        
                        # 尝试从响应头获取文件名
                        file_name = ""
                        if hasattr(response.raw, 'headers'):
                            content_disposition = response.raw.headers.get('Content-Disposition', '')
                            file_name = decode_filename(content_disposition)
                        
                        # 解析文件内容
                        return self._parse_file_content(response.raw.content, file_name)
                    
                    logger.debug(f"drive API 未返回内容: code={response.code}, msg={response.msg}")
                except Exception as e:
                    logger.error(f"方法2(drive API)失败: {str(e)}")
            
            # 构建详细错误信息
            error_msg = f"飞书文件下载失败"
            if is_file_v3:
                error_msg += f"（file_v3格式需要有效的message_id）"
            else:
                error_msg += f"（请确认file_key正确）"
            
            raise Exception(error_msg)
            
        except Exception as e:
            logger.error(f"读取飞书文件失败：file_key={file_key}, message_id={message_id}, 错误详情: {str(e)}", exc_info=True)
            return None

    def _download_via_message_resource(self, message_id: str, file_key: str) -> tuple:
        """
        使用飞书官方推荐的 message resource 接口下载文件（备用方法）
        
        接口: GET /open-apis/im/v1/messages/{message_id}/resource
        参数: message_id, file_key, type=file
        
        Returns:
            (文件内容bytes, 文件名)，失败返回(None, "")
        """
        try:
            from lark_oapi.api.im.v1 import GetMessageResourceRequest
            
            req = GetMessageResourceRequest.builder()\
                .message_id(message_id)\
                .file_key(file_key)\
                .type("file")\
                .build()
            
            resp = self._api_client.im.v1.message_resource.get(req)
            
            if resp.success():
                logger.info(f"使用 message resource 接口下载文件成功: {file_key}")
                # 尝试从响应头获取文件名
                file_name = ""
                if hasattr(resp.raw, 'headers'):
                    content_disposition = resp.raw.headers.get('Content-Disposition', '')
                    file_name = decode_filename(content_disposition)
                
                return (resp.raw.content, file_name)
            else:
                logger.error(f"message resource 接口调用失败: message_id={message_id}, file_key={file_key}, 错误码={resp.code}, 错误信息={resp.msg}")
                return (None, "")
                
        except Exception as e:
            logger.error(f"使用 message resource 接口下载失败: message_id={message_id}, file_key={file_key}, 错误详情: {str(e)}", exc_info=True)
            return (None, "")

    def _parse_file_content(self, content: bytes, file_name: str) -> str:
        """根据文件类型解析内容"""
        try:
            import os
            _, ext = os.path.splitext(file_name.lower())
            content_length = len(content)
            
            logger.debug(f"开始解析文件：file_name={file_name}, extension={ext}, content_length={content_length}")
            
            # 文本文件直接解码
            if ext in ['.txt', '.md', '.json', '.xml', '.html', '.csv', '.tsv']:
                logger.debug(f"解析文本文件：file_name={file_name}, encoding=utf-8")
                return content.decode('utf-8', errors='ignore')
            
            # docx 文件需要专门解析
            elif ext == '.docx':
                logger.debug(f"解析docx文件：file_name={file_name}")
                from docx import Document
                from io import BytesIO
                doc = Document(BytesIO(content))
                full_text = []
                for para in doc.paragraphs:
                    full_text.append(para.text)
                parsed_content = '\n'.join(full_text)
                logger.debug(f"docx解析完成：file_name={file_name}, parsed_length={len(parsed_content)}")
                return parsed_content
            
            # xlsx 文件解析
            elif ext == '.xlsx':
                logger.debug(f"解析xlsx文件：file_name={file_name}")
                import pandas as pd
                from io import BytesIO
                df = pd.read_excel(BytesIO(content))
                parsed_content = df.to_string()
                logger.debug(f"xlsx解析完成：file_name={file_name}, parsed_length={len(parsed_content)}")
                return parsed_content
            
            # pdf 文件解析
            elif ext == '.pdf':
                logger.debug(f"解析PDF文件：file_name={file_name}")
                from PyPDF2 import PdfReader
                from io import BytesIO
                reader = PdfReader(BytesIO(content))
                full_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                parsed_content = '\n'.join(full_text)
                logger.debug(f"PDF解析完成：file_name={file_name}, pages={len(reader.pages)}, parsed_length={len(parsed_content)}")
                return parsed_content
            
            # 其他未知类型，尝试作为文本处理
            else:
                logger.warning(f"未知文件格式：file_name={file_name}, extension={ext}")
                try:
                    text = content.decode('utf-8')
                    if self._is_binary(text):
                        error_msg = f"无法解析文件格式: {ext}\n\n文件大小: {content_length} bytes\n\n支持的文件类型: .txt, .md, .json, .xml, .html, .csv, .tsv, .docx, .xlsx, .pdf"
                        logger.warning(f"文件为二进制格式：file_name={file_name}, extension={ext}")
                        return error_msg
                    return text
                except Exception as decode_e:
                    error_msg = f"无法解析文件格式: {ext}\n\n文件大小: {content_length} bytes\n\n支持的文件类型: .txt, .md, .json, .xml, .html, .csv, .tsv, .docx, .xlsx, .pdf"
                    logger.error(f"文件解码失败：file_name={file_name}, extension={ext}, 错误: {str(decode_e)}")
                    return error_msg
                    
        except Exception as e:
            error_msg = f"文件解析失败：{str(e)}\n\n文件名: {file_name}\n文件大小: {len(content)} bytes"
            logger.error(f"解析文件内容失败：file_name={file_name}, 错误详情: {str(e)}", exc_info=True)
            return error_msg
    
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
