# -*- coding: utf-8 -*-
"""管理后台 · AI 管理端点：模型自由选择 / 知识库 / AI 出题 / AI 判卷。
任务会话：固定 sid=falllearn-aiops（gksc-student 预设，KB 工作区），模型随平台设置切换
（session.selectModel，DSH 原生支持，实测目录见 settings.yaml llm-pi-ai）。
"""
import asyncio
import json
import os
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db, dsh_client, llm_direct
from .auth import require_teacher

router = APIRouter(prefix="/api/admin/ai", tags=["aiops"])

# 知识库目录：默认仓库内 knowledge/（可移植到服务器；与 DSH preset 工作区内容一致，
# 2026-09-28 逐文件 hash 核对 26/26），可用 env FALLLEARN_KB 覆盖
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.environ.get("FALLLEARN_KB") or os.path.join(_PROJECT_ROOT, "knowledge")
PRESET = "gksc-student"
AIOPS_SID = "falllearn-aiops"
client = dsh_client.make_client()

_model_cache = {"at": 0, "value": None}


async def _task_session():
    """获取/自愈 AI 任务会话，并把模型切到平台设置（若配置了）。"""
    d = db.get_db()
    try:
        for attempt in (1, 2):
            try:
                await dsh_client.get_history(client, AIOPS_SID, 1)
                break
            except Exception as e:
                if attempt == 1 and ("not found" in str(e) or "no session" in str(e).lower()):
                    await dsh_client.create_session(client, AIOPS_SID, KB, PRESET)
                    break
                raise
        raw = db.get_setting(d, "ai_model")
        if raw:
            sel = json.loads(raw)
            try:
                await dsh_client.select_model(client, AIOPS_SID, sel["provider"], sel["model"])
            except Exception:
                pass  # 模型切换失败不阻塞任务（沿用当前模型）
    finally:
        d.close()
    return AIOPS_SID


def _assistant_text(events) -> str:
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
    return "".join(step_texts.get(max_step, [])) if max_step else ""


def _extract_json(text):
    """从模型输出里抠出 JSON 数组（容忍 ```json 包裹/前后废话）。"""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    s, e = t.find("["), t.rfind("]")
    if s >= 0 and e > s:
        try:
            return json.loads(t[s:e + 1])
        except Exception:
            pass
    return None


async def _rpc(coro, what: str, deadline_s: int = 30):
    """单发 DSH RPC 的硬超时：防 hang 的 RPC 拖死整个请求（原只有墙钟总超时）。"""
    try:
        return await asyncio.wait_for(coro, timeout=deadline_s)
    except asyncio.TimeoutError:
        raise RuntimeError(f"{what} 超时（>{deadline_s}s）")


async def _run_task(sid: str, prompt: str, timeout: int = 240):
    """发任务 → 轮询 history → 返回 (assistant_text, base_seq)。中途澄清卡自动催办。"""
    h0 = await _rpc(dsh_client.get_history(client, sid, 20), "读取会话历史")
    base = max((ev.get("event", ev).get("seq", 0) for ev in h0.get("events", [])), default=0)
    await _rpc(dsh_client.send_prompt(client, sid, prompt), "发送任务")
    t0 = time.time()
    last_text = ""
    nagged = False
    while time.time() - t0 < timeout:
        await asyncio.sleep(6)
        h = await _rpc(dsh_client.get_history(client, sid, 300), "读取会话历史")
        events = [ev for ev in h.get("events", []) if ev.get("event", ev).get("seq", 0) > base]
        # 澄清卡：催办（系统任务不等待用户）
        for ev in events:
            e = ev.get("event", ev)
            if e.get("type") == "tool/call" and (e.get("data") or {}).get("name") == "ask_user_question" and not nagged:
                nagged = True
                await _rpc(dsh_client.send_prompt(client, sid, "（这是系统任务，无需澄清，请继续直接输出结果。）"), "催办")
                break
        text = _assistant_text(events)
        if text and text != last_text:
            last_text = text
        if _extract_json(text):
            return text, base
    raise RuntimeError(f"AI 任务超时（{timeout}s 未返回可解析结果）")


