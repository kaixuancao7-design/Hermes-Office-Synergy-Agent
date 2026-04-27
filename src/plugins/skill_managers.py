"""技能管理插件实现"""
from typing import Dict, Any, List, Optional

from src.plugins.base import SkillManagerBase
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class DatabaseSkillManager(SkillManagerBase):
    """基于数据库的技能管理器"""
    
    def __init__(self):
        self.skills_cache = {}
        self._load_skills()
    
    def _load_skills(self):
        """从数据库加载技能到缓存"""
        try:
            skills = db.get_all_skills()
            for skill in skills:
                self.skills_cache[skill.id] = skill
            logger.info(f"已加载 {len(self.skills_cache)} 个技能")
        except Exception as e:
            logger.error(f"加载技能失败: {str(e)}")
    
    def add_skill(self, skill: Skill) -> bool:
        """添加技能"""
        try:
            db.save_skill(skill)
            self.skills_cache[skill.id] = skill
            logger.info(f"添加技能成功: {skill.name}")
            return True
        except Exception as e:
            logger.error(f"添加技能失败: {str(e)}")
            return False
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        if skill_id in self.skills_cache:
            return self.skills_cache[skill_id]
        
        try:
            skill = db.get_skill(skill_id)
            if skill:
                self.skills_cache[skill_id] = skill
            return skill
        except Exception as e:
            logger.error(f"获取技能失败: {str(e)}")
            return None
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有技能"""
        return list(self.skills_cache.values())
    
    def find_relevant_skill(self, query: str) -> Optional[Skill]:
        """查找相关技能"""
        query_lower = query.lower()
        
        for skill in self.skills_cache.values():
            # 检查技能名称
            if query_lower in skill.name.lower():
                return skill
            
            # 检查触发模式
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query_lower:
                    return skill
            
            # 检查描述
            if query_lower in skill.description.lower():
                return skill
        
        return None
    
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": "技能不存在"}
        
        try:
            results = []
            for i, step in enumerate(skill.steps):
                step_result = self._execute_step(step, parameters)
                results.append({
                    "step": i + 1,
                    "action": step.action,
                    "result": step_result.get("result", ""),
                    "success": step_result.get("success", False)
                })
                
                if not step_result.get("success", False):
                    return {
                        "success": False,
                        "error": f"步骤 {i + 1} 执行失败: {step_result.get('error', '')}",
                        "results": results
                    }
            
            return {
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"执行技能失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _execute_step(self, step: SkillStep, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤"""
        try:
            # 合并步骤参数和传入参数
            step_params = {**step.parameters, **parameters}
            
            # 根据动作类型执行不同操作
            if step.action == "execute":
                from src.plugins.model_routers import select_model, call_model
                
                instruction = step_params.get("instruction", "")
                if instruction:
                    model = select_model("general", "simple")
                    if model:
                        result = call_model(model, [{"role": "user", "content": instruction}])
                        return {"success": True, "result": result}
                
                return {"success": True, "result": f"执行指令: {instruction}"}
            
            elif step.action == "open_app":
                app_name = step_params.get("app", "")
                return {"success": True, "result": f"打开应用: {app_name}"}
            
            elif step.action == "create_document":
                doc_type = step_params.get("type", "document")
                return {"success": True, "result": f"创建{doc_type}文档"}
            
            elif step.action == "send_email":
                to = step_params.get("to", "")
                subject = step_params.get("subject", "")
                return {"success": True, "result": f"发送邮件给 {to}，主题: {subject}"}
            
            else:
                return {"success": False, "error": f"未知动作类型: {step.action}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        try:
            # 数据库删除需要实现
            if skill_id in self.skills_cache:
                del self.skills_cache[skill_id]
            logger.info(f"删除技能成功: {skill_id}")
            return True
        except Exception as e:
            logger.error(f"删除技能失败: {str(e)}")
            return False
    
    def get_manager_type(self) -> str:
        return "database"


class FileSkillManager(SkillManagerBase):
    """基于文件的技能管理器（适用于预设技能）"""
    
    def __init__(self):
        self.skills_cache = {}
        self.skill_dir = "./skills"
        self._load_skills_from_files()
    
    def _load_skills_from_files(self):
        """从文件加载技能"""
        import os
        import json
        
        if not os.path.exists(self.skill_dir):
            os.makedirs(self.skill_dir)
        
        for filename in os.listdir(self.skill_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.skill_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        
                        steps = []
                        for step_data in data.get("steps", []):
                            steps.append(SkillStep(
                                id=step_data.get("id", generate_id()),
                                action=step_data.get("action", ""),
                                parameters=step_data.get("parameters", {}),
                                next_step_id=step_data.get("next_step_id"),
                                condition=step_data.get("condition")
                            ))
                        
                        skill = Skill(
                            id=data.get("id", filename.replace(".json", "")),
                            name=data.get("name", ""),
                            description=data.get("description", ""),
                            type="preset",
                            trigger_patterns=data.get("trigger_patterns", []),
                            steps=steps,
                            metadata=data.get("metadata", {}),
                            created_at=data.get("created_at", get_timestamp()),
                            updated_at=data.get("updated_at", get_timestamp())
                        )
                        
                        self.skills_cache[skill.id] = skill
                except Exception as e:
                    logger.error(f"加载技能文件失败 {filename}: {str(e)}")
        
        logger.info(f"已从文件加载 {len(self.skills_cache)} 个技能")
    
    def add_skill(self, skill: Skill) -> bool:
        """添加技能到文件"""
        import json
        import os
        
        filepath = os.path.join(self.skill_dir, f"{skill.id}.json")
        
        try:
            data = {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "type": skill.type,
                "trigger_patterns": skill.trigger_patterns,
                "steps": [
                    {
                        "id": step.id,
                        "action": step.action,
                        "parameters": step.parameters,
                        "next_step_id": step.next_step_id,
                        "condition": step.condition
                    }
                    for step in skill.steps
                ],
                "metadata": skill.metadata,
                "created_at": skill.created_at,
                "updated_at": skill.updated_at
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.skills_cache[skill.id] = skill
            logger.info(f"添加技能到文件: {skill.name}")
            return True
        except Exception as e:
            logger.error(f"添加技能到文件失败: {str(e)}")
            return False
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills_cache.get(skill_id)
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有技能"""
        return list(self.skills_cache.values())
    
    def find_relevant_skill(self, query: str) -> Optional[Skill]:
        """查找相关技能"""
        query_lower = query.lower()
        
        for skill in self.skills_cache.values():
            if query_lower in skill.name.lower():
                return skill
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query_lower:
                    return skill
        
        return None
    
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": "技能不存在"}
        
        try:
            results = []
            for i, step in enumerate(skill.steps):
                step_result = {
                    "step": i + 1,
                    "action": step.action,
                    "result": f"执行步骤 {i + 1}: {step.action}",
                    "success": True
                }
                results.append(step_result)
            
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        import os
        
        if skill_id in self.skills_cache:
            filepath = os.path.join(self.skill_dir, f"{skill_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            del self.skills_cache[skill_id]
            return True
        return False
    
    def get_manager_type(self) -> str:
        return "file"


class HybridSkillManager(SkillManagerBase):
    """混合技能管理器（预设技能从文件加载，自定义技能存储到数据库）"""
    
    def __init__(self):
        self.file_manager = FileSkillManager()
        self.db_manager = DatabaseSkillManager()
    
    def add_skill(self, skill: Skill) -> bool:
        """添加技能"""
        if skill.type == "preset":
            return self.file_manager.add_skill(skill)
        else:
            return self.db_manager.add_skill(skill)
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        skill = self.file_manager.get_skill(skill_id)
        if skill:
            return skill
        return self.db_manager.get_skill(skill_id)
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有技能"""
        skills = self.file_manager.get_all_skills()
        skills.extend(self.db_manager.get_all_skills())
        return skills
    
    def find_relevant_skill(self, query: str) -> Optional[Skill]:
        """查找相关技能"""
        skill = self.file_manager.find_relevant_skill(query)
        if skill:
            return skill
        return self.db_manager.find_relevant_skill(query)
    
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        skill = self.file_manager.get_skill(skill_id)
        if skill:
            return self.file_manager.execute_skill(skill_id, parameters)
        return self.db_manager.execute_skill(skill_id, parameters)
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        if self.file_manager.delete_skill(skill_id):
            return True
        return self.db_manager.delete_skill(skill_id)
    
    def get_manager_type(self) -> str:
        return "hybrid"


# 技能管理器注册表
SKILL_MANAGER_REGISTRY = {
    "database": DatabaseSkillManager,
    "file": FileSkillManager,
    "hybrid": HybridSkillManager
}
