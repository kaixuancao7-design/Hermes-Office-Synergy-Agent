"""MCP测试脚本 - 验证Model Context Protocol功能"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.mcp import (
    mcp_manager,
    MCPAdapter,
    ContextScope,
    ContextType,
    ContextState
)
from src.logging_config import get_logger

logger = get_logger("test_mcp")


def test_basic_context():
    """测试基础MCP上下文功能"""
    logger.info("=" * 60)
    logger.info("测试1: 基础MCP上下文功能")
    logger.info("=" * 60)
    
    # 创建上下文
    ctx = mcp_manager.create_context(
        context_type=ContextType.CUSTOM,
        scope=ContextScope.REQUEST,
        user_id="test_user_001",
        initial_data={
            "query": "测试查询",
            "metadata": {
                "source": "test",
                "timestamp": 1234567890
            }
        }
    )
    
    logger.info(f"创建上下文: {ctx}")
    assert ctx is not None, "上下文创建失败"
    assert ctx.get_metadata().context_id is not None, "上下文ID为空"
    assert ctx.get_metadata().context_type == ContextType.CUSTOM, "上下文类型错误"
    
    # 设置和获取数据
    ctx.set("key1", "value1")
    ctx.set("key2", {"nested": "value"})
    
    value1 = ctx.get("key1")
    value2 = ctx.get("key2")
    
    logger.info(f"key1: {value1}")
    logger.info(f"key2: {value2}")
    
    assert value1 == "value1", "数据获取失败"
    assert value2 is not None and value2.get("nested") == "value", "嵌套数据获取失败"
    
    # 测试状态更新
    ctx.update_state(ContextState.COMPLETED)
    assert ctx.get_metadata().state == ContextState.COMPLETED, "状态更新失败"
    
    # 测试标签
    ctx.add_tag("test")
    ctx.add_tag("mcp")
    assert "test" in ctx.get_metadata().tags, "标签添加失败"
    assert "mcp" in ctx.get_metadata().tags, "标签添加失败"
    
    ctx.remove_tag("test")
    assert "test" not in ctx.get_metadata().tags, "标签删除失败"
    
    logger.info("[OK] 基础功能测试通过")
    return ctx


def test_serialization():
    """测试序列化和反序列化"""
    logger.info("=" * 60)
    logger.info("测试2: 序列化和反序列化")
    logger.info("=" * 60)
    
    # 创建上下文
    ctx = mcp_manager.create_context(
        context_type=ContextType.TOOL,
        scope=ContextScope.SESSION,
        user_id="test_user_002",
        session_id="test_session_001",
        initial_data={
            "tool_id": "test_tool",
            "parameters": {"param1": "value1", "param2": 123}
        }
    )
    
    # 序列化
    serialized = ctx.serialize()
    logger.info(f"序列化结果长度: {len(serialized)}")
    assert isinstance(serialized, str) and len(serialized) > 0, "序列化失败"
    
    # 反序列化
    from src.engine.mcp import BaseMCPContext
    deserialized = BaseMCPContext.deserialize(serialized)
    
    logger.info(f"反序列化后的ID: {deserialized.get_metadata().context_id}")
    assert deserialized.get_metadata().context_id == ctx.get_metadata().context_id, "ID不匹配"
    assert deserialized.get("tool_id") == "test_tool", "数据不匹配"
    
    logger.info("[OK] 序列化测试通过")
    return deserialized


def test_context_manager():
    """测试上下文管理器功能"""
    logger.info("=" * 60)
    logger.info("测试3: 上下文管理器功能")
    logger.info("=" * 60)
    
    # 创建多个上下文
    ctx1 = mcp_manager.create_context(
        context_type=ContextType.REACT,
        scope=ContextScope.USER,
        user_id="test_user_003",
        initial_data={"step": 1}
    )
    
    ctx2 = mcp_manager.create_context(
        context_type=ContextType.REACT,
        scope=ContextScope.USER,
        user_id="test_user_003",
        initial_data={"step": 2}
    )
    
    ctx3 = mcp_manager.create_context(
        context_type=ContextType.PPT_WORKFLOW,
        scope=ContextScope.USER,
        user_id="test_user_003",
        initial_data={"stage": "planning"}
    )
    
    # 测试按用户获取
    user_contexts = mcp_manager.get_contexts_by_user("test_user_003")
    logger.info(f"用户003的上下文数量: {len(user_contexts)}")
    assert len(user_contexts) == 3, "用户上下文数量错误"
    
    # 测试按类型过滤
    react_contexts = mcp_manager.get_contexts_by_user("test_user_003", ContextType.REACT)
    logger.info(f"用户003的REACT上下文数量: {len(react_contexts)}")
    assert len(react_contexts) == 2, "REACT上下文数量错误"
    
    # 测试按类型获取
    ppt_contexts = mcp_manager.get_contexts_by_type(ContextType.PPT_WORKFLOW)
    logger.info(f"PPT_WORKFLOW类型上下文数量: {len(ppt_contexts)}")
    assert len(ppt_contexts) >= 1, "PPT上下文数量错误"
    
    # 测试统计
    stats = mcp_manager.get_context_count()
    logger.info(f"上下文统计: {stats}")
    assert stats["total"] > 0, "统计数据错误"
    
    # 测试删除
    mcp_manager.delete_context(ctx2.get_metadata().context_id)
    user_contexts_after = mcp_manager.get_contexts_by_user("test_user_003")
    logger.info(f"删除后用户003的上下文数量: {len(user_contexts_after)}")
    assert len(user_contexts_after) == 2, "删除功能错误"
    
    logger.info("[OK] 上下文管理器测试通过")


def test_context_merge():
    """测试上下文合并"""
    logger.info("=" * 60)
    logger.info("测试4: 上下文合并")
    logger.info("=" * 60)
    
    # 创建两个上下文
    ctx1 = mcp_manager.create_context(
        context_type=ContextType.CUSTOM,
        scope=ContextScope.REQUEST,
        initial_data={
            "common_key": "value1",
            "ctx1_key": "ctx1_value",
            "dict_key": {"a": 1}
        }
    )
    
    ctx2 = mcp_manager.create_context(
        context_type=ContextType.CUSTOM,
        scope=ContextScope.REQUEST,
        initial_data={
            "common_key": "value2",  # 会保留第一个
            "ctx2_key": "ctx2_value",
            "dict_key": {"b": 2},
            "list_key": [1, 2]
        }
    )
    
    # 合并
    merged = ctx1.merge(ctx2)
    
    logger.info(f"合并后的common_key: {merged.get('common_key')}")
    logger.info(f"合并后的ctx1_key: {merged.get('ctx1_key')}")
    logger.info(f"合并后的ctx2_key: {merged.get('ctx2_key')}")
    logger.info(f"合并后的dict_key: {merged.get('dict_key')}")
    
    assert merged.get("common_key") == "value2", "验证合并策略：后者覆盖前者"
    assert merged.get("ctx1_key") == "ctx1_value", "合并不完整"
    assert merged.get("ctx2_key") == "ctx2_value", "合并不完整"
    assert merged.get("dict_key") == {"a": 1, "b": 2}, "字典合并错误"
    
    logger.info("[OK] 上下文合并测试通过")


def test_context_clone():
    """测试上下文克隆"""
    logger.info("=" * 60)
    logger.info("测试5: 上下文克隆")
    logger.info("=" * 60)
    
    # 创建上下文
    ctx = mcp_manager.create_context(
        context_type=ContextType.MEMORY,
        scope=ContextScope.USER,
        user_id="test_user_004",
        initial_data={"data": "original"}
    )
    
    # 克隆
    cloned = ctx.clone()
    
    # 修改原上下文
    ctx.set("data", "modified")
    
    # 验证克隆独立
    logger.info(f"原上下文data: {ctx.get('data')}")
    logger.info(f"克隆上下文data: {cloned.get('data')}")
    
    assert ctx.get("data") == "modified", "原上下文修改失败"
    assert cloned.get("data") == "original", "克隆上下文被错误修改"
    assert cloned.get_metadata().context_id == ctx.get_metadata().context_id, "ID不匹配"
    
    logger.info("[OK] 上下文克隆测试通过")


def run_all_tests():
    """运行所有MCP测试"""
    logger.info("=" * 60)
    logger.info("Model Context Protocol (MCP) 测试套件")
    logger.info("=" * 60)
    
    try:
        test_basic_context()
        test_serialization()
        test_context_manager()
        test_context_merge()
        test_context_clone()
        
        logger.info("=" * 60)
        logger.info("[SUCCESS] 所有MCP测试通过!")
        logger.info("=" * 60)
        
        # 显示最终统计
        final_stats = mcp_manager.get_context_count()
        logger.info(f"最终上下文统计: {final_stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
