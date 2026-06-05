"""预设技能管理器 — 覆盖企业办公协同全场景

技能设计原则：
1. 每个技能绑定真实可用的工具（tool ID）或 LLM 原生能力（action type）
2. 步骤之间通过 next_step_id 形成有序工作流
3. 触发模式覆盖中英文双语，匹配用户自然语言请求
4. 场景覆盖：文档处理、沟通协作、知识管理、数据分析、任务管理、会议管理
"""

from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class PresetSkillsManager:
    """预设技能管理器 — 12 个技能覆盖企业办公全场景"""

    def __init__(self):
        self.preset_skills = []

    def initialize_preset_skills(self):
        """初始化预设技能（仅当技能不存在时写入）"""
        skills = self._get_default_skills()

        for skill_data in skills:
            # 幂等：如果技能已存在则跳过
            existing = db.get_skill(skill_data['id'])
            if existing:
                logger.debug(f"预设技能已存在，跳过: {skill_data['name']}")
                continue

            skill = Skill(
                id=skill_data['id'],
                name=skill_data['name'],
                description=skill_data['description'],
                type='preset',
                trigger_patterns=skill_data['trigger_patterns'],
                steps=[SkillStep(**s) for s in skill_data['steps']],
                metadata=skill_data.get('metadata', {}),
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by='system',
                version='1.1.0'
            )

            db.save_skill(skill)
            self.preset_skills.append(skill)

        logger.info(f"初始化了 {len(self.preset_skills)} 个预设技能（共 {len(skills)} 个定义）")

    # =========================================================================
    # 默认技能定义
    # =========================================================================

    def _get_default_skills(self) -> List[Dict[str, Any]]:
        """获取默认技能列表 — 12 个企业办公核心场景

        技能分类:
          A. 文档与内容处理 (3): 文档摘要, 内容润色, 文档翻译
          B. 沟通与协作 (3):   邮件草稿, 会议纪要, IM消息撰写
          C. 知识与研究 (2):   知识库问答, 竞品分析
          D. 数据与报表 (2):   数据分析, 图表生成
          E. 任务与项目 (1):   周报生成
          F. 演示与展示 (1):   PPT生成
        """
        return [
            # ===== A. 文档与内容处理 =====
            {
                'id': 'summarize-document',
                'name': '文档摘要',
                'description': '读取并总结文档内容，提取关键信息、核心观点和结论',
                'trigger_patterns': [
                    '总结文档', '文档摘要', '这篇文章说了什么', '概括内容',
                    '总结一下', '帮我读一下', '文件讲了什么', 'summarize document',
                ],
                'metadata': {
                    'category': 'document',
                    'estimated_steps': 2,
                    'tools_used': ['feishu_file_read', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'read-source',
                        'action': 'feishu_file_read',
                        'description': '读取源文档内容（飞书文件或本地文件）',
                        'parameters': {
                            'instruction': '读取用户指定的文档内容。如果是飞书文件使用 feishu_file_read，本地文件使用 file_operations read。',
                            'fallback_tool': 'file_operations',
                        },
                        'next_step_id': 'summarize-content',
                    },
                    {
                        'id': 'summarize-content',
                        'action': 'summarize',
                        'description': '提取文档核心观点与关键结论',
                        'parameters': {
                            'instruction': (
                                '对文档内容进行结构化总结，包括：\n'
                                '1. 文档主题与目的（1-2 句）\n'
                                '2. 核心观点（3-5 条，按重要性排列）\n'
                                '3. 关键数据与事实\n'
                                '4. 结论或建议\n'
                                '5. 待确认的问题（如有）'
                            ),
                            'output_format': 'markdown',
                        },
                    },
                ],
            },
            {
                'id': 'content-polish',
                'name': '内容润色',
                'description': '优化文本的表达、结构和风格，提升专业度和可读性',
                'trigger_patterns': [
                    '润色', '改写', '优化表达', '改进措辞', 'polish',
                    '帮我改一下', '措辞优化', '表达优化', '文字润色',
                    '改得好一点', '修辞', '润色文字',
                ],
                'metadata': {
                    'category': 'document',
                    'estimated_steps': 3,
                    'tools_used': ['file_operations'],
                },
                'steps': [
                    {
                        'id': 'get-original',
                        'action': 'file_operations',
                        'description': '获取原始文本内容',
                        'parameters': {
                            'operation': 'read',
                            'instruction': '读取需要润色的原始文本。如果用户在消息中直接提供了文本则跳过此步骤。',
                        },
                        'next_step_id': 'analyze-issues',
                    },
                    {
                        'id': 'analyze-issues',
                        'action': 'analyze',
                        'description': '分析原文的表达问题',
                        'parameters': {
                            'instruction': (
                                '分析原文存在的问题：\n'
                                '1. 逻辑结构是否清晰\n'
                                '2. 用词是否准确专业\n'
                                '3. 句式是否流畅\n'
                                '4. 是否存在冗余或歧义\n'
                                '5. 风格是否符合目标场景'
                            ),
                        },
                        'next_step_id': 'rewrite-polished',
                    },
                    {
                        'id': 'rewrite-polished',
                        'action': 'rewrite',
                        'description': '生成润色后的版本并对比展示',
                        'parameters': {
                            'instruction': (
                                '生成润色后的文本，并展示修改对照：\n'
                                '1. 输出润色后的完整文本\n'
                                '2. 列出主要修改点（原文 → 修改后）\n'
                                '3. 说明修改理由（简洁、专业、流畅）'
                            ),
                            'output_format': 'markdown',
                            'show_diff': True,
                        },
                    },
                ],
            },
            {
                'id': 'document-translate',
                'name': '文档翻译',
                'description': '将文档内容在中文和英文之间进行专业翻译',
                'trigger_patterns': [
                    '翻译', 'translate', '中译英', '英译中', '汉译英',
                    '翻译成中文', '翻译成英文', 'translate to Chinese', 'translate to English',
                ],
                'metadata': {
                    'category': 'document',
                    'estimated_steps': 2,
                    'tools_used': ['feishu_file_read', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'read-source',
                        'action': 'feishu_file_read',
                        'description': '读取需要翻译的文档内容',
                        'parameters': {
                            'instruction': '读取用户指定的文档内容。用户直接在消息中提供的文本则跳过此步骤。',
                            'fallback_tool': 'file_operations',
                        },
                        'next_step_id': 'translate-content',
                    },
                    {
                        'id': 'translate-content',
                        'action': 'translate',
                        'description': '执行专业翻译并保留格式',
                        'parameters': {
                            'instruction': (
                                '翻译要求：\n'
                                '1. 保持原文格式（标题层级、列表、段落）\n'
                                '2. 专业术语准确，使用行业标准译法\n'
                                '3. 语句流畅自然，符合目标语言习惯\n'
                                '4. 保留原文中的数据、日期、人名等关键信息不变\n'
                                '5. 翻译后附上术语对照表（如有专业术语）'
                            ),
                            'output_format': 'markdown',
                        },
                    },
                ],
            },

            # ===== B. 沟通与协作 =====
            {
                'id': 'email-draft',
                'name': '邮件草稿',
                'description': '根据上下文生成专业邮件，支持多种场景（商务沟通、汇报、通知等）',
                'trigger_patterns': [
                    '写邮件', '邮件草稿', '邮件', 'email', 'draft email',
                    '回复邮件', '商务邮件', '通知邮件', '汇报邮件',
                ],
                'metadata': {
                    'category': 'communication',
                    'estimated_steps': 3,
                    'tools_used': ['memory_search'],
                },
                'steps': [
                    {
                        'id': 'understand-context',
                        'action': 'memory_search',
                        'description': '检索历史对话上下文，了解邮件背景',
                        'parameters': {
                            'query': '邮件相关的上下文和历史信息',
                            'limit': 5,
                            'instruction': '搜索用户历史中与当前邮件主题相关的对话，获取背景信息。',
                        },
                        'next_step_id': 'compose-email',
                    },
                    {
                        'id': 'compose-email',
                        'action': 'generate_email',
                        'description': '撰写邮件正文',
                        'parameters': {
                            'instruction': (
                                '撰写专业邮件，包含以下要素：\n'
                                '1. 主题行（Subject）：简洁明确，10 词以内\n'
                                '2. 称呼：根据场景选择合适的称谓\n'
                                '3. 正文：开门见山，段落分明，3-5 段为宜\n'
                                '4. 行动项：明确需要收件人做什么\n'
                                '5. 签名：包含发件人基本信息\n'
                                '根据场景调整语气：商务正式 / 内部沟通 / 客户邮件'
                            ),
                            'email_type': 'auto',  # auto | formal | internal | client
                            'output_format': 'markdown',
                        },
                        'next_step_id': 'review-email',
                    },
                    {
                        'id': 'review-email',
                        'action': 'review',
                        'description': '检查邮件质量',
                        'parameters': {
                            'instruction': (
                                '邮件发送前检查清单：\n'
                                '1. 收件人是否正确\n'
                                '2. 主题行是否清晰\n'
                                '3. 附件是否提及\n'
                                '4. 语气是否得体\n'
                                '5. 是否有拼写或格式错误'
                            ),
                        },
                    },
                ],
            },
            {
                'id': 'meeting-minutes',
                'name': '会议纪要',
                'description': '根据会议录音/记录生成结构化会议纪要，提取决策和行动项',
                'trigger_patterns': [
                    '会议纪要', '会议记录', '会议总结', 'meeting minutes',
                    '会议内容', '开会纪要', '整理会议', 'meeting summary',
                    '会后总结', '会议回顾',
                ],
                'metadata': {
                    'category': 'communication',
                    'estimated_steps': 4,
                    'tools_used': ['feishu_file_read', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'read-meeting-source',
                        'action': 'feishu_file_read',
                        'description': '读取会议记录或录音转写内容',
                        'parameters': {
                            'instruction': '读取会议相关文件（录音转写文本、会议记录、聊天记录等）。用户在消息中直接提供的内容则跳过。',
                            'fallback_tool': 'file_operations',
                        },
                        'next_step_id': 'extract-meta',
                    },
                    {
                        'id': 'extract-meta',
                        'action': 'extract',
                        'description': '提取会议基本信息',
                        'parameters': {
                            'instruction': (
                                '提取会议基本信息：\n'
                                '1. 会议主题 / 名称\n'
                                '2. 日期和时间\n'
                                '3. 参会人员\n'
                                '4. 会议类型（决策会/讨论会/汇报会/评审会）'
                            ),
                        },
                        'next_step_id': 'summarize-discussion',
                    },
                    {
                        'id': 'summarize-discussion',
                        'action': 'summarize',
                        'description': '整理讨论要点与决策',
                        'parameters': {
                            'instruction': (
                                '按主题整理会议讨论内容：\n'
                                '1. 每个议题的讨论要点（3-5 条）\n'
                                '2. 达成的共识与决策\n'
                                '3. 未解决的问题 / 待讨论事项\n'
                                '4. 关键数据与引用'
                            ),
                            'output_format': 'markdown',
                        },
                        'next_step_id': 'extract-actions',
                    },
                    {
                        'id': 'extract-actions',
                        'action': 'extract_action_items',
                        'description': '提取行动项并分配责任人',
                        'parameters': {
                            'instruction': (
                                '提取行动项清单，每条包含：\n'
                                '1. 任务描述（具体可执行）\n'
                                '2. 责任人\n'
                                '3. 截止日期\n'
                                '4. 优先级（P0/P1/P2）\n'
                                '以表格形式输出行动项。'
                            ),
                            'output_format': 'table',
                        },
                    },
                ],
            },
            {
                'id': 'im-message-compose',
                'name': 'IM消息撰写',
                'description': '为企业IM（飞书/钉钉/企微）撰写各类工作消息',
                'trigger_patterns': [
                    '发消息', '写消息', '通知大家', '群公告', 'IM消息',
                    '工作群消息', '发通知', '群发', 'draft message',
                ],
                'metadata': {
                    'category': 'communication',
                    'estimated_steps': 2,
                    'tools_used': [],
                },
                'steps': [
                    {
                        'id': 'compose-im-message',
                        'action': 'generate_message',
                        'description': '撰写IM消息',
                        'parameters': {
                            'instruction': (
                                '撰写企业IM消息，注意以下规范：\n'
                                '1. 消息类型：[通知/提醒/询问/分享/庆祝]\n'
                                '2. 篇幅：群消息 ≤300 字，私聊 ≤500 字\n'
                                '3. 结构：标题/重点 → 正文 → @相关人员 → 行动要求\n'
                                '4. 善用 emoji 和换行提升可读性\n'
                                '5. 避免过度正式，保持亲切专业的团队风格'
                            ),
                            'message_type': 'auto',  # auto | notification | reminder | question | share | celebration
                        },
                        'next_step_id': 'format-for-platform',
                    },
                    {
                        'id': 'format-for-platform',
                        'action': 'format_message',
                        'description': '根据目标平台格式化消息',
                        'parameters': {
                            'instruction': (
                                '根据目标平台调整消息格式：\n'
                                '- 飞书：支持富文本、@用户、表情回复\n'
                                '- 钉钉：支持 Markdown、@用户\n'
                                '- 企微：支持 Markdown、@用户\n'
                                '- 微信群：纯文本 + emoji，避免 Markdown'
                            ),
                            'platform': 'auto',  # auto | feishu | dingtalk | wecom | wechat
                        },
                    },
                ],
            },

            # ===== C. 知识与研究 =====
            {
                'id': 'knowledge-qa',
                'name': '知识库问答',
                'description': '基于企业内部知识库（向量数据库）进行语义搜索与问答',
                'trigger_patterns': [
                    '知识库', '公司文档', '内部资料', '查一下', '搜索文档',
                    '有没有相关文档', '帮我查', 'knowledge base', 'search docs',
                    '找一下文档', '公司有规定吗', '之前怎么做的',
                ],
                'metadata': {
                    'category': 'knowledge',
                    'estimated_steps': 3,
                    'tools_used': ['document_search', 'web_search'],
                },
                'steps': [
                    {
                        'id': 'search-knowledge-base',
                        'action': 'document_search',
                        'description': '在向量知识库中语义搜索相关内容',
                        'parameters': {
                            'query': '用户的问题或搜索关键词',
                            'limit': 5,
                            'instruction': '使用用户问题在内部知识库中进行语义搜索，获取最相关的文档片段。',
                        },
                        'next_step_id': 'evaluate-results',
                    },
                    {
                        'id': 'evaluate-results',
                        'action': 'evaluate',
                        'description': '评估搜索结果的相关性和充分性',
                        'parameters': {
                            'instruction': (
                                '评估搜索结果：\n'
                                '1. 是否找到直接相关的信息\n'
                                '2. 信息是否足够回答用户问题\n'
                                '3. 是否需要补充外部搜索'
                            ),
                        },
                        'next_step_id': 'synthesize-answer',
                    },
                    {
                        'id': 'synthesize-answer',
                        'action': 'synthesize',
                        'description': '综合知识库结果生成答案',
                        'parameters': {
                            'instruction': (
                                '基于知识库搜索结果生成答案：\n'
                                '1. 直接回答用户问题\n'
                                '2. 引用具体文档来源（文件名/章节）\n'
                                '3. 标注答案的置信度（高/中/低）\n'
                                '4. 如果知识库信息不足，诚实说明并建议其他途径'
                            ),
                            'output_format': 'markdown',
                            'cite_sources': True,
                        },
                    },
                ],
            },
            {
                'id': 'competitive-analysis',
                'name': '竞品分析',
                'description': '收集竞品信息并进行多维度对比分析，生成分析报告',
                'trigger_patterns': [
                    '竞品分析', '竞争分析', '竞品调研', '市场分析',
                    'competitor analysis', '竞品对比', '行业对比',
                    '竞争对手', '市场调研', '对标分析',
                ],
                'metadata': {
                    'category': 'knowledge',
                    'estimated_steps': 4,
                    'tools_used': ['web_search', 'document_search'],
                },
                'steps': [
                    {
                        'id': 'define-scope',
                        'action': 'analyze',
                        'description': '明确分析范围和维度',
                        'parameters': {
                            'instruction': (
                                '确定竞品分析的范围：\n'
                                '1. 目标产品/公司\n'
                                '2. 竞品列表（用户指定或自动识别 3-5 个）\n'
                                '3. 分析维度：功能、定价、市场定位、用户体验、技术架构'
                            ),
                        },
                        'next_step_id': 'collect-info',
                    },
                    {
                        'id': 'collect-info',
                        'action': 'web_search',
                        'description': '收集竞品公开信息',
                        'parameters': {
                            'query': '竞品名称 + 分析维度关键词',
                            'limit': 10,
                            'instruction': '搜索各竞品的产品信息、市场动态、用户评价、融资新闻等公开资料。',
                        },
                        'next_step_id': 'compare-analyze',
                    },
                    {
                        'id': 'compare-analyze',
                        'action': 'analyze',
                        'description': '多维度对比分析',
                        'parameters': {
                            'instruction': (
                                '按维度进行对比分析：\n'
                                '1. 功能对比表（✅/⚠️/❌）\n'
                                '2. 定价策略对比\n'
                                '3. SWOT 分析（优势/劣势/机会/威胁）\n'
                                '4. 差异化建议'
                            ),
                            'output_format': 'markdown',
                        },
                        'next_step_id': 'generate-report',
                    },
                    {
                        'id': 'generate-report',
                        'action': 'generate_report',
                        'description': '生成竞品分析报告',
                        'parameters': {
                            'instruction': (
                                '生成结构化竞品分析报告：\n'
                                '1. 执行摘要（Executive Summary）\n'
                                '2. 分析范围与方法\n'
                                '3. 各竞品详细分析\n'
                                '4. 对比矩阵\n'
                                '5. 战略建议与行动计划'
                            ),
                            'output_format': 'markdown',
                            'save_to_workspace': True,
                        },
                    },
                ],
            },

            # ===== D. 数据与报表 =====
            {
                'id': 'data-analysis',
                'name': '数据分析',
                'description': '对表格数据进行统计分析，发现趋势和洞察',
                'trigger_patterns': [
                    '数据分析', '分析数据', '统计分析', '数据洞察',
                    'data analysis', '趋势分析', '数据报表', '分析表格',
                    '数据汇总', '透视分析',
                ],
                'metadata': {
                    'category': 'data',
                    'estimated_steps': 4,
                    'tools_used': ['feishu_file_read', 'code_execution', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'load-data',
                        'action': 'feishu_file_read',
                        'description': '加载数据源（Excel/CSV/飞书文档）',
                        'parameters': {
                            'instruction': '读取用户提供的数据文件。支持 .xlsx、.xls、.csv、飞书在线表格。',
                            'fallback_tool': 'file_operations',
                        },
                        'next_step_id': 'explore-data',
                    },
                    {
                        'id': 'explore-data',
                        'action': 'code_execution',
                        'description': '数据探索与清洗',
                        'parameters': {
                            'code': (
                                'import pandas as pd\n'
                                'import numpy as np\n'
                                '# 加载数据\n'
                                '# df = pd.read_excel("data.xlsx")  # 根据实际文件调整\n'
                                'print("数据概览：")\n'
                                'print(f"行数: {len(df)}, 列数: {len(df.columns)}")\n'
                                'print(f"列名: {list(df.columns)}")\n'
                                'print(f"缺失值: {df.isnull().sum().to_dict()}")\n'
                                'print(f"数据类型:\\n{df.dtypes}")\n'
                                'print(f"基本统计:\\n{df.describe()}")'
                            ),
                            'instruction': '用 Python 加载并探索数据的基本结构和质量。',
                        },
                        'next_step_id': 'deep-analysis',
                    },
                    {
                        'id': 'deep-analysis',
                        'action': 'code_execution',
                        'description': '深度数据分析',
                        'parameters': {
                            'instruction': (
                                '根据数据特点执行分析：\n'
                                '1. 描述性统计（均值/中位数/分布）\n'
                                '2. 趋势分析（同比/环比）\n'
                                '3. 相关性分析\n'
                                '4. 异常值检测\n'
                                '5. 分组聚合（按维度汇总）'
                            ),
                            'language': 'python',
                        },
                        'next_step_id': 'generate-insights',
                    },
                    {
                        'id': 'generate-insights',
                        'action': 'generate_report',
                        'description': '生成数据洞察报告',
                        'parameters': {
                            'instruction': (
                                '生成数据分析报告：\n'
                                '1. 数据概览（1 段）\n'
                                '2. 关键发现（3-5 条，每条附数据支撑）\n'
                                '3. 趋势与模式\n'
                                '4. 业务建议（可执行的下一步）\n'
                                '5. 数据质量说明（缺失值、异常值等）'
                            ),
                            'output_format': 'markdown',
                            'include_visualization_code': True,
                        },
                    },
                ],
            },
            {
                'id': 'chart-generation',
                'name': '图表生成',
                'description': '根据数据生成可视化图表（折线图、柱状图、饼图、散点图等）',
                'trigger_patterns': [
                    '生成图表', '画图', '图表', '可视化', 'chart',
                    '柱状图', '折线图', '饼图', '散点图', '数据可视化',
                    '做成图', 'graph', 'plot',
                ],
                'metadata': {
                    'category': 'data',
                    'estimated_steps': 3,
                    'tools_used': ['code_execution', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'prepare-data',
                        'action': 'code_execution',
                        'description': '准备并整理图表数据',
                        'parameters': {
                            'instruction': '将用户提供的数据整理为适合可视化的格式（DataFrame 或列表）。',
                            'language': 'python',
                        },
                        'next_step_id': 'generate-chart',
                    },
                    {
                        'id': 'generate-chart',
                        'action': 'code_execution',
                        'description': '使用 matplotlib 生成图表',
                        'parameters': {
                            'code': (
                                'import matplotlib.pyplot as plt\n'
                                'import matplotlib\n'
                                "matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']\n"
                                "matplotlib.rcParams['axes.unicode_minus'] = False\n\n"
                                '# TODO: 根据数据和图表类型生成图表\n'
                                '# plt.figure(figsize=(10, 6))\n'
                                '# plt.bar(x, y) / plt.plot(x, y) / plt.pie(values, labels=labels)\n'
                                '# plt.title("图表标题")\n'
                                '# plt.xlabel("X轴")\n'
                                '# plt.ylabel("Y轴")\n'
                                '# plt.tight_layout()\n'
                                "# plt.savefig('./output/chart.png', dpi=150)\n"
                                '# plt.show()'
                            ),
                            'instruction': (
                                '生成图表的要求：\n'
                                '1. 根据数据特征选择最佳图表类型\n'
                                '2. 设置合适的标题、轴标签、图例\n'
                                '3. 使用专业配色方案\n'
                                '4. 保存到 ./output/ 目录\n'
                                '5. 输出图表文件路径和简要说明'
                            ),
                            'language': 'python',
                            'timeout': 30,
                        },
                        'next_step_id': 'save-deliver',
                    },
                    {
                        'id': 'save-deliver',
                        'action': 'file_operations',
                        'description': '保存图表并提供下载路径',
                        'parameters': {
                            'operation': 'write',
                            'instruction': '将生成的图表文件保存到工作区，并告知用户文件路径和使用建议。',
                        },
                    },
                ],
            },

            # ===== E. 任务与项目 =====
            {
                'id': 'weekly-report',
                'name': '周报生成',
                'description': '根据本周工作记录自动生成结构化周报',
                'trigger_patterns': [
                    '周报', 'weekly report', '工作周报', '本周总结',
                    '写周报', '生成周报', '一周工作总结', '本周工作',
                ],
                'metadata': {
                    'category': 'task',
                    'estimated_steps': 4,
                    'tools_used': ['memory_search', 'file_operations'],
                },
                'steps': [
                    {
                        'id': 'collect-this-week',
                        'action': 'memory_search',
                        'description': '收集本周工作记录',
                        'parameters': {
                            'query': '本周工作任务 完成 进展',
                            'limit': 10,
                            'instruction': '从用户的历史记忆中搜索本周的工作内容和对话记录。',
                        },
                        'next_step_id': 'categorize-tasks',
                    },
                    {
                        'id': 'categorize-tasks',
                        'action': 'organize',
                        'description': '按类别整理工作任务',
                        'parameters': {
                            'instruction': (
                                '将本周工作按类别整理：\n'
                                '1. 重点项目进展\n'
                                '2. 已完成的任务\n'
                                '3. 进行中的任务\n'
                                '4. 遇到的问题与风险\n'
                                '5. 协作与沟通'
                            ),
                        },
                        'next_step_id': 'plan-next-week',
                    },
                    {
                        'id': 'plan-next-week',
                        'action': 'plan',
                        'description': '规划下周工作',
                        'parameters': {
                            'instruction': (
                                '根据本周进展制定下周计划：\n'
                                '1. 下周重点目标（3 个以内）\n'
                                '2. 待办事项优先级排序\n'
                                '3. 需要的资源和支持'
                            ),
                        },
                        'next_step_id': 'format-weekly',
                    },
                    {
                        'id': 'format-weekly',
                        'action': 'generate_report',
                        'description': '输出格式化的周报文档',
                        'parameters': {
                            'instruction': (
                                '生成 Markdown 格式周报：\n'
                                '---\n'
                                '# 周报 | YYYY.MM.DD - YYYY.MM.DD\n\n'
                                '## 本周工作概要\n'
                                '（一段话概括本周最重要的成果）\n\n'
                                '## 重点项目进展\n'
                                '### 项目A\n'
                                '- 完成：xxx\n'
                                '- 进行中：xxx\n\n'
                                '## 下周计划\n'
                                '- [ ] P0: xxx\n'
                                '- [ ] P1: xxx\n\n'
                                '## 需要关注\n'
                                '（风险、阻塞、需要的支持）'
                            ),
                            'output_format': 'markdown',
                            'save_to_workspace': True,
                        },
                    },
                ],
            },

            # ===== F. 演示与展示（保留 1 个 PPT 技能，使用完整工具链） =====
            {
                'id': 'ppt-generate',
                'name': 'PPT生成',
                'description': '根据内容自动生成专业演示文稿（大纲→模板→内容→质检）',
                'trigger_patterns': [
                    '做PPT', '生成PPT', '制作演示', 'presentation',
                    '幻灯片', 'ppt', 'PPT', '演示文稿', '做演示',
                ],
                'metadata': {
                    'category': 'presentation',
                    'estimated_steps': 5,
                    'tools_used': [
                        'ppt_generate_outline', 'ppt_template_match',
                        'ppt_generate_content', 'ppt_generate_file',
                        'ppt_quality_check',
                    ],
                },
                'steps': [
                    {
                        'id': 'generate-outline',
                        'action': 'ppt_generate_outline',
                        'description': '根据主题和内容生成PPT大纲',
                        'parameters': {
                            'instruction': '分析用户提供的内容，生成结构化的PPT大纲（标题页、目录、章节页、内容页、总结页）。',
                        },
                        'next_step_id': 'match-template',
                    },
                    {
                        'id': 'match-template',
                        'action': 'ppt_template_match',
                        'description': '匹配合适的PPT模板',
                        'parameters': {
                            'instruction': '根据内容类型（商务/技术/创意/教育/极简）自动推荐最合适的模板。',
                        },
                        'next_step_id': 'generate-content',
                    },
                    {
                        'id': 'generate-content',
                        'action': 'ppt_generate_content',
                        'description': '根据大纲生成每页幻灯片内容',
                        'parameters': {
                            'instruction': '为大纲中的每一页生成详细内容，包括标题、正文、图表占位、备注。',
                        },
                        'next_step_id': 'generate-pptx',
                    },
                    {
                        'id': 'generate-pptx',
                        'action': 'ppt_generate_file',
                        'description': '生成PPTX文件',
                        'parameters': {
                            'instruction': '将幻灯片内容渲染为 .pptx 文件并保存。',
                        },
                        'next_step_id': 'quality-check',
                    },
                    {
                        'id': 'quality-check',
                        'action': 'ppt_quality_check',
                        'description': '质检生成的PPT',
                        'parameters': {
                            'instruction': '检查页数、内容完整性、模板一致性，输出质检报告。',
                        },
                    },
                ],
            },
        ]

    # =========================================================================
    # 查询与统计
    # =========================================================================

    def get_preset_skills(self) -> List[Skill]:
        """获取所有已初始化的预设技能"""
        return self.preset_skills

    def get_skills_by_category(self, category: str) -> List[Skill]:
        """按类别筛选预设技能"""
        return [
            s for s in self.preset_skills
            if s.metadata.get('category') == category
        ]

    def list_categories(self) -> List[str]:
        """列出所有技能类别"""
        categories = set()
        for s in self.preset_skills:
            cat = s.metadata.get('category', 'other')
            categories.add(cat)
        return sorted(categories)

    def create_preset_skill(self, **kwargs) -> Skill:
        """手动创建预设技能"""
        skill = Skill(
            id=kwargs.get('id', generate_id()),
            name=kwargs['name'],
            description=kwargs.get('description', ''),
            type='preset',
            trigger_patterns=kwargs.get('trigger_patterns', []),
            steps=[SkillStep(**s) for s in kwargs.get('steps', [])],
            metadata=kwargs.get('metadata', {}),
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by='system',
            version='1.1.0'
        )

        db.save_skill(skill)
        self.preset_skills.append(skill)

        return skill


# 全局实例
preset_skills_manager = PresetSkillsManager()
