"""向量数据迁移工具 - 用于切换 embedding 模型后重新生成向量"""
import os
import json
from typing import List, Dict, Any, Optional
from src.config import settings
from src.logging_config import get_logger
from src.plugins.embedding_services import get_embedding_service
from src.plugins.memory_stores import ChromaMemory

logger = get_logger("vector_migration")

class VectorMigrationTool:
    """向量数据迁移工具"""
    
    def __init__(self):
        self.metadata_file = os.path.join(settings.VECTOR_DB_PATH, "embedding_metadata.json")
        self.current_model = None
    
    def get_current_embedding_model(self) -> Optional[str]:
        """获取当前使用的 embedding 模型"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    return metadata.get("embedding_model")
            except Exception as e:
                logger.error(f"读取 embedding 元数据失败: {str(e)}")
                return None
        return None
    
    def save_embedding_model(self, model_name: str):
        """保存当前使用的 embedding 模型信息"""
        metadata = {
            "embedding_model": model_name,
            "last_updated": os.path.getmtime(__file__)
        }
        os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存 embedding 模型信息: {model_name}")
    
    def check_migration_needed(self) -> bool:
        """检查是否需要迁移向量数据"""
        saved_model = self.get_current_embedding_model()
        current_config = settings.EMBEDDING_SERVICE_TYPE
        
        if saved_model is None:
            # 首次使用，保存当前配置
            self.save_embedding_model(current_config)
            return False
        
        if saved_model != current_config:
            logger.warning(f"检测到 embedding 模型变更: {saved_model} -> {current_config}")
            return True
        
        return False
    
    def backup_vector_data(self, backup_path: Optional[str] = None) -> str:
        """备份当前向量数据"""
        import shutil
        
        if backup_path is None:
            backup_path = f"{settings.VECTOR_DB_PATH}_backup_{os.path.getmtime(settings.VECTOR_DB_PATH)}"
        
        if os.path.exists(settings.VECTOR_DB_PATH):
            shutil.copytree(settings.VECTOR_DB_PATH, backup_path)
            logger.info(f"向量数据已备份到: {backup_path}")
        
        return backup_path
    
    def export_documents(self) -> List[Dict[str, Any]]:
        """导出所有文档数据（不含向量）"""
        try:
            chroma = ChromaMemory()
            all_docs = []
            
            for collection_name, collection in chroma.collections.items():
                try:
                    result = collection.get()
                    if result["ids"]:
                        for i, doc_id in enumerate(result["ids"]):
                            all_docs.append({
                                "id": doc_id,
                                "collection": collection_name,
                                "content": result["documents"][i],
                                "metadata": result["metadatas"][i] if result["metadatas"] else {}
                            })
                except Exception as e:
                    logger.warning(f"导出集合 {collection_name} 失败: {str(e)}")
            
            logger.info(f"成功导出 {len(all_docs)} 条文档")
            return all_docs
        except Exception as e:
            logger.error(f"导出文档失败: {str(e)}")
            return []
    
    def regenerate_vectors(self, documents: List[Dict[str, Any]]) -> bool:
        """使用新的 embedding 模型重新生成向量"""
        try:
            # 获取新的 embedding 服务
            embedding_service = get_embedding_service(settings.EMBEDDING_SERVICE_TYPE)
            if not embedding_service:
                logger.error("无法获取新的 embedding 服务")
                return False
            
            # 创建新的 Chroma 实例（使用新模型）
            new_chroma = ChromaMemory(embedding_service=settings.EMBEDDING_SERVICE_TYPE)
            
            # 按集合分组文档
            docs_by_collection = {}
            for doc in documents:
                collection = doc["collection"]
                if collection not in docs_by_collection:
                    docs_by_collection[collection] = []
                docs_by_collection[collection].append(doc)
            
            # 重新生成向量并插入
            total_count = 0
            for collection_name, docs in docs_by_collection.items():
                if collection_name not in new_chroma.collections:
                    new_chroma.collections[collection_name] = new_chroma.client.get_or_create_collection(collection_name)
                
                collection = new_chroma.collections[collection_name]
                
                # 批量处理
                ids = [doc["id"] for doc in docs]
                contents = [doc["content"] for doc in docs]
                metadatas = [doc["metadata"] for doc in docs]
                
                # 使用新模型生成向量并插入（Chroma会自动处理）
                collection.add(
                    ids=ids,
                    documents=contents,
                    metadatas=metadatas
                )
                
                total_count += len(docs)
                logger.info(f"集合 {collection_name} 已重新生成 {len(docs)} 条向量")
            
            # 保存新的模型信息
            self.save_embedding_model(settings.EMBEDDING_SERVICE_TYPE)
            logger.info(f"成功重新生成 {total_count} 条向量")
            return True
            
        except Exception as e:
            logger.error(f"重新生成向量失败: {str(e)}")
            return False
    
    def migrate(self, backup: bool = True) -> bool:
        """执行完整的向量数据迁移流程"""
        logger.info("开始向量数据迁移...")
        
        # 1. 备份数据
        backup_path = None
        if backup:
            backup_path = self.backup_vector_data()
            logger.info(f"数据已备份到: {backup_path}")
        
        try:
            # 2. 导出文档
            documents = self.export_documents()
            if not documents:
                logger.warning("没有可迁移的文档数据")
                self.save_embedding_model(settings.EMBEDDING_SERVICE_TYPE)
                return True
            
            # 3. 删除旧数据
            import shutil
            if os.path.exists(settings.VECTOR_DB_PATH):
                shutil.rmtree(settings.VECTOR_DB_PATH)
                logger.info("已删除旧的向量数据")
            
            # 4. 重新生成向量
            success = self.regenerate_vectors(documents)
            
            if success:
                logger.info("向量数据迁移完成")
                return True
            else:
                # 迁移失败，恢复备份
                if backup_path and os.path.exists(backup_path):
                    shutil.rmtree(settings.VECTOR_DB_PATH, ignore_errors=True)
                    shutil.copytree(backup_path, settings.VECTOR_DB_PATH)
                    logger.warning("迁移失败，已恢复备份")
                return False
                
        except Exception as e:
            logger.error(f"迁移过程发生错误: {str(e)}")
            # 恢复备份
            if backup_path and os.path.exists(backup_path):
                import shutil
                shutil.rmtree(settings.VECTOR_DB_PATH, ignore_errors=True)
                shutil.copytree(backup_path, settings.VECTOR_DB_PATH)
                logger.warning("迁移失败，已恢复备份")
            return False
    
    def run_auto_migration(self):
        """自动检测并执行迁移"""
        if self.check_migration_needed():
            logger.info("检测到 embedding 模型变更，自动执行迁移...")
            success = self.migrate()
            if success:
                logger.info("自动迁移成功")
            else:
                logger.error("自动迁移失败，请手动处理")
        else:
            logger.info("embedding 模型未变更，无需迁移")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="向量数据迁移工具")
    parser.add_argument("--check", action="store_true", help="检查是否需要迁移")
    parser.add_argument("--migrate", action="store_true", help="执行迁移")
    parser.add_argument("--backup", action="store_true", help="仅备份数据")
    parser.add_argument("--no-backup", action="store_true", help="迁移时不备份")
    
    args = parser.parse_args()
    
    tool = VectorMigrationTool()
    
    if args.check:
        if tool.check_migration_needed():
            print("需要迁移向量数据")
        else:
            print("无需迁移")
    
    elif args.backup:
        backup_path = tool.backup_vector_data()
        print(f"数据已备份到: {backup_path}")
    
    elif args.migrate:
        backup = not args.no_backup
        success = tool.migrate(backup=backup)
        if success:
            print("迁移成功")
        else:
            print("迁移失败")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()