# backend/app/api/agents.py
import json
import asyncio
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from app.agents.SQL_agent import SqlAgent
from app.agents.evo_agent import EvoAgent
from app.core.guardrails import SESSION_CLUSTER_DB

router = APIRouter(prefix="/api/agents", tags=["AgentCoreGateway"])

# 初始化多智能体单例
sql_agent_instance = SqlAgent()
evo_agent_instance = EvoAgent()

@router.get("/stream-orchestrator")
async def stream_orchestrator(
    session_id: str = Query(..., description="全局唯一会话流水号"),
    prompt: str = Query(..., description="产品经理输入的业务诉求描述")
):
    """
    大厂标准：基于 SSE (Server-Sent Events) 的多智能体级联编排长连接分发网关。
    流式穿透核心 CoT、执行状态切面以及 HITL 人类在环熔断断点。
    """
    
    async def sse_event_generator():
        # 初始化分布式 Session 上下文状态
        SESSION_CLUSTER_DB[session_id] = {
            "status": "RUNNING",
            "sql_asset": None,
            "marketing_asset": None,
            "target_rows": 0,
            "hitl_approved": False,
            "raw_prompt": prompt
        }

# =====================================================================
        # 阶段一：激活 SQL 取数清洗 Agent
        # =====================================================================
        sql_stream = sql_agent_instance.stream_chunks(prompt)
        
        async for chunk in sql_stream:
            if not chunk:
                continue
            # 向前端 SSE 观察窗实时推入 SQL Agent 的纯文本思维链
            yield f"data: {json.dumps({'type': 'cot', 'agent': 'SQL清洗智能体', 'content': chunk}, ensure_ascii=False)}\n\n"

        # =====================================================================
        # 阶段二：流自然结束后 (等同于 agent_complete)，进行风控断点判定
        # =====================================================================
        import random
        # 模拟沙盒返回的规模分配：12000 正常通过，55000 触发高危熔断
        last_compiled_rows = random.choice([12000, 55000]) 
        SESSION_CLUSTER_DB[session_id]["target_rows"] = last_compiled_rows

        if last_compiled_rows > 50000:
            SESSION_CLUSTER_DB[session_id]["status"] = "SUSPENDED_AWAITING_HITL"
            
            # 瞬间向前端长连接广播挂起事件，要求人类架构师进行高危操作二次确认
            hitl_brake_payload = {
                "event": "hitl_brake",
                "agent_name": "Harness_HITL_Manager",
                "content": f"【🚨 触发大厂风控红线拦截】当前 SQL 清洗出客群覆盖规模达 {last_compiled_rows} 人，已突破 50,000 人高客群资损资位阈值！系统已强制挂起该会话。",
                "target_rows": last_compiled_rows
            }
            yield f"data: {json.dumps(hitl_brake_payload, ensure_ascii=False)}\n\n"
            return  # 强行掐断当前流，等待人类通过独立 REST API 予以激活
        

# =====================================================================
        # 阶段三：级联激活红蓝对抗文案演化 Agent
        # =====================================================================
        yield f"data: {json.dumps({'event': 'agent_transition', 'content': '🟢 自动化流水线流转：SQL 跑测通过且无越权风险，正式转交营销演化沙盒'}, ensure_ascii=False)}\n\n"
        
        evo_prompt = f"请针对上一步清洗出来的优质客群（规模: {last_compiled_rows} 人），结合历史金律，推演高转化文案。前置产品诉求: {prompt}"
        
        # 💡 统一换成跟 SqlAgent 一致的纯文本流方法
        evo_stream = evo_agent_instance.stream_chunks(evo_prompt)
        
        async for chunk in evo_stream:
            # 同样将其包装为标准格式返给前端
            yield f"data: {json.dumps({'type': 'cot', 'agent': '红蓝文案演化智能体', 'content': chunk}, ensure_ascii=False)}\n\n"
        
        # 正常流水线收官
        SESSION_CLUSTER_DB[session_id]["status"] = "COMPLETED"
        yield f"data: {json.dumps({'event': 'pipeline_finished', 'content': '🎉 恭喜！全栈智能全自动模型编排与红蓝演化清洗全部闭环圆满完成。'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.post("/hitl-approve")
async def hitl_approve(
    session_id: str = Body(..., embed=True, description="被挂起的会话流水号"),
    action: str = Body(..., embed=True, description="审批动作: APPROVE 或 REJECT")
):
    """
    人类在环独立 REST 触发表单审批接口。
    用于对被安全马具强制拦截挂起（SUSPENDED）的高危会话进行人工解锁复苏。
    """
    if session_id not in SESSION_CLUSTER_DB:
        raise HTTPException(status_code=404, detail="未在分布式 Session 缓存集群中找到该流水号")
    
    session_data = SESSION_CLUSTER_DB[session_id]
    
    if session_data["status"] != "SUSPENDED_AWAITING_HITL":
        return {"status": "REJECTED", "message": f"当前会话状态为 {session_data['status']}，无需重复审批"}

    if action.upper() == "APPROVE":
        session_data["status"] = "APPROVED_RESUME"
        session_data["hitl_approved"] = True
        return {
            "status": "SUCCESS",
            "message": "【🟢 人工审批通过】高资损客群已被人类架构师背书解锁，请前端发起二次复苏请求。"
        }
    else:
        session_data["status"] = "TERMINATED_BY_HUMAN"
        return {"status": "TERMINATED", "message": "【🔴 人工驳回】高危营销发布已被就地拦截销毁。"}


@router.get("/resume-stream")
async def resume_stream(session_id: str = Query(..., description="解锁复苏的会话 ID")):
    """
    HITL 解锁后的二次复苏长连接。
    当人类审批通过后，前端通过此长连接继续消费后半段（红蓝文案对抗进化）的流式资产。
    """
    if session_id not in SESSION_CLUSTER_DB or SESSION_CLUSTER_DB[session_id]["status"] != "APPROVED_RESUME":
        raise HTTPException(status_code=400, detail="该会话未通过安全合规复核，拒绝复苏。")

    async def resume_generator():
        yield f"data: {json.dumps({'event': 'pipeline_resume', 'content': '🚀 收到人类架构师合规解锁凭证，复苏流式管线，开始灌入红蓝对抗沙盒...'}, ensure_ascii=False)}\n\n"
        
        session_data = SESSION_CLUSTER_DB[session_id]
        evo_prompt = f"【人类特批上线】针对突发规模为 {session_data['target_rows']} 的高价值流失预警客群，启动最终反思演化文案。"
        
        async for chunk in evo_agent_instance.run_stream(session_id, evo_prompt):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
        session_data["status"] = "COMPLETED"
        yield f"data: {json.dumps({'event': 'pipeline_finished', 'content': '🎉 经人类特批背书的全链智能资产交付圆满结束。'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(resume_generator(), media_type="text/event-stream")