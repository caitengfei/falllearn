# -*- coding: utf-8 -*-
"""学习对话：转发 DSH gksc-student 会话；澄清卡中转；四栏落库+mastery+积分

链路（实测 2026-09-28）：
- POST /api/session.create {cwd=KB, agentPreset=gksc-student} 每生一个会话
- POST /api/session.prompt 发问（档案摘要附在提问后）
- 澄清卡 = history 里的 tool/call 事件（name=ask_user_question, arguments.questions）
- 应答：优先 POST /api/respond（需 WS 拿问题 rpcId）；WS 不可用时降级为追问"（已选择：X）"
- 四栏答案 = history 里 assistant/chunk 文本块拼接（data.chunk.type=text-delta）
"""
import asyncio
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db, dsh_client, llm_direct
from .auth import current_user

router = APIRouter(prefix="/api/learn", tags=["learn"])

KB = r"E:\lilei\跌倒-岗课赛证知识库"
PRESET = "gksc-student"
# 每学生每日 AI 提问上限（含澄清应答轮次外的新提问）；防演示账号被公网陌生人刷
AI_DAILY_CAP = 30
client = dsh_client.make_client()

# 已应答问题的会话（sid -> 时间戳），防 status 重复报告 question；10 分钟未活跃自动淘汰（防泄漏）
_answered_sessions = {}
_ANSWERED_TTL = 600


def _answered_touch(sid):
    _answered_sessions[sid] = time.time()
    # 顺带清理过期项，保持集合有界
    cutoff = time.time() - _ANSWERED_TTL
    for k in [k for k, t in _answered_sessions.items() if t < cutoff]:
        _answered_sessions.pop(k, None)


def _answered(sid) -> bool:
    t = _answered_sessions.get(sid)
    if t is None:
        return False
    if time.time() - t > _ANSWERED_TTL:
        _answered_sessions.pop(sid, None)
        return False
    return True


# 已切换过模型的 DSH 会话（sid -> (provider, model)），避免每问重复 RPC
_applied_models = {}


async def _apply_model(sid: str):
    """把平台「AI 管理·模型选择」的设置切到该会话（幂等）。"""
    d = db.get_db()
    raw = db.get_setting(d, "ai_model")
    d.close()
    if not raw:
        return
    try:
        sel = json.loads(raw)
    except Exception:
        return
    key = (sel.get("provider"), sel.get("model"))
    if not key[0] or not key[1] or _applied_models.get(sid) == key:
        return
    if len(_applied_models) > 500:
        _applied_models.clear()
    try:
        await dsh_client.select_model(client, sid, key[0], key[1])
        _applied_models[sid] = key
    except Exception:
        pass


async def _ensure_session(client, d, student_id) -> str:
    """返回学生 DSH 会话 id；不存在时在 DSH 端真正创建（session.create）后落库。"""
    row = d.execute("SELECT dsh_session_id FROM student_sessions WHERE student_id=?", (student_id,)).fetchone()
    if row:
        return row["dsh_session_id"]
    sid = str(uuid.uuid4())
    await dsh_client.create_session(client, sid, KB, PRESET)
    d.execute("INSERT INTO student_sessions(student_id,dsh_session_id,dsh_preset,created_at) VALUES(?,?,?,?)",
              (student_id, sid, PRESET, int(time.time())))
    d.commit()
    return sid


def _parse_question(events):
    """从 history 事件里找 ask_user_question 工具调用（仅当未被应答）。
    已被应答的判据：该 tool/call 之后出现 step>1 的事件或新的 user/message。"""
    target = None
    target_seq = -1
    for ev in events:
        e = ev.get("event", ev)
        if e.get("type") == "tool/call" and (e.get("data") or {}).get("name") == "ask_user_question":
            target = e
            target_seq = e.get("seq", -1)
    if target is None:
        return None
    answered = False
    for ev in events:
        e = ev.get("event", ev)
        if e.get("seq", -1) <= target_seq:
            continue
        d = e.get("data") or {}
        if d.get("step", 0) > 1:
            answered = True
            break
        if e.get("type") == "user/message":
            answered = True
            break
    if answered:
        return None
    try:
        args = json.loads(target.get("data", {}).get("arguments", "{}"))
    except Exception:
        return None
    qs = args.get("questions") or []
    if not qs:
        return None
    q0 = qs[0]
    return {
        "call_id": (target.get("data") or {}).get("callId"),
        "rpc_id": None,  # rpcId 只在 WS question/requested 帧里
        "id": q0.get("id"),
        "question": q0.get("question", ""),
        "header": q0.get("header", ""),
        "options": [{"id": str(i), "label": o.get("label", ""), "description": o.get("description", "")}
                    for i, o in enumerate(q0.get("options", []))],
    }


