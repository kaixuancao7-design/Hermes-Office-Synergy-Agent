import pytest
import os
import shutil
from src.utils import (
    setup_logging,
    safe_log_string,
    generate_id,
    get_timestamp,
    ensure_directory,
    truncate_text
)


class TestUtils:
    """工具函数测试"""

    def test_setup_logging(self):
        """测试日志设置"""
        logger = setup_logging("DEBUG")
        assert logger is not None
        assert logger.level == 10  # DEBUG level

        # 测试重复初始化不会重复添加handler
        logger2 = setup_logging("INFO")
        assert logger2 is not None
        # 验证handler数量合理
        assert len(logger.handlers) <= 2  # 最多console + file

    def test_safe_log_string_basic(self):
        """测试安全日志字符串处理 - 基本功能"""
        text = "Hello, World!"
        result = safe_log_string(text)
        assert result == "Hello, World!"

    def test_safe_log_string_none(self):
        """测试安全日志字符串处理 - None输入"""
        result = safe_log_string(None)
        assert result == ""

    def test_safe_log_string_emoji(self):
        """测试安全日志字符串处理 - emoji替换"""
        text_with_emoji = "Hello 👋 World! 😊"
        result = safe_log_string(text_with_emoji)
        assert "👋" not in result
        # 实际映射是 [wavehello] 和 [blush]
        assert "[wavehello]" in result or "[wave]" in result
        assert "[blush]" in result or "[smile]" in result

    def test_safe_log_string_complex_emoji(self):
        """测试安全日志字符串处理 - 复杂emoji"""
        text = "🎉 完成任务！✅ 发送邮件 📧"
        result = safe_log_string(text)
        # 实际映射是 [celebration] 而不是 [party]
        assert "[celebration]" in result or "[party]" in result
        assert "[ok]" in result
        assert "[email]" in result

    def test_generate_id(self):
        """测试生成唯一ID"""
        id1 = generate_id()
        id2 = generate_id()
        
        assert id1 is not None
        assert id2 is not None
        assert id1 != id2
        assert len(id1) == 36  # UUID长度

    def test_get_timestamp(self):
        """测试获取时间戳"""
        ts = get_timestamp()
        assert isinstance(ts, int)
        assert ts > 0
        
        # 验证时间戳在合理范围内
        import time
        current_ts = int(time.time())
        assert abs(ts - current_ts) < 10  # 允许10秒误差

    def test_ensure_directory(self):
        """测试确保目录存在"""
        test_dir = "./test_temp_dir"
        
        # 确保目录不存在
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        
        # 创建目录
        ensure_directory(test_dir)
        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)
        
        # 重复创建不会报错
        ensure_directory(test_dir)
        assert os.path.exists(test_dir)
        
        # 清理
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

    def test_truncate_text(self):
        """测试文本截断"""
        short_text = "Short text"
        result = truncate_text(short_text, max_length=100)
        assert result == short_text
        
        long_text = "A" * 600
        result = truncate_text(long_text, max_length=500)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")
        
        # 测试默认长度
        result = truncate_text(long_text)
        assert len(result) == 503

    def test_truncate_text_empty(self):
        """测试空文本截断"""
        result = truncate_text("")
        assert result == ""
