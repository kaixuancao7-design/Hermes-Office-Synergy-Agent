"""Claude风格的技能执行引擎"""

from typing import Dict, Any, Optional, List
from src.types import Skill
from src.tools.claude_tool import ClaudeToolExecutor, ToolCall
from src.skills.skill_context import SkillExecutionContext, ExecutionStatus, skill_execution_manager
from src.logging_config import get_logger

logger = get_logger("skill.executor")


class ClaudeSkillExecutor:
    """Claude风格的技能执行引擎"""

    def __init__(self):
        self._tool_executor = ClaudeToolExecutor()

    def execute_skill(self, skill: Skill, user_id: str, input_data: Dict[str, Any]) -> SkillExecutionContext:
        """执行技能"""
        # 创建执行上下文
        context = skill_execution_manager.create_execution(
            skill_id=skill.id,
            user_id=user_id,
            input_data=input_data
        )

        # 添加额外的上下文信息
        input_data["context"] = {
            "user_id": user_id,
            "skill_id": skill.id,
            "execution_id": context.execution_id
        }

        # 开始执行
        context.set_status(ExecutionStatus.RUNNING)
        return self._execute_steps(skill, context, input_data)

    def continue_execution(self, execution_id: str, user_response: str) -> SkillExecutionContext:
        """继续暂停的执行"""
        context = skill_execution_manager.get_execution(execution_id)
        if not context:
            raise ValueError(f"执行上下文不存在: {execution_id}")

        if context.status != ExecutionStatus.PAUSED:
            raise ValueError(f"执行未暂停: {execution_id}")

        # 处理用户响应
        input_data = context.input_data.copy()
        input_data["_user_response"] = user_response
        input_data["_user_approved"] = user_response.lower() in ["是", "yes", "确认", "y", "好"]

        # 继续执行
        context.set_status(ExecutionStatus.RUNNING)

        # 获取技能
        from src.services.skill_discovery import skill_discovery
        skill = skill_discovery.get_skill_by_name(context.skill_id)
        if not skill:
            context.set_error(f"技能不存在: {context.skill_id}")
            return context

        return self._execute_steps(skill, context, input_data, start_step=context.current_step)

    def _execute_steps(self, skill: Skill, context: SkillExecutionContext, input_data: Dict[str, Any], start_step: int = 0) -> SkillExecutionContext:
        """执行技能步骤"""
        output_data = {}

        for idx, step in enumerate(skill.steps[start_step:], start=start_step):
            context.current_step = idx

            # 解析参数（支持模板变量）
            params = self._resolve_params(step.parameters, input_data, output_data)

            # 记录工具调用
            logger.info(f"执行步骤 {idx}: {step.action}")

            # 检查是否需要等待确认
            if step.condition == "await_confirmation":
                # 执行工具获取结果
                result = self._tool_executor.call_tool_raw(step.action, params)

                if result.get("success"):
                    output_data[step.id] = result
                    context.add_tool_call(step.action, params, result)

                    # 设置暂停状态
                    context.set_status(ExecutionStatus.PAUSED)
                    context.output_data = output_data

                    # 获取确认提示
                    confirmation_prompt = step.parameters.get("_prompt", "请确认是否继续？")
                    context.output_data["_confirmation_prompt"] = confirmation_prompt

                    return context
                else:
                    context.set_error(result.get("error", "工具执行失败"))
                    return context

            # 执行工具
            result = self._tool_executor.call_tool_raw(step.action, params)

            if result.get("success"):
                output_data[step.id] = result
                context.add_tool_call(step.action, params, result)
                logger.info(f"步骤 {idx} 完成: {step.action}")
            else:
                context.set_error(result.get("error", f"步骤 {idx} 执行失败"))
                return context

        # 完成执行
        context.set_status(ExecutionStatus.COMPLETED)
        context.output_data = output_data

        return context

    def _resolve_params(self, params: Dict[str, Any], input_data: Dict[str, Any], output_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数中的模板变量"""
        resolved = {}

        for key, value in params.items():
            if isinstance(value, str):
                resolved_value = value

                # 替换输入变量 {{input.xxx}}
                resolved_value = self._replace_template(resolved_value, input_data, "input")

                # 替换输出变量 {{output.xxx}}
                resolved_value = self._replace_template(resolved_value, output_data, "output")

                # 替换上下文变量 {{context.xxx}}
                context_data = input_data.get("context", {})
                resolved_value = self._replace_template(resolved_value, context_data, "context")

                resolved[key] = resolved_value
            else:
                resolved[key] = value

        return resolved

    def _replace_template(self, text: str, data: Dict[str, Any], prefix: str) -> str:
        """替换模板变量"""
        if not text or not data:
            return text

        for key, value in data.items():
            placeholder = f"{{{{{prefix}.{key}}}}}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))

        return text

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行状态"""
        context = skill_execution_manager.get_execution(execution_id)
        if context:
            return context.to_dict()
        return None


# 全局实例
claude_skill_executor = ClaudeSkillExecutor()