# 渠道友好名（原始 id 太技术化，管理端展示用）
def _group_friendly(g: dict) -> dict:
    gid = g.get("id", "")
    if gid.startswith("freehub"):
        g = {**g, "name": "FreeHub 免费渠道（GLM / DeepSeek / SenseNova）", "short": "FreeHub"}
    elif gid == "qwen-gateway":
        g = {**g, "name": "Qwen 本地网关", "short": "Qwen"}
    else:
        g = {**g, "short": g.get("short") or gid}
    return g


# ================= 模型选择 =================
@router.get("/models")
async def models_list(u: dict = Depends(require_teacher)):
    """DSH 实时模型目录（qwen/deepseek/glm/…）+ 当前平台设置 + 会话默认模型。"""
    d = db.get_db()
    cur_raw = db.get_setting(d, "ai_model")
    d.close()
    cur = json.loads(cur_raw) if cur_raw else None
    # 直连模式：目录即直连模型，不依赖 DSH（部署服务器只有直连通道）
    dcfg = llm_direct.get_cfg()
    if dcfg:
        return {"items": [{"id": "direct", "name": "直连通道（OpenAI 兼容接口）", "short": "直连",
                           "models": [{"id": dcfg["model"], "name": dcfg["model"] + "（直连）"}]}],
                "current": cur, "routable": False, "direct": True}
    if _model_cache["value"] and time.time() - _model_cache["at"] < 600:
        return {"items": [_group_friendly(g) for g in _model_cache["value"]], "current": cur}
    try:
        sid = await _task_session()
        cat = await dsh_client.call(client, "session.models", {"sessionId": sid})
    except Exception as e:
        return {"items": [], "current": cur, "routable": False, "warning": f"DSH 中继不可用：{e}"}
    _model_cache.update(at=time.time(), value=cat.get("groups", []))
    return {"items": [_group_friendly(g) for g in cat.get("groups", [])],
            "current": cur, "routable": cat.get("routable", False),
            "current_session": cat.get("current")}


class ModelIn(BaseModel):
    provider: str | None = None
    model: str | None = None


@router.post("/model")
async def model_select(m: ModelIn, u: dict = Depends(require_teacher)):
    """切换平台 AI 模型：先切任务会话成功、再落设置（失败不留脏配置）。
    空 body = 清除设置（回落到任务会话默认模型）。"""
    provider = (m.provider or "").strip()
    model = (m.model or "").strip()
    if not provider and not model:
        d = db.get_db()
        db.set_setting(d, "ai_model", "")
        d.commit()
        d.close()
        return {"ok": True, "cleared": True}
    if not provider or not model:
        raise HTTPException(400, "provider 与 model 必须同时提供")
    sid = await _task_session()
    try:
        r = await dsh_client.select_model(client, sid, provider, model)
    except Exception as e:
        raise HTTPException(502, f"模型切换失败（未保存设置）：{e}")
    d = db.get_db()
    db.set_setting(d, "ai_model", json.dumps({"provider": provider, "model": model}, ensure_ascii=False))
    d.commit()
    d.close()
    return {"ok": True, "selected": r.get("selected")}


# ================= AI 直连通道（OpenAI 兼容，默认 DeepSeek） =================
class DirectIn(BaseModel):
    base_url: str
    model: str
    api_key: str | None = None


@router.get("/direct")
async def direct_get(u: dict = Depends(require_teacher)):
    return llm_direct.public_view(llm_direct.get_cfg())


@router.post("/direct")
async def direct_save(b: DirectIn, u: dict = Depends(require_teacher)):
    """保存直连配置（settings.ai_direct）。api_key 留空=沿用现有密钥（无现存则 400）。"""
    base_url = (b.base_url or "").strip().rstrip("/")
    model = (b.model or "").strip()
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "base_url 需以 http:// 或 https:// 开头")
    if not model:
        raise HTTPException(400, "model 不能为空")
    d = db.get_db()
    raw = db.get_setting(d, "ai_direct")
    d.close()
    old = {}
    if raw:
        try:
            old = json.loads(raw)
        except Exception:
            old = {}
    key = (b.api_key or "").strip() or (old.get("api_key") or "")
    if not key:
        raise HTTPException(400, "请填写 api_key（留空表示沿用现有密钥，当前未设置）")
    d = db.get_db()
    db.set_setting(d, "ai_direct",
                   json.dumps({"base_url": base_url, "model": model, "api_key": key}, ensure_ascii=False))
    d.commit()
    d.close()
    llm_direct.kb_fresh(max_age=0)
    return {"ok": True, "selected": {"base_url": base_url, "model": model}}


