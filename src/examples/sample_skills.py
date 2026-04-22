from src.skills import skill_manager
from src.utils import generate_id, get_timestamp


def create_sample_skills():
    sample_skills = [
        {
            "name": "周报生成",
            "description": "自动生成工作周报，包含本周工作内容、成果和下周计划",
            "steps": [
                {
                    "action": "execute",
                    "parameters": {"instruction": "收集本周完成的工作任务"},
                    "next_step_id": "step2"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "整理工作成果和数据"},
                    "next_step_id": "step3"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "制定下周工作计划"},
                    "next_step_id": "step4"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "生成Markdown格式的周报文档"}
                }
            ]
        },
        {
            "name": "会议纪要",
            "description": "根据会议内容生成详细的会议纪要",
            "steps": [
                {
                    "action": "execute",
                    "parameters": {"instruction": "提取会议主题和参与人员"},
                    "next_step_id": "step2"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "整理讨论要点和决策事项"},
                    "next_step_id": "step3"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "记录行动项和责任人"}
                }
            ]
        },
        {
            "name": "PPT大纲",
            "description": "根据主题生成PPT大纲",
            "steps": [
                {
                    "action": "execute",
                    "parameters": {"instruction": "分析演示主题和目标受众"},
                    "next_step_id": "step2"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "确定PPT结构和章节"},
                    "next_step_id": "step3"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "生成详细的PPT大纲"}
                }
            ]
        },
        {
            "name": "竞品分析",
            "description": "分析竞争对手的产品和市场策略",
            "steps": [
                {
                    "action": "execute",
                    "parameters": {"instruction": "收集竞品产品信息"},
                    "next_step_id": "step2"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "分析竞品功能和优势"},
                    "next_step_id": "step3"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "对比自身产品定位"},
                    "next_step_id": "step4"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "生成竞品分析报告"}
                }
            ]
        },
        {
            "name": "数据可视化",
            "description": "将数据转换为图表",
            "steps": [
                {
                    "action": "execute",
                    "parameters": {"instruction": "分析数据结构和需求"},
                    "next_step_id": "step2"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "选择合适的图表类型"},
                    "next_step_id": "step3"
                },
                {
                    "action": "execute",
                    "parameters": {"instruction": "生成图表并导出"}
                }
            ]
        }
    ]
    
    for skill_data in sample_skills:
        skill_manager.create_custom_skill(
            user_id="system",
            name=skill_data["name"],
            description=skill_data["description"],
            steps=skill_data["steps"]
        )
    
    print("Sample skills created successfully!")


if __name__ == "__main__":
    create_sample_skills()
