"""示例自定义技能 — 覆盖企业办公多样化场景

这些技能通过 `create_sample_skills()` 脚本按需创建为 custom 类型技能，
作为 preset 技能的补充，展示更细分的场景用法。

运行方式:
    python -m src.examples.sample_skills
"""

from src.skills import skill_manager
from src.utils import generate_id, get_timestamp


def create_sample_skills():
    """创建示例自定义技能（非 PPT 聚焦，覆盖更广泛的企业场景）"""

    sample_skills = [
        # ===== 项目管理 =====
        {
            "name": "项目进展同步",
            "description": "根据项目任务列表自动生成项目进展报告，包含里程碑状态、风险项和下一步计划",
            "trigger_patterns": ["项目进展", "项目状态", "project status", "里程碑", "项目汇报"],
            "steps": [
                {
                    "id": "step1",
                    "action": "memory_search",
                    "description": "检索项目相关历史记录",
                    "parameters": {
                        "query": "项目任务 进展 里程碑 完成状态",
                        "limit": 10,
                        "instruction": "搜索项目相关的历史对话和任务记录，获取最新进展信息。"
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "document_search",
                    "description": "搜索项目相关文档",
                    "parameters": {
                        "query": "项目计划 需求文档 设计文档",
                        "limit": 5,
                        "instruction": "在知识库中搜索项目相关文档，获取项目背景和需求信息。"
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "analyze",
                    "description": "分析项目状态和风险",
                    "parameters": {
                        "instruction": (
                            "分析项目当前状态：\n"
                            "1. 各里程碑完成情况（按计划/延期/已完成）\n"
                            "2. 识别风险项和阻塞点\n"
                            "3. 资源使用情况评估"
                        )
                    },
                    "next_step_id": "step4"
                },
                {
                    "id": "step4",
                    "action": "generate_report",
                    "description": "生成项目进展报告",
                    "parameters": {
                        "instruction": (
                            "生成结构化项目报告：\n"
                            "## 项目概览\n"
                            "## 里程碑状态（表格）\n"
                            "## 风险与问题\n"
                            "## 下周计划\n"
                            "## 需要决策的事项"
                        ),
                        "output_format": "markdown",
                        "save_to_workspace": True
                    }
                }
            ]
        },

        # ===== 合同与法务 =====
        {
            "name": "合同要点提取",
            "description": "从合同中提取关键条款（金额、期限、违约责任、保密条款等），生成要点摘要",
            "trigger_patterns": [
                "合同审查", "合同要点", "审合同", "合同条款",
                "contract review", "合同摘要", "看合同"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "feishu_file_read",
                    "description": "读取合同文件",
                    "parameters": {
                        "instruction": "读取合同文件内容（PDF/DOCX），获取完整文本。",
                        "fallback_tool": "file_operations"
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "extract",
                    "description": "提取合同关键信息",
                    "parameters": {
                        "instruction": (
                            "提取以下关键条款信息（如合同中有则标注具体条款号）：\n"
                            "1. 合同金额与支付方式\n"
                            "2. 合同期限与终止条件\n"
                            "3. 违约责任条款\n"
                            "4. 保密与数据保护条款\n"
                            "5. 知识产权归属\n"
                            "6. 争议解决方式\n"
                            "7. 其他非常规/需关注的条款"
                        )
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "generate_report",
                    "description": "生成合同审查摘要",
                    "parameters": {
                        "instruction": (
                            "生成合同摘要报告：\n"
                            "## 合同基本信息\n"
                            "## 关键条款摘要（表格）\n"
                            "## 风险提示（⚠️ 需要关注的条款）\n"
                            "## 建议修改项\n"
                            "## 签署建议"
                        ),
                        "output_format": "markdown"
                    }
                }
            ]
        },

        # ===== 招聘与HR =====
        {
            "name": "面试问题生成",
            "description": "根据职位描述自动生成结构化面试问题和评估维度",
            "trigger_patterns": [
                "面试问题", "面试题库", "招聘面试", "面试准备",
                "interview questions", "出面试题", "面试评估"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "analyze",
                    "description": "分析职位要求",
                    "parameters": {
                        "instruction": (
                            "分析职位描述，提取关键能力要求：\n"
                            "1. 技术硬技能（编程语言、工具、框架）\n"
                            "2. 业务/领域知识\n"
                            "3. 软技能（沟通、领导力、解决问题）\n"
                            "4. 文化契合度方向"
                        )
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "generate_questions",
                    "description": "生成分类面试问题",
                    "parameters": {
                        "instruction": (
                            "根据能力维度生成面试问题：\n"
                            "1. 技术能力（4-6 题，含实操/白板题）\n"
                            "2. 项目经验（3-4 题，行为面试法 STAR）\n"
                            "3. 问题解决（2-3 题，案例分析型）\n"
                            "4. 团队协作（2-3 题，情景模拟型）\n"
                            "每题标注：考察点、期望回答要点、评分标准（1-5分）"
                        )
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "format",
                    "description": "生成面试评估表",
                    "parameters": {
                        "instruction": (
                            "生成面试评估表：\n"
                            "## 候选人信息\n"
                            "## 面试问题清单（按考察维度分组）\n"
                            "## 评分表（含评分维度与权重）\n"
                            "## 面试官备注区"
                        ),
                        "output_format": "markdown",
                        "save_to_workspace": True
                    }
                }
            ]
        },

        # ===== 运营与营销 =====
        {
            "name": "产品文案撰写",
            "description": "为产品或功能撰写多场景营销文案（官网、社媒、应用商店、邮件）",
            "trigger_patterns": [
                "产品文案", "宣传文案", "推广文案", "营销文案",
                "产品介绍", "功能描述", "广告文案", "copywriting"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "analyze",
                    "description": "分析产品特性和目标受众",
                    "parameters": {
                        "instruction": (
                            "分析产品信息：\n"
                            "1. 目标用户画像\n"
                            "2. 核心卖点与差异化优势\n"
                            "3. 使用场景与痛点\n"
                            "4. 品牌调性（专业/活泼/温暖/科技感）"
                        )
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "generate_copy",
                    "description": "撰写多场景文案",
                    "parameters": {
                        "instruction": (
                            "为以下场景撰写文案：\n"
                            "1. 官网首页（标题+副标题+3 段介绍，200 字）\n"
                            "2. 应用商店描述（标题+简介+亮点列表，500 字）\n"
                            "3. 社交媒体帖子（3 个版本：正式/轻松/故事型）\n"
                            "4. 营销邮件（主题+正文+CTA，300 字）\n"
                            "统一品牌调性，适配各平台风格。"
                        )
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "review",
                    "description": "文案质量检查",
                    "parameters": {
                        "instruction": (
                            "检查文案质量：\n"
                            "1. 是否符合平台字数限制\n"
                            "2. 是否有明确的 Call-to-Action\n"
                            "3. 是否突出了差异化优势\n"
                            "4. 文案的可读性评分（Flesch 或等价指标）"
                        )
                    }
                }
            ]
        },

        # ===== 技术支持 =====
        {
            "name": "故障排查引导",
            "description": "根据用户描述的故障现象，逐步排查定位根因并提供解决方案",
            "trigger_patterns": [
                "报错了", "出问题了", "不工作", "故障", "bug",
                "怎么修复", "排查", "troubleshoot", "debug", "报错"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "analyze",
                    "description": "分析故障现象",
                    "parameters": {
                        "instruction": (
                            "分析用户描述的故障：\n"
                            "1. 复述故障现象（确认理解正确）\n"
                            "2. 列出可能的原因（按概率排序）\n"
                            "3. 确定排查优先级"
                        )
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "document_search",
                    "description": "搜索知识库中的解决方案",
                    "parameters": {
                        "query": "故障现象关键词 + 解决方案",
                        "limit": 5,
                        "instruction": "搜索内部知识库中是否有类似问题的解决方案或文档。"
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "diagnose",
                    "description": "逐步排查诊断",
                    "parameters": {
                        "instruction": (
                            "提供逐步排查步骤：\n"
                            "1. 每步明确检查什么、期望结果是什么\n"
                            "2. 如果结果不符合预期，下一步是什么\n"
                            "3. 标记需要用户确认的步骤\n"
                            "4. 安全提示（如涉及生产环境操作）"
                        )
                    },
                    "next_step_id": "step4"
                },
                {
                    "id": "step4",
                    "action": "suggest_solution",
                    "description": "提供解决方案",
                    "parameters": {
                        "instruction": (
                            "根据诊断结果提供：\n"
                            "1. 具体修复步骤（可直接复制执行）\n"
                            "2. 修复后如何验证问题已解决\n"
                            "3. 预防措施（避免再次发生）\n"
                            "4. 如果无法解决，提供进一步支持渠道"
                        )
                    }
                }
            ]
        },

        # ===== 日程与会议管理 =====
        {
            "name": "会议议程策划",
            "description": "根据会议目标策划完整议程，包含时间分配、讨论要点和预期产出",
            "trigger_patterns": [
                "会议议程", "会议策划", "开会准备", "meeting agenda",
                "会议安排", "议程安排", "怎么开会", "组织会议"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "analyze",
                    "description": "分析会议目标",
                    "parameters": {
                        "instruction": (
                            "确定会议要素：\n"
                            "1. 会议目标（决策/讨论/汇报/脑暴）\n"
                            "2. 参会人员与角色\n"
                            "3. 预计时长\n"
                            "4. 期望产出"
                        )
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "plan_agenda",
                    "description": "策划会议议程",
                    "parameters": {
                        "instruction": (
                            "策划详细议程：\n"
                            "1. 每个议题的时长分配（精确到分钟）\n"
                            "2. 每个议题的讨论方式和引导问题\n"
                            "3. 需要的会前准备材料\n"
                            "4. 中间安排休息和缓冲时间"
                        )
                    },
                    "next_step_id": "step3"
                },
                {
                    "id": "step3",
                    "action": "generate_agenda",
                    "description": "生成会议议程文档",
                    "parameters": {
                        "instruction": (
                            "生成会议议程文档：\n"
                            "## 会议信息\n"
                            "## 会议目标\n"
                            "## 议程安排（时间表）\n"
                            "## 会前准备（需提前阅读的材料）\n"
                            "## 会议规则（如：不打断、限时发言等）\n"
                            "## 预期产出与后续行动"
                        ),
                        "output_format": "markdown",
                        "save_to_workspace": True
                    }
                }
            ]
        },

        # ===== 个人效率 =====
        {
            "name": "信息摘要速览",
            "description": "快速将长文/长邮件/长聊天记录压缩为3-5句话的核心摘要",
            "trigger_patterns": [
                "太长不看", "简要总结", "快速摘要", "要点速览",
                "帮我概括", "三句话总结", "TLDR", "tldr", "简洁版"
            ],
            "steps": [
                {
                    "id": "step1",
                    "action": "feishu_file_read",
                    "description": "读取原始内容",
                    "parameters": {
                        "instruction": "读取需要摘要的原文。用户在消息中直接粘贴的内容则跳过。",
                        "fallback_tool": "file_operations"
                    },
                    "next_step_id": "step2"
                },
                {
                    "id": "step2",
                    "action": "summarize",
                    "description": "生成简洁摘要",
                    "parameters": {
                        "instruction": (
                            "生成 3-5 句话的核心摘要，要求：\n"
                            "1. 第一句：一句话说清楚主要内容\n"
                            "2. 中间 1-3 句：关键要点或数据\n"
                            "3. 最后一句：结论或建议行动\n"
                            "4. 如果原文超过 5000 字，先分段总结再合并\n"
                            "5. 标注原文长度和阅读时间节省比例"
                        ),
                        "max_sentences": 5,
                        "output_format": "markdown"
                    }
                }
            ]
        }
    ]

    for skill_data in sample_skills:
        skill_manager.create_custom_skill(
            user_id="system",
            name=skill_data["name"],
            description=skill_data["description"],
            steps=skill_data["steps"],
            trigger_patterns=skill_data.get("trigger_patterns", [])
        )

    print(f"✅ {len(sample_skills)} 个示例技能创建完成！")
    print()
    for i, s in enumerate(sample_skills, 1):
        print(f"  {i}. {s['name']} — {s['description'][:50]}...")


if __name__ == "__main__":
    create_sample_skills()
