"""文档版本管理器 - 支持文档版本追踪和管理"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import settings
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("version_manager")


class VersionInfo:
    """版本信息"""
    
    def __init__(self, version_id: str, document_id: str, content: str, 
                 metadata: Dict[str, Any], created_at: str, 
                 created_by: str, version_number: int = 1, 
                 parent_version_id: Optional[str] = None, 
                 change_note: str = ""):
        self.version_id = version_id
        self.document_id = document_id
        self.content = content
        self.metadata = metadata
        self.created_at = created_at
        self.created_by = created_by
        self.version_number = version_number
        self.parent_version_id = parent_version_id
        self.change_note = change_note
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version_id": self.version_id,
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "version_number": self.version_number,
            "parent_version_id": self.parent_version_id,
            "change_note": self.change_note
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionInfo":
        """从字典创建"""
        return cls(
            version_id=data["version_id"],
            document_id=data["document_id"],
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", get_timestamp()),
            created_by=data.get("created_by", ""),
            version_number=data.get("version_number", 1),
            parent_version_id=data.get("parent_version_id"),
            change_note=data.get("change_note", "")
        )


class VersionManager:
    """文档版本管理器"""
    
    def __init__(self):
        self.versions: Dict[str, List[VersionInfo]] = {}  # document_id -> [versions]
        self._load_versions()
    
    def _load_versions(self):
        """加载已保存的版本信息"""
        version_path = os.path.join(settings.VECTOR_DB_PATH, "versions")
        if os.path.exists(version_path):
            for filename in os.listdir(version_path):
                if filename.endswith(".json"):
                    document_id = filename.replace(".json", "")
                    filepath = os.path.join(version_path, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.versions[document_id] = [VersionInfo.from_dict(v) for v in data]
                    except Exception as e:
                        logger.error(f"加载版本文件失败: {filepath}, 错误: {str(e)}")
    
    def _save_versions(self):
        """保存版本信息"""
        version_path = os.path.join(settings.VECTOR_DB_PATH, "versions")
        os.makedirs(version_path, exist_ok=True)
        
        for document_id, versions in self.versions.items():
            filepath = os.path.join(version_path, f"{document_id}.json")
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([v.to_dict() for v in versions], f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"保存版本文件失败: {filepath}, 错误: {str(e)}")
    
    def create_version(self, document_id: str, content: str, metadata: Dict[str, Any],
                      created_by: str = "system", change_note: str = "") -> VersionInfo:
        """
        创建新版本
        
        Args:
            document_id: 文档ID
            content: 文档内容
            metadata: 元数据
            created_by: 创建者
            change_note: 变更说明
        
        Returns:
            版本信息
        """
        # 获取最新版本号
        if document_id in self.versions:
            latest_version = self.get_latest_version(document_id)
            version_number = latest_version.version_number + 1 if latest_version else 1
            parent_version_id = latest_version.version_id if latest_version else None
        else:
            version_number = 1
            parent_version_id = None
        
        version_id = generate_id()
        version = VersionInfo(
            version_id=version_id,
            document_id=document_id,
            content=content,
            metadata=metadata,
            created_at=get_timestamp(),
            created_by=created_by,
            version_number=version_number,
            parent_version_id=parent_version_id,
            change_note=change_note
        )
        
        if document_id not in self.versions:
            self.versions[document_id] = []
        
        self.versions[document_id].append(version)
        
        # 保存到文件
        self._save_versions()
        
        logger.info(f"创建文档版本: document_id={document_id}, version={version_number}")
        
        return version
    
    def get_version(self, document_id: str, version_number: int) -> Optional[VersionInfo]:
        """
        获取指定版本
        
        Args:
            document_id: 文档ID
            version_number: 版本号
        
        Returns:
            版本信息，如果不存在返回None
        """
        if document_id not in self.versions:
            return None
        
        for version in self.versions[document_id]:
            if version.version_number == version_number:
                return version
        
        return None
    
    def get_latest_version(self, document_id: str) -> Optional[VersionInfo]:
        """
        获取最新版本
        
        Args:
            document_id: 文档ID
        
        Returns:
            最新版本信息，如果不存在返回None
        """
        if document_id not in self.versions or not self.versions[document_id]:
            return None
        
        return max(self.versions[document_id], key=lambda v: v.version_number)
    
    def get_all_versions(self, document_id: str) -> List[VersionInfo]:
        """
        获取文档的所有版本
        
        Args:
            document_id: 文档ID
        
        Returns:
            版本列表，按版本号升序排列
        """
        if document_id not in self.versions:
            return []
        
        return sorted(self.versions[document_id], key=lambda v: v.version_number)
    
    def compare_versions(self, document_id: str, version1: int, version2: int) -> Dict[str, Any]:
        """
        比较两个版本的差异
        
        Args:
            document_id: 文档ID
            version1: 版本号1
            version2: 版本号2
        
        Returns:
            差异信息
        """
        v1 = self.get_version(document_id, version1)
        v2 = self.get_version(document_id, version2)
        
        if not v1 or not v2:
            return {"success": False, "error": "版本不存在"}
        
        # 简单的差异比较
        diff = {
            "document_id": document_id,
            "version1": version1,
            "version2": version2,
            "version1_content_length": len(v1.content),
            "version2_content_length": len(v2.content),
            "content_changed": v1.content != v2.content,
            "metadata_changed": v1.metadata != v2.metadata,
            "version1_created_at": v1.created_at,
            "version2_created_at": v2.created_at,
            "version1_created_by": v1.created_by,
            "version2_created_by": v2.created_by
        }
        
        # 如果内容有变化，提供简单的差异摘要
        if diff["content_changed"]:
            diff["diff_summary"] = self._generate_diff_summary(v1.content, v2.content)
        
        return {"success": True, "diff": diff}
    
    def _generate_diff_summary(self, content1: str, content2: str) -> str:
        """生成差异摘要"""
        lines1 = content1.split('\n')
        lines2 = content2.split('\n')
        
        added_lines = len(lines2) - len(lines1)
        content_diff = abs(len(content2) - len(content1))
        
        summary_parts = []
        if added_lines > 0:
            summary_parts.append(f"新增 {added_lines} 行")
        elif added_lines < 0:
            summary_parts.append(f"删除 {abs(added_lines)} 行")
        
        if content_diff > 0:
            summary_parts.append(f"内容变化 {content_diff} 字符")
        elif content_diff < 0:
            summary_parts.append(f"内容减少 {abs(content_diff)} 字符")
        
        return "; ".join(summary_parts) if summary_parts else "内容无实质性变化"
    
    def restore_version(self, document_id: str, version_number: int) -> Optional[VersionInfo]:
        """
        恢复到指定版本
        
        Args:
            document_id: 文档ID
            version_number: 版本号
        
        Returns:
            恢复后的版本信息
        """
        version = self.get_version(document_id, version_number)
        
        if not version:
            return None
        
        # 创建新版本，内容与旧版本相同
        new_version = self.create_version(
            document_id=document_id,
            content=version.content,
            metadata=version.metadata,
            created_by="system",
            change_note=f"从版本 {version_number} 恢复"
        )
        
        return new_version
    
    def delete_version(self, document_id: str, version_number: int) -> bool:
        """
        删除指定版本
        
        Args:
            document_id: 文档ID
            version_number: 版本号
        
        Returns:
            是否删除成功
        """
        if document_id not in self.versions:
            return False
        
        versions = self.versions[document_id]
        original_length = len(versions)
        
        self.versions[document_id] = [
            v for v in versions if v.version_number != version_number
        ]
        
        if len(self.versions[document_id]) < original_length:
            self._save_versions()
            logger.info(f"删除文档版本: document_id={document_id}, version={version_number}")
            return True
        
        return False
    
    def get_version_count(self, document_id: str) -> int:
        """
        获取文档的版本数量
        
        Args:
            document_id: 文档ID
        
        Returns:
            版本数量
        """
        return len(self.versions.get(document_id, []))
    
    def list_documents_with_versions(self) -> List[str]:
        """
        获取有版本记录的文档ID列表
        
        Returns:
            文档ID列表
        """
        return list(self.versions.keys())


# 全局实例
version_manager = VersionManager()


# 便捷函数
def create_document_version(document_id: str, content: str, metadata: Dict[str, Any],
                           created_by: str = "system", change_note: str = "") -> VersionInfo:
    """创建文档版本"""
    return version_manager.create_version(document_id, content, metadata, created_by, change_note)


def get_document_version(document_id: str, version_number: int) -> Optional[VersionInfo]:
    """获取指定版本"""
    return version_manager.get_version(document_id, version_number)


def get_document_latest_version(document_id: str) -> Optional[VersionInfo]:
    """获取最新版本"""
    return version_manager.get_latest_version(document_id)


def compare_document_versions(document_id: str, version1: int, version2: int) -> Dict[str, Any]:
    """比较两个版本"""
    return version_manager.compare_versions(document_id, version1, version2)