@router.delete("/direct")
async def direct_clear(u: dict = Depends(require_teacher)):
    """清除直连配置 → 学生端 AI 问答/出题/判卷回落 DSH 中继（仅本机可用）。"""
    d = db.get_db()
    db.set_setting(d, "ai_direct", "")
    d.commit()
    d.close()
    return {"ok": True, "cleared": True}


@router.post("/direct/test")
async def direct_test(u: dict = Depends(require_teacher)):
    cfg = llm_direct.get_cfg()
    if not cfg:
        raise HTTPException(400, "直连通道未配置")
    t0 = time.time()
    try:
        text = await llm_direct.complete(cfg, [{"role": "user", "content": "只回复「好的」两个字"}],
                                         max_tokens=200, timeout=60)
        return {"ok": True, "latency": round(time.time() - t0, 1), "reply": text[:80]}
    except Exception as e:
        raise HTTPException(502, f"连接测试失败：{e}")


# ================= 知识库 =================
@router.get("/kb")
def kb_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    items = []
    for root, _dirs, files in os.walk(KB):
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, KB).replace("\\", "/")
            try:
                size = os.path.getsize(p)
                mtime = int(os.path.getmtime(p))
                head = open(p, encoding="utf-8", errors="ignore").read(160).replace("\n", " ")
            except Exception:
                continue
            items.append({"path": rel, "size": size, "mtime": mtime, "head": head})
    items.sort(key=lambda x: x["path"])
    d.close()
    return {"items": items, "count": len(items), "root": KB}


def _kb_abs(rel: str) -> str:
    rel = (rel or "").strip().replace("\\", "/")
    # 显式拒绝绝对路径 / 反斜杠绝对路径 / 上级跳转（KB 是真实教研材料，不容许误写）
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        raise HTTPException(400, f"路径非法：{rel}（仅允许 KB 内相对路径，如 05-元数据/说明.md）")
    p = os.path.normpath(os.path.join(KB, rel))
    if not p.startswith(os.path.normpath(KB) + os.sep) or not p.lower().endswith(".md"):
        raise HTTPException(400, "仅允许操作知识库目录内的 .md 文件")
    return p


class KbWriteIn(BaseModel):
    path: str
    content: str
    force: bool = False


@router.post("/kb")
def kb_write(b: KbWriteIn, u: dict = Depends(require_teacher)):
    p = _kb_abs(b.path)
    depth = b.path.strip("/").count("/")
    if depth > 1:
        raise HTTPException(400, "路径最多两级（目录/文件.md）")
    if not b.content.strip():
        raise HTTPException(400, "内容不能为空")
    existed = os.path.isfile(p)
    if existed and not b.force:
        raise HTTPException(400, f"已存在文档 {b.path.strip('/')}，确认覆盖请带 force=true")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(b.content)
    return {"ok": True, "path": os.path.relpath(p, KB), "overwritten": existed}


class KbDeleteIn(BaseModel):
    path: str


@router.delete("/kb")
def kb_delete(b: KbDeleteIn, u: dict = Depends(require_teacher)):
    p = _kb_abs(b.path)
    if not os.path.isfile(p):
        raise HTTPException(404, "文件不存在")
    os.remove(p)
    return {"ok": True}


# ================= AI 出题 =================
class GenIn(BaseModel):
    cluster_id: str = "general"
    count: int = 10
    qtypes: str = "单选,判断"  # 如 "单选,多选,判断"


