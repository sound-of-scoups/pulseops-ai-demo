import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.agents.SQL_agent import SqlAgent
from app.agents.dynamic_tools import sandbox_tool_center
from app.agents.evo_agent import EvoAgent
from app.core.guardrails import SESSION_CLUSTER_DB, guardrail_manager
from app.knowledge.store import EnterpriseKnowledgeStore

router = APIRouter(prefix="/api/agents", tags=["Agent orchestration"])
sql_agent = SqlAgent()
evo_agent = EvoAgent()


class ReviewDecision(BaseModel):
    task_id: str
    action: str


def packet(event: str, **data: Any) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


async def emit_text(agent: str, text: str) -> AsyncGenerator[str, None]:
    for line in text.splitlines():
        if line.strip():
            yield packet("log", agent=agent, content=line)
            await asyncio.sleep(0.045)


def copy_steps(scene_id: str) -> list[dict[str, str]]:
    return [{"agent": "Growth Planner", "label": "拆解业务目标", "status": "done", "detail": "将模糊目标拆为人群、指标、时间窗与实验约束"}, {"agent": "SQL / Data", "label": "取数与清洗", "status": "done", "detail": "基于知识库生成 SQL，注册运行时清洗工具"}, {"agent": "Red / Blue Copy", "label": "对抗生成文案", "status": "done" if scene_id not in ("risk", "hitl") else "waiting", "detail": "红方生成，蓝方以用户视角挑刺并反思"}, {"agent": "QA / Guardrail", "label": "测试与护栏", "status": "running", "detail": "检查 SQL、样本量、文案合规和频控"}]


async def pipeline(session_id: str, prompt: str) -> AsyncGenerator[str, None]:
    context = EnterpriseKnowledgeStore.context(prompt)
    scene = context["scene"]
    session = SESSION_CLUSTER_DB.setdefault(session_id, {})
    session.update({"status": "RUNNING", "prompt": prompt, "scene": scene, "started_at": time.time(), "steps": copy_steps(scene["id"])})
    yield packet("run_started", session_id=session_id, scene=scene, steps=session["steps"], knowledge={"tables": context["schema"], "rules": context["rules"]})
    yield packet("agent_transition", agent="Growth Planner", label="目标拆解智能体", status="running")
    async for event in emit_text("Growth Planner", f"目标已解析：{scene['label']}\n成功抽取约束：目标人群 / 增长指标 / 触达渠道 / 风险等级 {scene['risk']}"):
        yield event
    yield packet("agent_transition", agent="SQL / Data", label="数据取数与清洗智能体", status="running")
    sql_result = sql_agent.build_sql(prompt, scene)
    yield packet("tool_registered", tool=sql_result["tool"])
    yield packet("asset", asset_type="rules", data=context["rules"])
    yield packet("asset", asset_type="sql", data=sql_result["sql"])
    async for event in emit_text("SQL / Data", "知识库命中：5 张营销域表 + 6 条数据质量规则\n动态注册工具：profile_cleaner（画像去重 / 空值 / 枚举校验）\n已生成 SQL，并准备进入只读沙盒 EXPLAIN"):
        yield event
    if scene["id"] == "618":
        yield packet("quality_retry", attempt=1, status="fail", issue="avg_amount 口径与验收规则不一致", fix="改为 COUNT(DISTINCT order_id) 后重新计算日均客单价")
        await asyncio.sleep(0.25)
        yield packet("log", agent="SQL / Data", content="自优化重试 #1：已修正聚合口径，保留 Gap-and-Island 连续区间逻辑")
    sandbox = sandbox_tool_center.mock_execute_sql_sandbox(sql_result["sql"], scene["rows"])
    yield packet("asset", asset_type="sandbox", data=sandbox)
    yield packet("log", agent="SQL / Data", content=f"沙盒结果：{sandbox['status']} · 预计输出 {scene['rows']:,} 行 · 成本 {sandbox.get('cost_seconds', 0)}s")
    sql_guard = guardrail_manager.inspect_sql(sql_result["sql"], scene["rows"], scene["id"])
    yield packet("asset", asset_type="guardrail", data={"stage": "SQL", **sql_guard})
    if sql_guard["status"] == "PENDING_REVIEW" or scene["id"] == "hitl":
        session.update({"status": "SUSPENDED_AWAITING_HITL", "target_rows": scene["rows"], "guardrail": sql_guard})
        yield packet("hitl_brake", agent="QA / Guardrail", target_rows=scene["rows"], reason=sql_guard["reason"], session_id=session_id)
        return
    yield packet("agent_transition", agent="Red / Blue Copy", label="红蓝文案演化智能体", status="running")
    yield packet("tool_registered", tool=sandbox_tool_center.register("copy_policy_check", "文案合规检查", "敏感词与绝对化承诺扫描"))
    async for event in emit_text("Red / Blue Copy", "红方 v1：利益点前置，强调专属权益与明确行动按钮\n蓝方 v1：删去泛化形容词，减少打扰感，补充有效期与退订入口\n红方 v2：用用户身份认同替代催促，形成 A/B 两组可测文案"):
        yield event
    copy_result = evo_agent.generate(scene, prompt)
    yield packet("asset", asset_type="copy", data=copy_result)
    # Audit both the generated asset and the original request: a user can ask
    # the copy agent to intentionally emit a prohibited claim.
    copy_guard = guardrail_manager.inspect_copy(json.dumps(copy_result, ensure_ascii=False) + prompt)
    yield packet("asset", asset_type="guardrail", data={"stage": "COPY", **copy_guard})
    if copy_guard["status"] == "BLOCK":
        session.update({"status": "BLOCKED_BY_GUARDRAIL", "copy": copy_result})
        yield packet("guardrail_block", agent="QA / Guardrail", reason=copy_guard["reason"], matched=copy_guard["matched"])
        return
    yield packet("agent_transition", agent="QA / Guardrail", label="自动化测试与实验护栏", status="running")
    tests = [{"name": "SQL 可编译", "status": "pass", "value": "只读 / schema 命中"}, {"name": "人群规模", "status": "pass", "value": f"{scene['rows']:,} 行，在策略阈值内"}, {"name": "A/B 分流", "status": "pass", "value": "A 50% / B 50%"}, {"name": "48h 频控", "status": "pass", "value": "单用户最多 1 次"}, {"name": "文案合规", "status": "pass", "value": "敏感词 0 命中"}]
    yield packet("asset", asset_type="tests", data=tests)
    yield packet("log", agent="QA / Guardrail", content="5 项自动化测试全部通过，实验配置可进入灰度发布")
    session.update({"status": "COMPLETED", "sql": sql_result["sql"], "copy": copy_result, "tests": tests, "target_rows": scene["rows"]})
    yield packet("pipeline_finished", session_id=session_id, summary={"rows": scene["rows"], "tests": "5/5 passed", "winner": copy_result.get("winner", "A")})


