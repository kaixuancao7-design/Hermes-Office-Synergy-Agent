"""数据处理工具 - 提供数据清洗、转换、分析等功能"""
from typing import Dict, Any, List, Optional, Union
from src.logging_config import get_logger

logger = get_logger("tool")


class DataProcessor:
    """数据处理器 - 提供数据处理和分析功能"""
    
    def __init__(self):
        pass
    
    def clean_text(self, text: str) -> str:
        """
        清洗文本数据
        
        Args:
            text: 原始文本
        
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 去除多余空白字符
        text = " ".join(text.split())
        
        # 去除特殊字符
        import re
        text = re.sub(r'[^\w\s\u4e00-\u9fa5。，！？；：、\"\']', '', text)
        
        return text.strip()
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        提取文本关键词
        
        Args:
            text: 输入文本
            top_n: 返回前N个关键词
        
        Returns:
            关键词列表
        """
        if not text:
            return []
        
        try:
            import jieba
            from collections import Counter
            
            # 使用jieba分词
            words = jieba.lcut(text)
            
            # 过滤停用词
            stopwords = self._get_stopwords()
            words = [word for word in words if word not in stopwords and len(word) >= 2]
            
            # 统计词频
            word_counts = Counter(words)
            
            # 返回前N个关键词
            return [word for word, _ in word_counts.most_common(top_n)]
        
        except ImportError:
            logger.warning("jieba 未安装，使用简单分词")
            return self._simple_keyword_extraction(text, top_n)
        except Exception as e:
            logger.error(f"提取关键词失败: {str(e)}")
            return []
    
    def _simple_keyword_extraction(self, text: str, top_n: int) -> List[str]:
        """简单关键词提取（备用方案）"""
        from collections import Counter
        import re
        
        # 简单分词（按非中文字符分割）
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        
        # 统计词频
        word_counts = Counter(words)
        
        return [word for word, _ in word_counts.most_common(top_n)]
    
    def _get_stopwords(self) -> set:
        """获取停用词集合"""
        stopwords = {
            '的', '是', '在', '和', '有', '我', '他', '她', '它', '这', '那', '能',
            '会', '可以', '不', '了', '着', '过', '吧', '吗', '呢', '啊', '哦',
            '嗯', '哎', '呀', '哦', '哈', '嘿', '喂', '嗨', '哦', '嗯', '啊',
            '一个', '一些', '有些', '很多', '非常', '特别', '很', '太', '更',
            '最', '比较', '相当', '稍微', '一点', '一下', '一会儿', '一直',
            '已经', '曾经', '刚刚', '正在', '将要', '会', '能', '可能', '应该',
            '必须', '需要', '可以', '应该', '得', '要', '会', '可能', '应该',
            '已经', '曾经', '刚刚', '正在', '将要', '马上', '立刻', '突然',
            '忽然', '渐渐', '慢慢', '快速', '迅速', '缓慢', '经常', '常常',
            '偶尔', '有时', '总是', '一直', '始终', '永远', '暂时', '临时',
            '目前', '现在', '将来', '过去', '刚才', '昨天', '今天', '明天',
            '后天', '前天', '去年', '今年', '明年', '最近', '最近', '近来',
            '以前', '以后', '之前', '之后', '之间', '以来', '以内', '以上',
            '以下', '左右', '上下', '前后', '内外', '中间', '旁边', '附近',
            '到处', '四处', '到处', '处处', '任何', '所有', '每', '各', '某',
            '其他', '另外', '别的', '什么', '怎么', '为什么', '如何', '多少',
            '几', '哪', '谁', '什么', '哪', '几', '谁', '何时', '何地', '为何',
            '是否', '有无', '多少', '大小', '长短', '高低', '远近', '快慢',
            '好坏', '真假', '对错', '是非', '善恶', '美丑', '新旧', '难易',
            '轻重', '缓急', '先后', '主次', '男女', '老少', '中外', '古今',
            '东西', '南北', '前后', '左右', '上下', '里外', '中间', '旁边',
            '上面', '下面', '前面', '后面', '左面', '右面', '这里', '那里',
            '这边', '那边', '这样', '那样', '这么', '那么', '如此', '这般',
            '一样', '不同', '相同', '类似', '好像', '仿佛', '似乎', '犹如',
            '如同', '好比', '例如', '比如', '譬如', '包括', '包含', '含有',
            '属于', '关于', '对于', '至于', '由于', '因为', '所以', '因此',
            '从而', '于是', '但是', '然而', '可是', '不过', '虽然', '尽管',
            '如果', '假如', '要是', '万一', '只要', '只有', '除非', '否则',
            '无论', '不管', '不论', '即使', '即便', '倘若', '要是', '若',
            '一旦', '假如', '如果', '倘若', '要是', '若', '万一', '一旦',
            '首先', '其次', '然后', '接着', '最后', '终于', '终于', '终究',
            '到底', '毕竟', '究竟', '竟然', '居然', '果然', '确实', '的确',
            '实在', '真的', '非常', '十分', '特别', '尤其', '格外', '更加',
            '极其', '相当', '略微', '稍微', '几乎', '差不多', '将近', '大约',
            '大概', '左右', '上下', '前后', '内外', '之间', '之中', '之前',
            '之后', '以来', '以内', '以上', '以下', '以外', '以来', '为止',
            '等等', '等等', '之类', '等等', '等等', '等等', '等等', '等等',
        }
        return stopwords
    
    def summarize_text(self, text: str, max_length: int = 300, method: str = "extract") -> str:
        """
        文本摘要生成
        
        Args:
            text: 输入文本
            max_length: 最大长度
            method: 摘要方法 ('extract' 抽取式, 'abstract' 抽象式)
        
        Returns:
            摘要文本
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        if method == "abstract":
            return self._abstract_summary(text, max_length)
        else:
            return self._extract_summary(text, max_length)
    
    def _extract_summary(self, text: str, max_length: int) -> str:
        """抽取式摘要 - 提取关键句子"""
        sentences = self._split_sentences(text)
        
        # 计算句子重要性（基于关键词）
        keywords = set(self.extract_keywords(text, top_n=20))
        sentence_scores = []
        
        for i, sentence in enumerate(sentences):
            score = 0
            # 包含关键词的数量
            for keyword in keywords:
                if keyword in sentence:
                    score += 1
            # 位置权重（开头和结尾的句子更重要）
            position_score = 1.0 - abs(i - len(sentences)/2) / (len(sentences)/2)
            sentence_scores.append((score * position_score, sentence))
        
        # 按分数排序
        sentence_scores.sort(reverse=True, key=lambda x: x[0])
        
        # 选择前几个句子
        result = ""
        for _, sentence in sentence_scores:
            if len(result) + len(sentence) <= max_length:
                result += sentence + " "
            else:
                break
        
        return result.strip()
    
    def _abstract_summary(self, text: str, max_length: int) -> str:
        """抽象式摘要（使用简单规则）"""
        # 获取前几句话作为摘要
        sentences = self._split_sentences(text)
        result = ""
        
        for sentence in sentences[:5]:
            if len(result) + len(sentence) <= max_length:
                result += sentence + " "
            else:
                break
        
        return result.strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割文本为句子"""
        import re
        sentences = re.split(r'[。！？；\n\r]', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def format_table(self, data: List[List[str]], headers: Optional[List[str]] = None) -> str:
        """
        格式化数据为表格文本
        
        Args:
            data: 二维列表数据
            headers: 表头（可选）
        
        Returns:
            格式化的表格字符串
        """
        if not data:
            return "无数据"
        
        # 合并表头和数据
        if headers:
            all_rows = [headers] + data
        else:
            all_rows = data
        
        # 计算每列最大宽度
        col_widths = []
        for col_idx in range(len(all_rows[0])):
            max_width = max(len(str(row[col_idx])) for row in all_rows)
            col_widths.append(max_width + 2)  # 增加边距
        
        # 生成表格
        lines = []
        
        # 顶部边框
        lines.append("+" + "+".join("-" * w for w in col_widths) + "+")
        
        for i, row in enumerate(all_rows):
            # 数据行
            cells = []
            for j, cell in enumerate(row):
                cell_str = str(cell)
                # 截断过长的内容
                if len(cell_str) > col_widths[j] - 2:
                    cell_str = cell_str[:col_widths[j] - 5] + "..."
                cells.append(cell_str.ljust(col_widths[j] - 2))
            
            lines.append("| " + " | ".join(cells) + " |")
            
            # 表头分隔线
            if i == 0 and headers:
                lines.append("+" + "+".join("=" * w for w in col_widths) + "+")
            elif i < len(all_rows) - 1:
                lines.append("+" + "+".join("-" * w for w in col_widths) + "+")
        
        # 底部边框
        lines.append("+" + "+".join("-" * w for w in col_widths) + "+")
        
        return "\n".join(lines)
    
    def validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_phone(self, phone: str) -> bool:
        """验证手机号码格式"""
        import re
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))
    
    def normalize_string(self, s: str) -> str:
        """标准化字符串（去除空格、转小写等）"""
        if not s:
            return ""
        return s.strip().lower()
    
    def count_words(self, text: str) -> Dict[str, int]:
        """统计文本词数"""
        if not text:
            return {"characters": 0, "words": 0, "sentences": 0}
        
        # 字符数（不含空格）
        char_count = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        
        # 中文词数（按字符算）+ 英文词数
        import re
        english_words = re.findall(r'[a-zA-Z]+', text)
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        
        # 句子数
        sentences = self._split_sentences(text)
        
        return {
            "characters": char_count,
            "words": len(english_words) + len(chinese_chars),
            "sentences": len(sentences)
        }
    
    def json_to_markdown(self, data: Union[Dict, List], indent: int = 0) -> str:
        """
        将JSON数据转换为Markdown格式
        
        Args:
            data: JSON数据
            indent: 缩进级别
        
        Returns:
            Markdown格式字符串
        """
        prefix = "  " * indent
        
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}- **{key}**:")
                    lines.append(self.json_to_markdown(value, indent + 1))
                else:
                    lines.append(f"{prefix}- **{key}**: {value}")
            return "\n".join(lines)
        
        elif isinstance(data, list):
            lines = []
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}{i+1}.")
                    lines.append(self.json_to_markdown(item, indent + 1))
                else:
                    lines.append(f"{prefix}{i+1}. {item}")
            return "\n".join(lines)
        
        else:
            return f"{prefix}{data}"


# 单例实例
data_processor = DataProcessor()


def clean_text(text: str) -> str:
    """清洗文本（便捷函数）"""
    return data_processor.clean_text(text)


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """提取关键词（便捷函数）"""
    return data_processor.extract_keywords(text, top_n)


def summarize_text(text: str, max_length: int = 300) -> str:
    """生成文本摘要（便捷函数）"""
    return data_processor.summarize_text(text, max_length)


def format_table(data: List[List[str]], headers: Optional[List[str]] = None) -> str:
    """格式化表格（便捷函数）"""
    return data_processor.format_table(data, headers)


def count_words(text: str) -> Dict[str, int]:
    """统计词数（便捷函数）"""
    return data_processor.count_words(text)