def _assistant_text(events) -> str:
    """拼接 assistant 文本块（text-delta），只取最后一步（最后一个 step 的 text 块）。"""
    texts = []
    step_texts = {}
    max_step = 0
    for ev in events:
        e = ev.get("event", ev)
        if e.get("type") != "assistant/chunk":
            continue
        d = e.get("data") or {}
        step = d.get("step", 0)
        max_step = max(max_step, step)
        chunk = d.get("chunk") or {}
        if chunk.get("type") == "text-delta" and chunk.get("text"):
            step_texts.setdefault(step, []).append(chunk["text"])
    for step, ts in sorted(step_texts.items()):
        if step == max_step:
            texts.append("".join(ts))
    return "\n".join(texts)


class AskIn(BaseModel):
    question: str


@router.post("/ask", response_model=None)
async def ask(body: AskIn, u: dict = Depends(current_user)):
    q = body.question.strip()
    if len(q) < 2:
        raise HTTPException(400, "问题太短")
    d = db.get_db()
    # 每日 AI 提问上限（公网演示保护：防陌生人拿演示账号无限白嫖 AI 资源）
    ask_today = d.execute(
        "SELECT COUNT(*) FROM chat_logs WHERE student_id=? AND question<>'' AND created_at > ?",
        (u["id"], int(time.time()) - 86400)).fetchone()[0]
    if ask_today >= AI_DAILY_CAP:
        d.close()
        raise HTTPException(429, "今日 AI 提问次数已用完，明日再来")
    # 档案注入
    lv = {r["cluster_id"]: r["level"] for r in d.execute(
        "SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()}
    weak = [f"{db.CLUSTER_NAMES[c]} {int(v)}" for c, v in lv.items() if v < 60]
    profile = f"（学习档案·薄弱簇：{'、'.join(weak) if weak else '无'}）"
    # —— 直连通道优先（settings.ai_direct 配置存在即启用；否则回落 DSH 中继）——
    if llm_direct.get_cfg():
        sid = str(uuid.uuid4())
        d.execute(
            "INSERT INTO student_sessions(student_id,dsh_session_id,dsh_preset,created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(student_id) DO UPDATE SET dsh_session_id=excluded.dsh_session_id,"
            " dsh_preset=excluded.dsh_preset, created_at=excluded.created_at",
            (u["id"], sid, "direct", int(time.time())))
        log_id = d.execute(
            "INSERT INTO chat_logs(student_id,dsh_session_id,question,answer,clusters_touched,created_at,dsh_base_seq) VALUES(?,?,?,?,?,?,?)",
            (u["id"], sid, q, "", "", int(time.time()), 0)).lastrowid
        # 提问积分（日上限 20）
        today_pts = d.execute(
            "SELECT COALESCE(SUM(delta),0) FROM points_log WHERE student_id=? AND reason='AI 问答' AND created_at > ?",
            (u["id"], int(time.time()) - 86400)).fetchone()[0]
        if today_pts < 20:
            db.add_points(d, u["id"], 2, "AI 问答", str(log_id))
        d.commit()
        d.close()
        asyncio.create_task(llm_direct.run_direct_ask(sid, u["id"], q, profile, log_id))
        return {"session_id": sid, "log_id": log_id, "status": "running"}
    ctx = profile + "\n学生提问：" + q
    # 创建/复用 DSH 会话并转发；会话在 DSH 端丢失（实例重启等）时自愈重建
    # base_seq = 提问前会话事件水位线：status 只认水位线之后的事件，
    # 防止同会话第二问把上一问的答案当成自己的（实测竞态串档）
    sid = None
    base_seq = 0
    for attempt in (1, 2):
        sid = await _ensure_session(client, d, u["id"])
        try:
            await _apply_model(sid)
            h0 = await dsh_client.get_history(client, sid, 50)
            base_seq = max((ev.get("event", ev).get("seq", 0) for ev in h0.get("events", [])), default=0)
            await dsh_client.send_prompt(client, sid, ctx)
            break
        except Exception as e:
            if attempt == 1 and "not found" in str(e):
                d.execute("DELETE FROM student_sessions WHERE student_id=?", (u["id"],))
                d.commit()
                continue
            d.close()
            raise HTTPException(502, f"DSH 转发失败：{e}")
    # 预落一条 chat_log
    log_id = d.execute(
        "INSERT INTO chat_logs(student_id,dsh_session_id,question,answer,clusters_touched,created_at,dsh_base_seq) VALUES(?,?,?,?,?,?,?)",
        (u["id"], sid, q, "", "", int(time.time()), base_seq)).lastrowid
    d.commit()
    # 提问积分（日上限 20）
    today_pts = d.execute(
        "SELECT COALESCE(SUM(delta),0) FROM points_log WHERE student_id=? AND reason='AI 问答' AND created_at > ?",
        (u["id"], int(time.time()) - 86400)).fetchone()[0]
    if today_pts < 20:
        db.add_points(d, u["id"], 2, "AI 问答", str(log_id))
    d.commit()
    d.close()
    return {"session_id": sid, "log_id": log_id, "status": "running"}


class AnswerIn(BaseModel):
    log_id: int
    option_index: int  # 学生选的选项下标


@router.post("/answer", response_model=None)
async def answer(body: AnswerIn, u: dict = Depends(current_user)):
    d = db.get_db()
    row = d.execute("SELECT dsh_session_id, dsh_preset FROM student_sessions WHERE student_id=?", (u["id"],)).fetchone()
    log = d.execute("SELECT * FROM chat_logs WHERE id=? AND student_id=?", (body.log_id, u["id"])).fetchone()
    if not row or not log:
        d.close()
        raise HTTPException(403, "会话/记录不存在")
    sid = row["dsh_session_id"]
    if row["dsh_preset"] == "direct":
        d.close()
        ok, label = llm_direct.continue_direct(sid, body.option_index)
        if not ok:
            raise HTTPException(400, label)
        return {"ok": True, "method": "direct", "label": label}
    try:
        h = await dsh_client.get_history(client, sid, 200)
        events = h.get("events", [])
        q = _parse_question(events)
        if not q:
            d.close()
            raise HTTPException(400, "当前没有待答的澄清卡")
        label = q["options"][body.option_index]["label"] if body.option_index < len(q["options"]) else ""
        rpc = q.get("rpc_id")
        if not rpc:
            # 短 WS 连接拿 pending 问题的 rpcId（连接时重放）
            fetched = await dsh_client.fetch_pending_question(sid)
            rpc = fetched[0] if fetched else None
        if rpc:
            await dsh_client.respond_question(client, rpc, sid,
                                              [{"id": q["id"] or "q0", "selected": [label]}])
            method = "respond"
        else:
            # 降级：追问选择，让 agent 继续
            await dsh_client.send_prompt(client, sid, f"（学生已选择：{label}）请按此选择继续完整作答。")
            method = "re-prompt"
    except HTTPException:
        d.close()
        raise
    except Exception as e:
        d.close()
        raise HTTPException(502, f"应答失败：{e}")
    _answered_touch(sid)
    d.close()
    return {"ok": True, "method": method, "label": label}


@router.get("/status", response_model=None)
async def status(session_id: str, log_id: int, u: dict = Depends(current_user)):
    d = db.get_db()
    row = d.execute("SELECT dsh_session_id, dsh_preset FROM student_sessions WHERE student_id=?", (u["id"],)).fetchone()
    if not row or row["dsh_session_id"] != session_id:
        d.close()
        raise HTTPException(403, "会话不属于你")
    if row["dsh_preset"] == "direct":
        d.close()
        return llm_direct.direct_status(session_id, log_id)
    # 只取本次提问水位线之后的事件（防串档）
    log = d.execute("SELECT dsh_base_seq, created_at FROM chat_logs WHERE id=? AND student_id=?",
                    (log_id, u["id"])).fetchone()
    base = (log["dsh_base_seq"] if log else 0) or 0
    elapsed = (int(time.time()) - (log["created_at"] if log else int(time.time())))
    try:
        h = await dsh_client.get_history(client, session_id, 300)
        events = [ev for ev in h.get("events", []) if ev.get("event", ev).get("seq", 0) > base]
    except Exception as e:
        d.close()
        raise HTTPException(502, f"history 失败：{e}")
    if not _answered(session_id):
        q = _parse_question(events)
        if q:
            d.close()
            return {"status": "question", "log_id": log_id, "question": q}
    text = _assistant_text(events)
    if text and "【岗】" in text and "【证】" in text:
        touched = db.clusters_touched(text[:400])
        d.execute("UPDATE chat_logs SET answer=?, clusters_touched=? WHERE id=? AND student_id=?",
                  (text, ",".join(touched), log_id, u["id"]))
        for c in touched:
            db.update_mastery(d, u["id"], c, None)
        db.ensure_badge(d, u["id"], "b_first_q")
        db.grant_mastery_badges(d, u["id"])
        db.add_study(d, u["id"], "ai_quiz", (int(time.time()) - (log["created_at"] if log else int(time.time()))) / 60,
                     str(log_id))
        d.commit()
        d.close()
        return {"status": "done", "log_id": log_id, "answer": text, "clusters": touched}
    # 超时兜底：模型漏掉【岗】【证】标记时，150s 内已有文本则强制落库，避免前端无限轮询
    if elapsed > 150:
        if text:
            d.execute("UPDATE chat_logs SET answer=?, clusters_touched=? WHERE id=? AND student_id=?",
                      (text + "\n\n（注：本次回答未识别出完整四栏结构，已按现有内容落库。）", "", log_id, u["id"]))
            db.ensure_badge(d, u["id"], "b_first_q")
            db.add_study(d, u["id"], "ai_quiz", (int(time.time()) - (log["created_at"] if log else int(time.time()))) / 60,
                         str(log_id))
            d.commit()
            d.close()
            return {"status": "done", "log_id": log_id, "answer": text, "clusters": [], "incomplete": True}
        d.close()
        return {"status": "failed", "log_id": log_id, "error": "AI 老师这次没有返回内容，请再问一次"}
    d.close()
    return {"status": "running", "log_id": log_id}


@router.get("/stream")
async def stream(session_id: str, log_id: int, u: dict = Depends(current_user)):
    """SSE 流式输出（直连通道）：chunk 逐字下发，终态事件带完整答案/澄清卡/错误。
    DSH 中继通道不支持流式（返回 400，前端回落 /status 轮询）。"""
    d = db.get_db()
    row = d.execute("SELECT dsh_session_id, dsh_preset FROM student_sessions WHERE student_id=?",
                    (u["id"],)).fetchone()
    if not row or row["dsh_session_id"] != session_id:
        d.close()
        raise HTTPException(403, "会话不属于你")
    direct = row["dsh_preset"] == "direct"
    d.close()
    if not direct:
        raise HTTPException(400, "当前通道不支持流式，请用轮询")
    s = llm_direct._sess_get(session_id)
    if not s or s.get("queue") is None:
        raise HTTPException(404, "AI 会话已失效，请再问一次")

    async def gen():
        q = s["queue"]
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": ping\n\n"  # 心跳保活（防中间代理掐空闲连接）
                if s.get("state") in ("done", "question", "failed"):
                    break
                continue
            if item is None:
                break
            yield "data: " + json.dumps({"type": "chunk", "t": item}, ensure_ascii=False) + "\n\n"
        st = s.get("state")
        if st == "done":
            ev = {"type": "done", "answer": s.get("answer", ""),
                  "clusters": s.get("answer_clusters") or []}
        elif st == "question" and s.get("clarify"):
            ev = {"type": "question", "question": s["clarify"]}
        else:
            ev = {"type": "failed", "error": s.get("error") or "AI 直连调用失败，请再问一次"}
        yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
def history(u: dict = Depends(current_user)):
    d = db.get_db()
    rows = d.execute(
        "SELECT question, answer, clusters_touched, created_at FROM chat_logs "
        "WHERE student_id=? AND answer != '' ORDER BY id DESC LIMIT 30", (u["id"],)).fetchall()
    out = [{"question": r["question"], "answer": r["answer"],
            "clusters": r["clusters_touched"], "at": r["created_at"]} for r in rows]
    d.close()
    return {"items": out}