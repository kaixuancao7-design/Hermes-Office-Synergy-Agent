from typing import List, Dict, Any, Optional
from src.types import Task, TaskStep, ToolCall, Intent, Skill
from src.data.database import db
from src.engine.intent_recognition import intent_recognizer
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.plugins.model_routers import select_model, call_model

logger = get_logger("engine")


class TaskPlanner:
    def __init__(self):
        self.skills = self._load_skills()
    
    def _load_skills(self) -> List[Skill]:
        return db.get_all_skills()
    
    def plan(self, user_id: str, intent: Intent, context: str) -> Task:
        task_id = generate_id()
        steps: List[TaskStep] = []
        
        skill = self._find_matching_skill(intent)
        
        if skill:
            steps = self._skill_to_steps(skill)
        else:
            steps = self._generate_steps(intent, context)
        
        return Task(
            id=task_id,
            user_id=user_id,
            goal=intent.entities.get("task", context),
            status="pending",
            steps=steps,
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
    
    def _find_matching_skill(self, intent: Intent) -> Optional[Skill]:
        for skill in self.skills:
            for pattern in skill.trigger_patterns:
                if pattern.lower() in intent.entities.get("task", "").lower():
                    return skill
        return None
    
    def _skill_to_steps(self, skill: Skill) -> List[TaskStep]:
        steps: List[TaskStep] = []
        
        for step in skill.steps:
            tool_call = None
            if step.action == "execute":
                tool_call = ToolCall(
                    tool_id="execute_script",
                    parameters=step.parameters
                )
            
            steps.append(TaskStep(
                id=step.id,
                description=step.parameters.get("instruction", step.action),
                status="pending",
                tool_call=tool_call
            ))
        
        return steps
    
    def _generate_steps(self, intent: Intent, context: str) -> List[TaskStep]:
        prompt = f"""
        Generate a step-by-step plan for the following task:
        
        Intent: {intent.type}
        Confidence: {intent.confidence}
        Entities: {intent.entities}
        Context: {context}
        
        Provide a numbered list of steps. Each step should be:
        1. Actionable
        2. Specific
        3. In order
        
        Format:
        1. Step 1 description
        2. Step 2 description
        ...
        """
        
        model = select_model("task_planning", "medium")
        if not model:
            return [TaskStep(
                id=generate_id(),
                description="Execute task",
                status="pending"
            )]
        
        try:
            response = call_model(model, [{"role": "user", "content": prompt}])
            return self._parse_steps(response)
        except Exception as e:
            logger.error(f"Step generation failed: {str(e)}")
            return [TaskStep(
                id=generate_id(),
                description="Execute task",
                status="pending"
            )]
    
    def _parse_steps(self, response: str) -> List[TaskStep]:
        steps: List[TaskStep] = []
        lines = response.strip().split("\n")
        
        for line in lines:
            match = line.strip().split(".", 1)
            if len(match) == 2:
                steps.append(TaskStep(
                    id=generate_id(),
                    description=match[1].strip(),
                    status="pending"
                ))
        
        return steps
    
    def execute_step(self, task: Task, step_index: int) -> Task:
        if step_index >= len(task.steps):
            return task
        
        step = task.steps[step_index]
        step.status = "in_progress"
        
        try:
            if step.tool_call:
                result = self._execute_tool(step.tool_call)
                step.result = result
                step.status = "completed"
            else:
                step.result = "Step executed"
                step.status = "completed"
        except Exception as e:
            step.error = str(e)
            step.status = "failed"
        
        task.updated_at = get_timestamp()
        
        if all(s.status == "completed" for s in task.steps):
            task.status = "completed"
        elif any(s.status == "failed" for s in task.steps):
            task.status = "failed"
        else:
            task.status = "in_progress"
        
        return task
    
    def _execute_tool(self, tool_call: ToolCall) -> str:
        from src.plugins import get_tool_executor
        executor = get_tool_executor()
        if executor:
            return executor.execute(tool_call.tool_id, tool_call.parameters)
        return f"工具执行器未初始化"
    
    def revise_plan(self, task: Task, feedback: str) -> Task:
        prompt = f"""
        Current task plan:
        {task.goal}
        
        Steps:
        {[f"{i+1}. {s.description} ({s.status})" for i, s in enumerate(task.steps)]}
        
        Feedback: {feedback}
        
        Please revise the plan. Provide new steps if needed.
        """
        
        model = select_model("task_revision", "medium")
        if not model:
            return task
        
        try:
            response = call_model(model, [{"role": "user", "content": prompt}])
            task.steps = self._parse_steps(response)
            task.status = "pending"
            task.updated_at = get_timestamp()
            return task
        except Exception as e:
            logger.error(f"Plan revision failed: {str(e)}")
            return task


task_planner = TaskPlanner()
