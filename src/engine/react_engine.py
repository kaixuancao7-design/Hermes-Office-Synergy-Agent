"""ReAct推理引擎 - 增强日志版本"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.logging_config import get_logger, log_performance, log_event
from src.utils import generate_id, get_timestamp
from src.plugins import get_tool_executor, get_model_router
from src.plugins.model_routers import select_model, call_model

logger = get_logger("engine")


class ReActEngine:
    """ReAct推理引擎"""
    
    def __init__(self):
        self.max_thinking_steps = 5
        self.max_tool_calls = 3
        logger.info("[INIT] ReActEngine 初始化完成 | max_steps=%d | max_tool_calls=%d", 
                   self.max_thinking_steps, self.max_tool_calls)
    
    @log_performance(logger, "ReAct推理")
    async def run(self, user_id: str, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """执行ReAct推理"""
        start_time = datetime.now()
        trace_id = metadata.get("message_id", generate_id()) if metadata else generate_id()
        
        logger.info(f"[ReAct_START] 开始推理 | trace_id={trace_id} | user_id={user_id} | query={query[:50]}")
        
        try:
            # 获取工具执行器
            tool_executor = get_tool_executor()
            
            if not tool_executor:
                logger.warning("[ReAct_WARNING] 工具执行器不可用，降级到直接调用模型")
                return await self._call_model_directly(query)
            
            # 获取可用工具列表
            available_tools = tool_executor.get_tools()
            logger.info(f"[ReAct_TOOLS] 可用工具列表 | count={len(available_tools)} | tools={available_tools}")
            
            # ReAct推理循环
            thought = "开始分析用户请求"
            context = query
            tool_call_count = 0
            
            logger.debug(f"[ReAct_CONTEXT] 初始上下文 | length={len(context)}")
            
            for step in range(self.max_thinking_steps):
                logger.info(f"[ReAct_STEP] 推理步骤 {step+1}/{self.max_thinking_steps} | thought={thought[:50]}")
                
                # 决定是否调用工具
                tool_to_call = self._decide_tool_call(query, context, available_tools)
                
                if tool_to_call and tool_call_count < self.max_tool_calls:
                    # 调用工具
                    tool_call_count += 1
                    logger.info(f"[ReAct_TOOL_CALL] 调用工具 | step={step+1} | tool={tool_to_call} | count={tool_call_count}")
                    
                    result = await self._execute_tool(tool_executor, tool_to_call, query, user_id, metadata)
                    
                    if result.get("success"):
                        # 更新上下文
                        tool_result = result.get('result', '')
                        context = f"{context}\n\n工具执行结果: {tool_result}"
                        thought = f"工具 {tool_to_call} 执行成功，获得新信息"
                        logger.debug(f"[ReAct_TOOL_SUCCESS] 工具执行成功 | tool={tool_to_call} | result_length={len(str(tool_result))}")
                    else:
                        thought = f"工具 {tool_to_call} 执行失败: {result.get('error')}"
                        logger.warning(f"[ReAct_TOOL_FAILED] 工具执行失败 | tool={tool_to_call} | error={result.get('error')}")
                
                else:
                    # 不需要调用工具，直接生成回答
                    if tool_to_call:
                        logger.info(f"[ReAct_STOP] 达到最大工具调用次数 | max={self.max_tool_calls}")
                    else:
                        logger.info("[ReAct_STOP] 不需要调用工具，直接生成回答")
                    break
            
            # 使用最终上下文生成回答
            logger.debug(f"[ReAct_FINAL_CONTEXT] 最终上下文长度 | length={len(context)}")
            final_response = await self._generate_final_response(query, context)
            
            # 记录推理统计
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_event(logger, "react_complete",
                     trace_id=trace_id,
                     user_id=user_id,
                     steps=step+1,
                     tool_calls=tool_call_count,
                     response_length=len(final_response),
                     elapsed_ms=elapsed_ms)
            
            logger.info(f"[ReAct_COMPLETE] 推理完成 | trace_id={trace_id} | steps={step+1} | tool_calls={tool_call_count} | response_length={len(final_response)}")
            
            return final_response
        
        except Exception as e:
            logger.error(f"[ReAct_ERROR] 推理失败 | trace_id={trace_id} | user_id={user_id} | error={str(e)}", exc_info=True)
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
                    logger.debug(f"[ReAct_DECISION] 决定调用工具 | tool={tool_id} | matched_keywords={[k for k in keywords if k in query_lower]}")
                    return tool_id
        
        logger.debug("[ReAct_DECISION] 未匹配到需要调用的工具")
        return None
    
    async def _execute_tool(self, tool_executor, tool_id: str, query: str, user_id: str, metadata: Optional[Dict[str, Any]]) -> dict:
        """执行工具调用（异步）"""
        start_time = datetime.now()
        
        logger.info(f"[TOOL_EXECUTE] 开始执行工具 | tool={tool_id} | user_id={user_id}")
        
        params = {
            "user_id": user_id,
            "query": query
        }
        
        # 添加元数据
        if metadata:
            params.update(metadata)
        
        try:
            # 使用线程池执行同步工具，避免阻塞事件循环
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: tool_executor.execute(tool_id, params))
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if result.get("success"):
                logger.info(f"[TOOL_SUCCESS] 工具执行成功 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms")
            else:
                logger.warning(f"[TOOL_FAILED] 工具执行失败 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms | error={result.get('error')}")
            
            return result
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[TOOL_EXCEPTION] 工具执行异常 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms | error={str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _call_model_directly(self, query: str) -> str:
        """直接调用模型生成回答"""
        logger.info("[MODEL_DIRECT] 直接调用模型 | query_length=%d", len(query))
        
        try:
            response = await call_model(query, "ollama")
            if response and response.strip():
                logger.debug(f"[MODEL_DIRECT] 模型返回成功 | response_length={len(response)}")
                return response
            
            logger.warning("[MODEL_DIRECT] 模型返回空响应")
            return "抱歉，当前无法处理您的请求。"
        except Exception as e:
            logger.error(f"[MODEL_DIRECT] 模型调用失败 | error={str(e)}", exc_info=True)
            return "抱歉，当前无法处理您的请求。"
    
    async def _generate_final_response(self, query: str, context: str) -> str:
        """生成最终回答"""
        logger.info("[RESPONSE_GENERATE] 生成最终回答 | context_length=%d", len(context))
        
        try:
            prompt = f"基于以下上下文回答问题：\n\n上下文：{context}\n\n问题：{query}"
            response = await call_model(prompt, "ollama")
            
            if response and response.strip():
                logger.debug(f"[RESPONSE_GENERATE] 回答生成成功 | response_length={len(response)}")
                return response
            
            logger.warning("[RESPONSE_GENERATE] 模型返回空响应")
            return "根据分析，我已处理您的请求。"
        except Exception as e:
            logger.error(f"[RESPONSE_GENERATE] 模型调用失败 | error={str(e)}", exc_info=True)
            return "根据分析，我已处理您的请求。"


# 全局实例
react_engine = ReActEngine()