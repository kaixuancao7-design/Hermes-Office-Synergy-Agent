"""技能工作流引擎 - 支持技能编排和条件执行"""

from typing import List, Dict, Any, Callable, Optional
from src.logging_config import get_logger
from src.tools.registry import execute_tool
from src.types import Skill

logger = get_logger("skill.workflow")


class SkillWorkflowStep:
    """技能工作流步骤"""
    
    def __init__(self, 
                 tool_name: str, 
                 params: Dict[str, Any],
                 condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
                 next_step: Optional[str] = None,
                 output_key: Optional[str] = None):
        """
        Args:
            tool_name: 工具名称
            params: 工具参数（支持模板变量，如 {{result.key}}）
            condition: 执行条件，返回True时执行
            next_step: 下一步骤名称
            output_key: 输出结果存储键名
        """
        self.tool_name = tool_name
        self.params = params
        self.condition = condition
        self.next_step = next_step
        self.output_key = output_key
    
    def _resolve_params(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数中的模板变量"""
        resolved = {}
        for key, value in self.params.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                for ctx_key, ctx_value in context.items():
                    placeholder = f"{{{{{ctx_key}}}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(ctx_value))
            resolved[key] = value
        return resolved


class SkillWorkflowEngine:
    """技能工作流引擎"""
    
    def __init__(self, steps: Optional[List[SkillWorkflowStep]] = None):
        self.steps = steps or []
        self.step_index = {step.tool_name: step for step in self.steps}
    
    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行工作流"""
        if context is None:
            context = {}
        
        for step in self.steps:
            if step.condition and not step.condition(context):
                logger.info(f"步骤 {step.tool_name} 条件不满足，跳过")
                continue
            
            params = step._resolve_params(context)
            logger.info(f"执行步骤: {step.tool_name}")
            
            result = execute_tool(step.tool_name, params)
            
            if step.output_key:
                context[step.output_key] = result
            else:
                context[step.tool_name] = result
            
            if step.next_step:
                logger.info(f"设置下一步跳转: {step.next_step}")
        
        return context
    
    def add_step(self, step: SkillWorkflowStep):
        """添加步骤"""
        self.steps.append(step)
        self.step_index[step.tool_name] = step
    
    def remove_step(self, tool_name: str):
        """移除步骤"""
        self.steps = [s for s in self.steps if s.tool_name != tool_name]
        self.step_index.pop(tool_name, None)
    
    def from_skill(self, skill: Skill) -> 'SkillWorkflowEngine':
        """从技能创建工作流"""
        steps = []
        for idx, step in enumerate(skill.steps):
            tool_name = step.tool_name
            params = step.parameters
            
            # 添加简单的条件逻辑
            condition = None
            if idx > 0:
                prev_step = skill.steps[idx - 1]
                condition = lambda ctx, prev=prev_step.tool_name: prev in ctx
            
            steps.append(SkillWorkflowStep(
                tool_name=tool_name,
                params=params,
                condition=condition,
                output_key=f"step_{idx}_result"
            ))
        
        return SkillWorkflowEngine(steps)


def create_ppt_workflow() -> SkillWorkflowEngine:
    """创建PPT生成工作流"""
    steps = [
        SkillWorkflowStep(
            tool_name="feishu_file_read",
            params={"file_key": "{{file_key}}", "user_id": "{{user_id}}"},
            output_key="file_content"
        ),
        SkillWorkflowStep(
            tool_name="generate_outline",
            params={"content": "{{file_content}}", "title": "{{title}}"},
            output_key="outline"
        ),
        SkillWorkflowStep(
            tool_name="generate_ppt_from_outline",
            params={"title": "{{title}}", "outline": "{{outline}}"},
            output_key="ppt_path"
        )
    ]
    
    return SkillWorkflowEngine(steps)