@router.post("/generate-questions")
async def gen_questions(g: GenIn, u: dict = Depends(require_teacher)):
    """AI 按簇出题：任务会话读 KB 真实内容 → JSON → 返回预览（未入库）。"""
    if g.cluster_id not in db.CLUSTER_IDS:
        raise HTTPException(400, "cluster_id 非法")
    count = max(3, min(int(g.count), 20))
    cname = db.CLUSTER_NAMES[g.cluster_id]
    qtypes = [t for t in g.qtypes.split(",") if t in ("单选", "多选", "判断")] or ["单选", "判断"]
    d = db.get_db()
    model_raw = db.get_setting(d, "ai_model")
    d.close()
    dcfg = llm_direct.get_cfg()
    model_name = dcfg["model"] + "（直连）" if dcfg else (json.loads(model_raw)["model"] if model_raw else "默认")
    prompt = (
        f"这是管理后台系统任务（不适用四栏格式、不要提问）：请基于工作区知识库（01-岗/02-课/03-赛/04-证 目录的真实文档，先 grep/read 取材）"
        f"为「{cname}」出 {count} 道题，题型分布：{('、'.join(qtypes))}。\n"
        "要求：① 内容必须来自知识库真实材料，不得编造；② 答案唯一正确；③ 干扰项 plausible；④ 难度 1-3。\n"
        "只输出一个 JSON 数组（不要 markdown 包裹、不要解释）：\n"
        f'单选: {{"qtype":"单选","stem":"题干（含（　））","options":["A全文","B全文","C全文","D全文"],"answer":"A","difficulty":2}}\n'
        f'多选: {{"qtype":"多选","stem":"...","options":["...","...","...","..."],"answer":"AB","difficulty":2}}\n'
        f'判断: {{"qtype":"判断","stem":"陈述句","options":[],"answer":"A","difficulty":1}}（A=对 B=错）'
    )
    t0 = time.time()
    if llm_direct.get_cfg():
        try:
            text = await llm_direct.run_task_direct(prompt, timeout=300)
        except Exception as e:
            raise HTTPException(502, f"AI 出题失败：{e}")
    else:
        sid = await _task_session()
        try:
            text, _base = await _run_task(sid, prompt, timeout=300)
        except Exception as e:
            raise HTTPException(502, f"AI 出题失败：{e}")
    data = _extract_json(text)
    if not data:
        raise HTTPException(502, "AI 未返回可解析的题目 JSON：" + text[:200])
    items = []
    for q in data:
        if not isinstance(q, dict) or not q.get("stem"):
            continue
        qt = q.get("qtype") or "单选"
        if qt not in ("单选", "多选", "判断"):
            qt = "单选"
        opts = q.get("options") or []
        ans = str(q.get("answer") or "").strip().upper()
        if qt == "判断":
            opts = ["对（A）", "错（B）"]
            ans = "A" if ans in ("A", "对", "T", "TRUE") else "B"
        elif not opts:
            continue
        items.append({
            "qtype": qt, "stem": str(q["stem"]).strip(), "options": [str(o).strip() for o in opts],
            "answer": ans, "difficulty": max(1, min(int(q.get("difficulty") or 2), 3)),
            "cluster_id": g.cluster_id,
        })
    return {"items": items, "model": model_name, "elapsed": round(time.time() - t0, 1),
            "raw": text[:500] if len(items) < count else ""}


class SaveQIn(BaseModel):
    items: list


@router.post("/questions/save")
def gen_save(b: SaveQIn, u: dict = Depends(require_teacher)):
    """确认预览后入库（origin=AI生成）。"""
    d = db.get_db()
    n = 0
    for q in b.items:
        if not q.get("stem") or not q.get("answer"):
            continue
        d.execute(
            "INSERT INTO questions(qtype,cluster_id,difficulty,stem,options,answer,source_doc,origin) VALUES(?,?,?,?,?,?,?,?)",
            (q["qtype"], q.get("cluster_id", "general"), q.get("difficulty", 2),
             q["stem"], json.dumps(q.get("options") or [], ensure_ascii=False), q["answer"],
             "AI 生成", "AI生成"))
        n += 1
    d.commit()
    d.close()
    return {"ok": True, "count": n}


# ================= AI 判卷 =================
class GradeIn(BaseModel):
    attempt_id: int


