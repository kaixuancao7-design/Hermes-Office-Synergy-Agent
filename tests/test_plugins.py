"""插件系统测试"""
import pytest
from src.plugins import init_plugins, get_im_adapter, IM_ADAPTER_REGISTRY


class TestPlugins:
    """插件系统测试类"""
    
    def test_get_im_adapter_with_type(self):
        """测试带类型参数的get_im_adapter"""
        # 测试传入飞书类型
        adapter = get_im_adapter("feishu")
        assert adapter is not None
        assert adapter.get_adapter_type() == "feishu"
    
    def test_get_im_adapter_with_dingtalk(self):
        """测试获取钉钉适配器"""
        adapter = get_im_adapter("dingtalk")
        assert adapter is not None
        assert adapter.get_adapter_type() == "dingtalk"
    
    def test_get_im_adapter_with_nonexistent_type(self):
        """测试获取不存在的适配器类型"""
        adapter = get_im_adapter("nonexistent")
        assert adapter is None
    
    def test_get_im_adapter_without_type(self):
        """测试不带参数的get_im_adapter"""
        # 在未初始化的情况下应该返回None
        adapter = get_im_adapter()
        assert adapter is None
    
    def test_get_im_adapter_after_init(self):
        """测试初始化后获取适配器"""
        init_plugins({"im_adapter": "feishu"})
        adapter = get_im_adapter()
        assert adapter is not None
        assert adapter.get_adapter_type() == "feishu"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])