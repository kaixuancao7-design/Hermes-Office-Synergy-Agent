"""多模态处理器 - 支持文本、图片、语音等多种模态数据"""
import os
import base64
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod

from src.config import settings
from src.logging_config import get_logger

logger = get_logger("multimodal")


class MultimodalProcessorBase(ABC):
    """多模态处理器基类"""
    
    @abstractmethod
    def process(self, data: Union[str, bytes], **kwargs) -> Dict[str, Any]:
        """处理多模态数据"""
        pass
    
    @abstractmethod
    def supports(self, data_type: str) -> bool:
        """检查是否支持该数据类型"""
        pass


class ImageProcessor(MultimodalProcessorBase):
    """图片处理器"""
    
    def __init__(self, lazy_load: bool = True):
        self.initialized = False
        self.caption_model = None
        self.processor = None
        if not lazy_load:
            self._initialize()
    
    def _initialize(self):
        """初始化图片处理模型"""
        if self.initialized:
            return
            
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            self.initialized = True
            logger.info("图片处理器初始化成功")
        except ImportError:
            logger.warning("transformers库未安装，图片描述功能不可用")
        except Exception as e:
            logger.error(f"图片处理器初始化失败: {str(e)}")
    
    def _ensure_initialized(self):
        """确保模型已初始化"""
        self._initialize()
    
    def process(self, data: Union[str, bytes], **kwargs) -> Dict[str, Any]:
        """处理图片数据"""
        if not self.initialized:
            return {"success": False, "error": "图片处理器未初始化"}
        
        try:
            from PIL import Image
            import io
            
            # 如果是base64字符串，解码
            if isinstance(data, str) and data.startswith("data:image/"):
                # 去掉data:image/xxx;base64,前缀
                header, encoded = data.split(",", 1)
                data = base64.b64decode(encoded)
            
            # 如果是文件路径，读取文件
            if isinstance(data, str) and os.path.exists(data):
                image = Image.open(data).convert("RGB")
            else:
                image = Image.open(io.BytesIO(data)).convert("RGB")
            
            # 生成图片描述
            inputs = self.processor(image, return_tensors="pt")
            out = self.caption_model.generate(**inputs, max_length=50)
            caption = self.processor.decode(out[0], skip_special_tokens=True)
            
            # 获取图片信息
            width, height = image.size
            format = image.format
            
            return {
                "success": True,
                "caption": caption,
                "metadata": {
                    "width": width,
                    "height": height,
                    "format": format,
                    "size": len(data) if isinstance(data, bytes) else os.path.getsize(data)
                }
            }
        except ImportError:
            return {"success": False, "error": "PIL库未安装"}
        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def supports(self, data_type: str) -> bool:
        return data_type.lower() in ["image", "picture", "photo", "jpg", "jpeg", "png", "gif"]


