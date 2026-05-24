"""任务规划引擎"""
from typing import Dict, Any, List, Optional
from src.types import Task, TaskStep, Intent
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("engine")


class TaskPlanner:
    """任务规划器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
    
    def plan(self, user_id: str, intent: Intent, context: str) -> Task:
        """根据意图和上下文生成任务计划"""
        task = Task(
            id=generate_id(),
            user_id=user_id,
            intent=intent.type,
            context=context,
            steps=[],
            status="created",
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        # 根据意图类型生成步骤
        steps = self._generate_steps(intent, context)
        task.steps = steps
        
        self.tasks[task.id] = task
        
        logger.info(f"任务规划完成: task_id={task.id}, intent={intent.type}, steps={len(steps)}")
        
        return task
    
    def _generate_steps(self, intent: Intent, context: str) -> List[TaskStep]:
        """根据意图生成任务步骤"""
        steps = []
        
        intent_type = intent.type
        
        # PPT生成相关任务
        if intent_type == "ppt_generate_outline":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="分析用户需求，提取关键信息",
                    status="pending",
                    task_type="analysis"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT大纲",
                    status="pending",
                    task_type="outline_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="确认大纲内容",
                    status="pending",
                    task_type="confirmation"
                )
            ]
        
        elif intent_type == "ppt_generate_from_outline":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="解析PPT大纲",
                    status="pending",
                    task_type="parsing"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT内容",
                    status="pending",
                    task_type="content_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="导出PPT文件",
                    status="pending",
                    task_type="export"
                )
            ]
        
        elif intent_type == "ppt_generate_from_content":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="读取文档内容",
                    status="pending",
                    task_type="document_read"
                ),
                TaskStep(
                    id=generate_id(),
                    description="分析文档结构",
                    status="pending",
                    task_type="analysis"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT大纲",
                    status="pending",
                    task_type="outline_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT内容",
                    status="pending",
                    task_type="content_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="导出PPT文件",
                    status="pending",
                    task_type="export"
                )
            ]
        
        elif intent_type == "ppt_custom_generate":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="询问用户PPT主题和要求",
                    status="pending",
                    task_type="query"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT大纲",
                    status="pending",
                    task_type="outline_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="确认大纲",
                    status="pending",
                    task_type="confirmation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成PPT内容",
                    status="pending",
                    task_type="content_generation"
                ),
                TaskStep(
                    id=generate_id(),
                    description="导出PPT文件",
                    status="pending",
                    task_type="export"
                )
            ]
        
        elif intent_type == "summarization":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="收集需要总结的内容",
                    status="pending",
                    task_type="collection"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成总结",
                    status="pending",
                    task_type="summarization"
                )
            ]
        
        elif intent_type == "document_analysis":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="读取文档内容",
                    status="pending",
                    task_type="document_read"
                ),
                TaskStep(
                    id=generate_id(),
                    description="分析文档结构和内容",
                    status="pending",
                    task_type="analysis"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成分析报告",
                    status="pending",
                    task_type="report_generation"
                )
            ]
        
        elif intent_type == "question_answering":
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="理解用户问题",
                    status="pending",
                    task_type="analysis"
                ),
                TaskStep(
                    id=generate_id(),
                    description="搜索相关知识",
                    status="pending",
                    task_type="search"
                ),
                TaskStep(
                    id=generate_id(),
                    description="生成回答",
                    status="pending",
                    task_type="generation"
                )
            ]
        
        else:
            # 默认步骤
            steps = [
                TaskStep(
                    id=generate_id(),
                    description="分析用户请求",
                    status="pending",
                    task_type="analysis"
                ),
                TaskStep(
                    id=generate_id(),
                    description="执行任务",
                    status="pending",
                    task_type="execution"
                ),
                TaskStep(
                    id=generate_id(),
                    description="返回结果",
                    status="pending",
                    task_type="result"
                )
            ]
        
        return steps
    
    def execute_step(self, task: Task, step_index: int) -> Task:
        """执行任务的指定步骤"""
        if step_index < 0 or step_index >= len(task.steps):
            return task
        
        step = task.steps[step_index]
        
        try:
            logger.info(f"执行任务步骤: task_id={task.id}, step={step_index}, description={step.description}")
            
            step.status = "running"
            step.start_time = get_timestamp()
            
            # 模拟步骤执行
            import time
            time.sleep(0.1)
            
            step.status = "completed"
            step.result = f"步骤 '{step.description}' 执行成功"
            step.end_time = get_timestamp()
            
            # 检查是否所有步骤都完成
            if all(s.status == "completed" for s in task.steps):
                task.status = "completed"
            
            task.updated_at = get_timestamp()
            
            logger.info(f"步骤执行完成: task_id={task.id}, step={step_index}")
            
        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            step.end_time = get_timestamp()
            task.status = "failed"
            task.updated_at = get_timestamp()
            
            logger.error(f"步骤执行失败: task_id={task.id}, step={step_index}, error={str(e)}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id].status = "cancelled"
        return True


# 全局实例
task_planner = TaskPlanner()
