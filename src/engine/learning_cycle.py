from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep, Intent
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.plugins import get_model_router, get_skill_manager
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("engine")


class LearningCycle:
    def __init__(self):
        self.pending_corrections: List[Dict[str, Any]] = []
    
    def capture_correction(self, user_id: str, original_output: str, corrected_output: str, task_context: str) -> None:
        correction = {
            "user_id": user_id,
            "original": original_output,
            "corrected": corrected_output,
            "context": task_context,
            "timestamp": get_timestamp()
        }
        self.pending_corrections.append(correction)
        
        if len(self.pending_corrections) >= 5:
            self.process_corrections()
    
    def process_corrections(self) -> None:
        for correction in self.pending_corrections:
            self._distill_skill(correction)
        
        self.pending_corrections = []
    
    def _distill_skill(self, correction: Dict[str, Any]) -> None:
        differences = self._find_differences(
            correction["original"],
            correction["corrected"]
        )
        
        if not differences:
            return
        
        prompt = f"""
        Analyze the following correction and extract a reusable skill:
        
        Context: {correction["context"]}
        
        Original Output:
        {correction["original"]}
        
        Corrected Output:
        {correction["corrected"]}
        
        Differences: {differences}
        
        Please provide:
        1. Skill Name
        2. Description
        3. Trigger Patterns (when to use this skill)
        4. Step-by-step instructions
        """
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            logger.error("Model router not available")
            return
        
        model = model_router.select_model("skill_distillation", "medium")
        if not model:
            logger.error("No suitable model found for skill distillation")
            return
        
        try:
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            self._parse_and_save_skill(response, correction["user_id"])
        except Exception as e:
            logger.error(f"Skill distillation failed: {str(e)}")
    
    def _find_differences(self, original: str, corrected: str) -> str:
        lines_original = original.split("\n")
        lines_corrected = corrected.split("\n")
        
        differences = []
        max_len = max(len(lines_original), len(lines_corrected))
        
        for i in range(max_len):
            orig_line = lines_original[i] if i < len(lines_original) else ""
            corr_line = lines_corrected[i] if i < len(lines_corrected) else ""
            
            if orig_line != corr_line:
                differences.append(f"Line {i+1}: '{orig_line}' -> '{corr_line}'")
        
        return "\n".join(differences)
    
    def _parse_and_save_skill(self, response: str, user_id: str) -> None:
        lines = response.strip().split("\n")
        
        skill_name = ""
        description = ""
        trigger_patterns = []
        steps = []
        
        current_section = None
        
        for line in lines:
            if line.startswith("1. Skill Name"):
                current_section = "name"
                skill_name = line.replace("1. Skill Name", "").strip().replace(":", "").strip()
            elif line.startswith("2. Description"):
                current_section = "description"
                description = line.replace("2. Description", "").strip().replace(":", "").strip()
            elif line.startswith("3. Trigger Patterns"):
                current_section = "triggers"
            elif line.startswith("4. Step-by-step"):
                current_section = "steps"
            elif current_section == "triggers" and line.strip():
                trigger_patterns.append(line.strip("- ").strip())
            elif current_section == "steps" and line.strip():
                step_match = line.strip().split(".", 1)
                if len(step_match) == 2:
                    steps.append(SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": step_match[1].strip()},
                        next_step_id=None
                    ))
        
        if skill_name and steps:
            skill = Skill(
                id=generate_id(),
                name=skill_name,
                description=description,
                type="learned",
                trigger_patterns=trigger_patterns,
                steps=steps,
                metadata={"user_id": user_id},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            )
            
            # 使用插件系统的技能管理器
            skill_manager = get_skill_manager()
            if skill_manager:
                skill_manager.add_skill(skill)
            else:
                db.save_skill(skill)
            
            logger.info(f"Created learned skill: {skill_name}")
    
    def suggest_skill_creation(self, user_id: str, task_description: str) -> Optional[Skill]:
        prompt = f"""
        Analyze the following task and determine if it should be saved as a reusable skill:
        
        Task: {task_description}
        
        If this is a repetitive or complex task that could benefit from automation, provide:
        1. Skill Name
        2. Description
        3. Trigger Patterns
        4. Step-by-step instructions
        
        If this is a one-time task, respond with: NOT_A_SKILL
        """
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            return None
        
        model = model_router.select_model("skill_analysis", "simple")
        if not model:
            return None
        
        try:
            response = model_router.call_model(model, [{"role": "user", "content": prompt}])
            
            if response.strip() == "NOT_A_SKILL":
                return None
            
            return self._parse_and_save_skill(response, user_id)
        except Exception as e:
            logger.error(f"Skill suggestion failed: {str(e)}")
            return None


learning_cycle = LearningCycle()