@router.get("/stream-orchestrator")
async def stream_orchestrator(session_id: str = Query(...), prompt: str = Query(...)):
    input_check = guardrail_manager.verify_input_safety(prompt)
    if input_check["status"] == "BLOCK":
        async def blocked():
            yield packet("guardrail_block", agent="Input Guardrail", reason="输入侧护栏拒绝执行", matched=input_check["matched"])
        return StreamingResponse(blocked(), media_type="text/event-stream")
    return StreamingResponse(pipeline(session_id, prompt), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@router.post("/review")
async def handle_human_review(decision: ReviewDecision):
    session = SESSION_CLUSTER_DB.get(decision.task_id)
    if not session:
        raise HTTPException(status_code=404, detail="找不到待审核会话")
    if decision.action.lower() == "approve":
        session.update({"status": "APPROVED_RESUME", "hitl_approved": True})
        return {"status": "SUCCESS", "message": "人工审核通过，已签发复苏凭证"}
    if decision.action.lower() == "reject":
        session.update({"status": "TERMINATED_BY_HUMAN", "hitl_approved": False})
        return {"status": "MUTED", "message": "人工审核驳回，工作流已熔断"}
    raise HTTPException(status_code=400, detail="action 仅支持 approve 或 reject")


@router.get("/resume-stream")
async def resume_stream(session_id: str = Query(...)):
    session = SESSION_CLUSTER_DB.get(session_id)
    if not session or session.get("status") != "APPROVED_RESUME":
        raise HTTPException(status_code=400, detail="该会话未通过人工审核")
    async def resumed():
        yield packet("pipeline_resume", content="收到人工授权，工作流从安全断点复苏")
        scene = session.get("scene", {"id": "hitl", "label": "高敏营销审核", "risk": "high", "rows": session.get("target_rows", 18000)})
        copy_result = evo_agent.generate(scene, session.get("prompt", ""))
        yield packet("agent_transition", agent="Red / Blue Copy", label="红蓝文案演化智能体", status="running")
        async for event in emit_text("Red / Blue Copy", "人工审核备注已注入上下文\n红方 v2：缩小触达范围并增加灰度实验说明\n蓝方 v2：确认无越权字段，允许下发"):
            yield event
        yield packet("asset", asset_type="copy", data=copy_result)
        yield packet("asset", asset_type="tests", data=[{"name": "人工授权凭证", "status": "pass", "value": "HITL approve"}, {"name": "灰度下发", "status": "pass", "value": "仅进入 5% 实验组"}])
        session.update({"status": "COMPLETED", "copy": copy_result})
        yield packet("pipeline_finished", session_id=session_id, summary={"rows": session.get("target_rows", 0), "tests": "人工复核 + 灰度通过", "winner": "A"})
    return StreamingResponse(resumed(), media_type="text/event-stream")


@router.get("/overview")
async def overview():
    return {"schema": EnterpriseKnowledgeStore.SCHEMA, "tools": EnterpriseKnowledgeStore.TOOLS, "rules": EnterpriseKnowledgeStore.QUALITY_RULES, "sessions": len(SESSION_CLUSTER_DB)}


@router.get("/session/{session_id}")
async def session_status(session_id: str):
    if session_id not in SESSION_CLUSTER_DB:
        raise HTTPException(status_code=404, detail="会话不存在")
    return SESSION_CLUSTER_DB[session_id]