@router.post("/grade")
async def ai_grade(g: GradeIn, u: dict = Depends(require_teacher)):
    """对一份已交卷做 AI 复核判卷：逐题判断 + 分数对比，落 ai_grades。"""
    d = db.get_db()
    att = d.execute(
        "SELECT a.*, u.name student_name FROM attempts a JOIN users u ON u.id=a.student_id WHERE a.id=?",
        (g.attempt_id,)).fetchone()
    if not att:
        d.close()
        raise HTTPException(404, "考试记录不存在")
    if att["status"] != "done":
        d.close()
        raise HTTPException(400, "该卷未交卷")
    rows = d.execute(
        "SELECT a.student_answer, q.id, q.stem, q.qtype, q.options, q.answer, q.source_doc "
        "FROM answers a JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=? ORDER BY q.id",
        (g.attempt_id,)).fetchall()
    d.close()
    if not rows:
        raise HTTPException(400, "该卷没有答题记录")
    lines = []
    for r in rows:
        opts = json.loads(r["options"]) or []
        if r["qtype"] == "判断" or not opts:
            opts = ["对（A）", "错（B）"]
        opt_s = "；".join(f"{chr(65 + i)} {o}" for i, o in enumerate(opts))
        lines.append(f"[{r['id']}]（{r['qtype']}）{r['stem']}\n  选项：{opt_s}\n  标准答案：{r['answer']}　学生答案：{r['student_answer'] or '（空）'}")
    prompt = (
        "这是管理后台判卷系统任务（不适用四栏格式、不要提问）。请逐题判断学生答案是否正确：与标准答案一致判对；"
        "表述不同但语义等价也判对；其余判错。\n"
        + "\n\n".join(lines)
        + '\n只输出一个 JSON 数组（不要 markdown 包裹、不要解释）：[{"qid":123,"correct":true,"reason":"一句话"}]'
    )
    t0 = time.time()
    if llm_direct.get_cfg():
        try:
            text = await llm_direct.run_task_direct(prompt, timeout=300)
        except Exception as e:
            raise HTTPException(502, f"AI 判卷失败：{e}")
    else:
        sid = await _task_session()
        try:
            text, _ = await _run_task(sid, prompt, timeout=300)
        except Exception as e:
            raise HTTPException(502, f"AI 判卷失败：{e}")
    data = _extract_json(text)
    if not data:
        raise HTTPException(502, "AI 未返回可解析的判卷 JSON：" + text[:200])
    by_qid = {r["id"]: r for r in rows}
    detail, n_correct = [], 0
    for item in data:
        qid = item.get("qid")
        if qid not in by_qid:
            continue
        ok = bool(item.get("correct"))
        n_correct += int(ok)
        detail.append({"qid": qid, "stem": by_qid[qid]["stem"][:60], "correct": ok,
                       "reason": str(item.get("reason") or "")[:120],
                       "student_answer": by_qid[qid]["student_answer"], "answer": by_qid[qid]["answer"]})
    total = len(by_qid)
    ai_score = round(100 * n_correct / total, 1) if total else 0
    rule_score = att["score"] if att["score"] is not None else -1
    d = db.get_db()
    # 幂等：同一卷重复判卷 = 覆盖旧结果（UNIQUE(attempt_id) 下先删后插）
    d.execute("DELETE FROM ai_grades WHERE attempt_id=?", (g.attempt_id,))
    d.execute(
        "INSERT INTO ai_grades(attempt_id,model,ai_score,detail,diff,created_at) VALUES(?,?,?,?,?,?)",
        (g.attempt_id, "AI复核", ai_score, json.dumps(detail, ensure_ascii=False),
         round(ai_score - (rule_score or 0), 1), int(time.time())))
    d.commit()
    d.close()
    return {"attempt_id": g.attempt_id, "ai_score": ai_score, "rule_score": rule_score,
            "diff": round(ai_score - (rule_score or 0), 1), "n": total,
            "correct": n_correct, "elapsed": round(time.time() - t0, 1), "detail": detail}


@router.get("/grades")
def grades_list(attempt_id: int = 0, u: dict = Depends(require_teacher)):
    d = db.get_db()
    sql = "SELECT * FROM ai_grades"
    args = []
    if attempt_id:
        sql += " WHERE attempt_id=?"
        args.append(attempt_id)
    sql += " ORDER BY id DESC LIMIT 20"
    rows = d.execute(sql, args).fetchall()
    out = []
    for r in rows:
        att = d.execute("SELECT score FROM attempts WHERE id=?", (r["attempt_id"],)).fetchone()
        out.append({
            "id": r["id"], "attempt_id": r["attempt_id"], "model": r["model"],
            "ai_score": r["ai_score"], "rule_score": att["score"] if att else None,
            "diff": r["diff"], "created_at": r["created_at"],
            "detail": json.loads(r["detail"]) if r["detail"] else [],
        })
    d.close()
    return {"items": out}