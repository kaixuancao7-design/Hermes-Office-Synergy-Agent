"""ReAct推理引擎"""
from typing import Dict, Any, Optional, List
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp
from src.plugins import get_tool_executor, get_model_router

logger = get_logger("engine")


class ReActEngine:
    """ReAct推理引擎"""
    
    def __init__(self):
        self.max_thinking_steps = 5
        self.max_tool_calls = 3
    
    def run(self, user_id: str, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """执行ReAct推理"""
        logger.info(f"[ReAct] 开始推理: user_id={user_id}, query={query[:50]}")
        
        try:
            # 获取工具执行器
            tool_executor = get_tool_executor()
            
            if not tool_executor:
                logger.warning("[ReAct] 工具执行器不可用，降级到直接调用模型")
                return self._call_model_directly(query)
            
            # 获取可用工具列表
            available_tools = tool_executor.list_tools()
            logger.info(f"[ReAct] 可用工具: {available_tools}")
            
            # ReAct推理循环
            thought = "开始分析用户请求"
            context = query
            
            for step in range(self.max_thinking_steps):
                logger.info(f"[ReAct] 步骤 {step+1}: {thought}")
                
                # 决定是否调用工具
                tool_to_call = self._decide_tool_call(query, context, available_tools)
                
                if tool_to_call:
                    # 调用工具
                    result = self._execute_tool(tool_executor, tool_to_call, query, user_id, metadata)
                    
                    if result.get("success"):
                        # 更新上下文
                        context = f"{context}\n\n工具执行结果: {result.get('result', '')}"
                        thought = f"工具 {tool_to_call} 执行成功，获得新信息"
                    else:
                        thought = f"工具 {tool_to_call} 执行失败: {result.get('error')}"
                
                else:
                    # 不需要调用工具，直接生成回答
                    logger.info("[ReAct] 不需要调用工具，直接生成回答")
                    break
            
            # 使用最终上下文生成回答
            final_response = self._generate_final_response(query, context)
            
            logger.info(f"[ReAct] 推理完成: response_length={len(final_response)}")
            
            return final_response
        
        except Exception as e:
            logger.error(f"[ReAct] 推理失败: {str(e)}")
            return f"处理请求时出现错误: {str(e)}"
    
    def _decide_tool_call(self, query: str, context: str, available_tools: List[str]) -> Optional[str]:
        """决定是否调用工具"""
        query_lower = query.lower()
        
        # 根据关键词决定调用哪个工具
        tool_keywords = {
            "feishu_file_read": ["文件", "文档", "读取", "内容"],
            "web_search": ["搜索", "查找", "信息", "新闻", "最新"],
            "memory_search": ["记得", "历史", "之前", "查找"],
            "document_search": ["文档", "资料", "文件"],
            "code_execution": ["运行", "执行", "代码"],
            "vector_migration": ["迁移", "升级"]
        }
        
        for tool_id, keywords in tool_keywords.items():
            if tool_id in available_tools:
                if any(keyword in query_lower for keyword in keywords):
                    logger.info(f"[ReAct] 决定调用工具: {tool_id}")
                    return tool_id
        
        return None
    
    def _execute_tool(self, tool_executor, tool_id: str, query: str, user_id: str, metadata: Optional[Dict[str, Any]]) -> dict:
        """执行工具调用"""
        logger.info(f"[ReAct] 调用工具: {tool_id}")
        
        params = {
            "user_id": user_id,
            "query": query
        }
        
        # 添加元数据
        if metadata:
            params.update(metadata)
        
        return tool_executor.execute(tool_id, params)
    
    def _call_model_directly(self, query: str) -> str:
        """直接调用模型生成回答"""
        model_router = get_model_router()
        
        if not model_router:
            logger.warning("[ReAct] 模型路由不可用")
            return "抱歉，当前无法处理您的请求。"
        
        model = model_router.select_model("general", "simple")
        if not model:
            return "抱歉，当前无法处理您的请求。"
        
        response = model_router.call_model(model, [{"role": "user", "content": query}])
        
        if response and response.strip():
            return response
        
        return "抱歉，当前无法处理您的请求。"
    
    def _generate_final_response(self, query: str, context: str) -> str:
        """生成最终回答"""
        model_router = get_model_router()
        
        if not model_router:
            logger.warning("[ReAct] 模型路由不可用")
            return "根据分析，我已处理您的请求。"
        
        model = model_router.select_model("general", "medium")
        if not model:
            return "根据分析，我已处理您的请求。"
        
        prompt = f"基于以下上下文回答问题：\n\n上下文：{context}\n\n问题：{query}"
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        if response and response.strip():
            return response
        
        return "根据分析，我已处理您的请求。"


# 全局实例
react_engine = ReActEngine()
