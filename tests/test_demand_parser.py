import pytest
from src.engine.demand_parser import DemandParser, PPTDemand, demand_parser
from src.engine.im_trigger import IMTrigger, TriggerResult, im_trigger


class TestDemandParser:
    """需求解析器测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.parser = DemandParser()
    
    def test_detect_ppt_demand_positive(self):
        """测试检测PPT需求（正面案例）"""
        test_cases = [
            "帮我做个PPT",
            "制作一份汇报材料",
            "生成演示稿",
            "做个10页的幻灯片",
            "需要一个presentation"
        ]
        
        for text in test_cases:
            assert self.parser.detect_ppt_demand(text) is True
    
    def test_detect_ppt_demand_negative(self):
        """测试检测PPT需求（负面案例）"""
        test_cases = [
            "你好",
            "今天天气怎么样",
            "帮我查一下资料",
            "这个文档不错"
        ]
        
        for text in test_cases:
            assert self.parser.detect_ppt_demand(text) is False
    
    def test_extract_page_count(self):
        """测试提取页数"""
        assert self.parser._extract_page_count("做个10页的PPT") == 10
        assert self.parser._extract_page_count("制作20 slides") == 20
        assert self.parser._extract_page_count("30张幻灯片") == 30
        assert self.parser._extract_page_count("不需要指定页数") is None
    
    def test_extract_style(self):
        """测试提取风格"""
        assert self.parser._extract_style("正式风格") == "正式"
        assert self.parser._extract_style("商务汇报") == "正式"
        assert self.parser._extract_style("活泼一点") == "活泼"
        assert self.parser._extract_style("科技感") == "科技"
        assert self.parser._extract_style("简约风格") == "简洁"
    
    def test_extract_audience(self):
        """测试提取受众"""
        assert self.parser._extract_audience("面向领导") == "领导"
        assert self.parser._extract_audience("给客户看") == "客户"
        assert self.parser._extract_audience("同事分享") == "同事"
        assert self.parser._extract_audience("公开演讲") == "公众"
    
    def test_extract_purpose(self):
        """测试提取用途"""
        assert self.parser._extract_purpose("工作汇报") == "汇报"
        assert self.parser._extract_purpose("产品介绍") == "介绍"
        assert self.parser._extract_purpose("员工培训") == "培训"
        assert self.parser._extract_purpose("项目路演") == "介绍"
    
    def test_extract_core_topic(self):
        """测试提取核心主题"""
        text = "@Hermes 用这份《Q3销售数据.xlsx》生成业绩分析PPT"
        topic = self.parser._extract_core_topic(text)
        assert "Q3销售数据" in topic
    
    def test_extract_key_data(self):
        """测试提取重点数据"""
        text = "重点突出华东区增长30%，销售额达到500万"
        data = self.parser._extract_key_data(text)
        assert "华东" in data
        assert "30%" in data or "30" in str(data)
    
    def test_extract_required_modules(self):
        """测试提取必含模块"""
        text = "需要包含目录、数据图表和总结部分"
        modules = self.parser._extract_required_modules(text)
        assert "目录" in modules
        assert "数据" in modules
        assert "总结" in modules
    
    def test_extract_demand_complete(self):
        """测试完整需求提取"""
        text = "@Hermes 把Q3销售数据做成10页的汇报PPT，面向部门领导，风格正式"
        demand = self.parser.extract_demand(text)
        
        assert demand.page_count == 10
        assert demand.audience == "领导"
        assert demand.style == "正式"
        assert demand.purpose == "汇报"
        assert "Q3销售" in demand.core_topic
    
    def test_generate_confirmation_message(self):
        """测试生成确认消息"""
        demand = PPTDemand(
            title="Q3销售汇报",
            page_count=10,
            audience="领导",
            style="正式",
            confirmation_questions=["是否需要添加竞品分析？"]
        )
        
        message = self.parser.generate_confirmation_message(demand)
        assert "Q3销售汇报" in message
        assert "10页" in message
        assert "领导" in message
    
    def test_aggregate_group_demands(self):
        """测试群聊需求聚合"""
        demands = [
            PPTDemand(title="项目汇报", page_count=8, audience="领导", style="正式"),
            PPTDemand(title="项目汇报PPT", page_count=10, audience="同事", style="简洁")
        ]
        
        aggregated = self.parser.aggregate_group_demands(demands)
        
        assert aggregated.title == "项目汇报PPT"
        assert aggregated.page_count == 10
        assert "领导" in aggregated.audience
        assert "同事" in aggregated.audience
        assert aggregated.style == "正式"


class TestIMTrigger:
    """IM触发器测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.trigger = IMTrigger()
    
    def test_direct_mention_trigger(self):
        """测试直接@机器人触发"""
        message = {
            "user_id": "user123",
            "content": "@Hermes 帮我做个10页的PPT",
            "mentioned_users": ["Hermes"],
            "chat_type": "group",
            "chat_id": "group1",
            "attachments": []
        }
        
        result = self.trigger.process_message(message)
        
        assert result.is_triggered is True
        assert result.trigger_type == "direct"
        assert result.demand is not None
        assert result.demand.page_count == 10
    
    def test_passive_trigger(self):
        """测试被动触发"""
        message = {
            "user_id": "user123",
            "content": "我需要做个汇报材料，不知道怎么做",
            "mentioned_users": [],
            "chat_type": "group",
            "chat_id": "group1",
            "attachments": []
        }
        
        result = self.trigger.process_message(message)
        
        assert result.is_triggered is True
        assert result.trigger_type == "passive"
    
    def test_no_trigger(self):
        """测试不触发"""
        message = {
            "user_id": "user123",
            "content": "今天天气真好",
            "mentioned_users": [],
            "chat_type": "group",
            "chat_id": "group1",
            "attachments": []
        }
        
        result = self.trigger.process_message(message)
        
        assert result.is_triggered is False
    
    def test_attachment_trigger(self):
        """测试附件触发"""
        message = {
            "user_id": "user123",
            "content": "用这份文件做个PPT",
            "mentioned_users": [],
            "chat_type": "group",
            "chat_id": "group1",
            "attachments": [{"name": "Q3销售数据.xlsx"}]
        }
        
        result = self.trigger.handle_attachment_upload(
            {"name": "Q3销售数据.xlsx"},
            message
        )
        
        assert result.is_triggered is True
    
    def test_clean_instruction(self):
        """测试清理指令"""
        content = "@Hermes 帮我做个PPT"
        cleaned = self.trigger._clean_instruction(content)
        assert "Hermes" not in cleaned
        assert cleaned == "帮我做个PPT"
    
    def test_extract_links(self):
        """测试提取链接"""
        content = "参考文档：https://example.com/doc.pdf 和 https://test.com/data"
        links = self.trigger._extract_links(content)
        assert len(links) == 2
        assert "example.com" in links[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])