class AudioProcessor(MultimodalProcessorBase):
    """音频处理器"""
    
    def __init__(self):
        self.initialized = False
        self._initialize()
    
    def _initialize(self):
        """初始化音频处理模型"""
        try:
            import whisper
            self.model = whisper.load_model("base")
            self.initialized = True
            logger.info("音频处理器初始化成功")
        except ImportError:
            logger.warning("whisper库未安装，语音转文字功能不可用")
        except Exception as e:
            logger.error(f"音频处理器初始化失败: {str(e)}")
    
    def process(self, data: Union[str, bytes], **kwargs) -> Dict[str, Any]:
        """处理音频数据"""
        if not self.initialized:
            return {"success": False, "error": "音频处理器未初始化"}
        
        try:
            import io
            
            # 如果是文件路径，直接处理
            if isinstance(data, str) and os.path.exists(data):
                result = self.model.transcribe(data)
            else:
                # 如果是字节数据，写入临时文件
                with io.BytesIO(data) as f:
                    f.write(data)
                    f.seek(0)
                    result = self.model.transcribe(f)
            
            return {
                "success": True,
                "transcription": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", ""),
                "metadata": {
                    "duration": result.get("duration", 0),
                    "segments_count": len(result.get("segments", []))
                }
            }
        except Exception as e:
            logger.error(f"处理音频失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def supports(self, data_type: str) -> bool:
        return data_type.lower() in ["audio", "voice", "sound", "mp3", "wav", "flac", "m4a"]


class VideoProcessor(MultimodalProcessorBase):
    """视频处理器"""
    
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.audio_processor = AudioProcessor()
    
    def process(self, data: Union[str, bytes], **kwargs) -> Dict[str, Any]:
        """处理视频数据"""
        try:
            import cv2
            import numpy as np
            
            # 如果是文件路径
            if isinstance(data, str) and os.path.exists(data):
                video_path = data
            else:
                # 如果是字节数据，写入临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                    f.write(data)
                    video_path = f.name
            
            # 提取帧
            cap = cv2.VideoCapture(video_path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            
            # 提取关键帧（每隔一段时间提取一帧）
            keyframes = []
            frame_interval = max(1, int(fps * 2))  # 每2秒提取一帧
            
            for i in range(0, frame_count, frame_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    # 将帧转换为图片描述
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()
                    
                    if self.image_processor.initialized:
                        result = self.image_processor.process(frame_bytes)
                        if result["success"]:
                            keyframes.append({
                                "frame_index": i,
                                "timestamp": i / fps,
                                "caption": result["caption"]
                            })
            
            cap.release()
            
            # 如果是临时文件，删除
            if "temp" in video_path:
                os.unlink(video_path)
            
            return {
                "success": True,
                "keyframes": keyframes,
                "metadata": {
                    "frame_count": frame_count,
                    "fps": fps,
                    "duration": duration,
                    "keyframes_count": len(keyframes)
                }
            }
        except ImportError:
            return {"success": False, "error": "cv2库未安装"}
        except Exception as e:
            logger.error(f"处理视频失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def supports(self, data_type: str) -> bool:
        return data_type.lower() in ["video", "mp4", "avi", "mov", "mkv"]


class TextProcessor(MultimodalProcessorBase):
    """文本处理器"""
    
    def process(self, data: Union[str, bytes], **kwargs) -> Dict[str, Any]:
        """处理文本数据"""
        try:
            # 如果是字节，解码
            if isinstance(data, bytes):
                content = data.decode("utf-8")
            else:
                content = str(data)
            
            # 简单的文本统计
            word_count = len(content.split())
            char_count = len(content)
            line_count = content.count('\n') + 1
            
            return {
                "success": True,
                "content": content,
                "metadata": {
                    "word_count": word_count,
                    "char_count": char_count,
                    "line_count": line_count,
                    "type": "text"
                }
            }
        except Exception as e:
            logger.error(f"处理文本失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def supports(self, data_type: str) -> bool:
        return data_type.lower() in ["text", "string", "document"]


class MultimodalProcessor:
    """多模态处理器"""
    
    def __init__(self):
        self.processors: List[MultimodalProcessorBase] = [
            TextProcessor(),
            ImageProcessor(),
            AudioProcessor(),
            VideoProcessor()
        ]
    
    def detect_type(self, data: Union[str, bytes], filename: Optional[str] = None) -> str:
        """
        检测数据类型
        
        Args:
            data: 数据内容
            filename: 文件名（可选，用于辅助检测）
        
        Returns:
            数据类型
        """
        # 如果提供了文件名，根据扩展名判断
        if filename:
            _, ext = os.path.splitext(filename)
            ext = ext.lower()
            
            image_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
            audio_exts = [".mp3", ".wav", ".flac", ".m4a", ".ogg"]
            video_exts = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
            text_exts = [".txt", ".md", ".json", ".xml", ".html"]
            
            if ext in image_exts:
                return "image"
            elif ext in audio_exts:
                return "audio"
            elif ext in video_exts:
                return "video"
            elif ext in text_exts:
                return "text"
        
        # 根据数据内容判断
        if isinstance(data, str):
            # 检查是否是base64图片
            if data.startswith("data:image/"):
                return "image"
            # 检查是否是base64音频
            if data.startswith("data:audio/"):
                return "audio"
            return "text"
        
        if isinstance(data, bytes):
            # 根据magic bytes判断
            if data[:4] in [b"\xff\xd8\xff", b"\x89PNG"]:
                return "image"
            if data[:3] == b"ID3" or data[:4] == b"fLaC":
                return "audio"
            if data[:4] == b"ftyp" or data[:2] == b"BM":
                return "video"
            
            # 尝试解码为文本
            try:
                data.decode("utf-8")
                return "text"
            except:
                return "binary"
        
        return "unknown"
    
    def process(self, data: Union[str, bytes], data_type: Optional[str] = None, 
               filename: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        处理多模态数据
        
        Args:
            data: 数据内容
            data_type: 数据类型（可选，自动检测）
            filename: 文件名（可选）
            kwargs: 额外参数
        
        Returns:
            处理结果
        """
        # 如果没有指定类型，自动检测
        if data_type is None:
            data_type = self.detect_type(data, filename)
        
        # 查找支持该类型的处理器
        for processor in self.processors:
            if processor.supports(data_type):
                result = processor.process(data, **kwargs)
                result["data_type"] = data_type
                result["filename"] = filename
                return result
        
        return {
            "success": False,
            "error": f"不支持的数据类型: {data_type}",
            "data_type": data_type,
            "filename": filename
        }
    
    def process_multiple(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理多个数据项
        
        Args:
            items: 数据项列表，每个项包含data、可选的data_type和filename
        
        Returns:
            处理结果列表
        """
        results = []
        for item in items:
            result = self.process(
                data=item["data"],
                data_type=item.get("data_type"),
                filename=item.get("filename"),
                **item.get("kwargs", {})
            )
            results.append(result)
        return results
    
    def get_supported_types(self) -> List[str]:
        """获取支持的数据类型"""
        types = set()
        for processor in self.processors:
            for t in ["text", "image", "audio", "video"]:
                if processor.supports(t):
                    types.add(t)
        return sorted(list(types))


# 全局实例
multimodal_processor = MultimodalProcessor()


# 便捷函数
def process_multimodal(data: Union[str, bytes], data_type: Optional[str] = None,
                      filename: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """处理多模态数据"""
    return multimodal_processor.process(data, data_type, filename, **kwargs)


def detect_data_type(data: Union[str, bytes], filename: Optional[str] = None) -> str:
    """检测数据类型"""
    return multimodal_processor.detect_type(data, filename)
