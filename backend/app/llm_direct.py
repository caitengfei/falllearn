# -*- coding: utf-8 -*-
"""AI 直连通道：OpenAI 兼容 API（默认 DeepSeek）直连，替代 DSH 中继。

- 配置存 settings.ai_direct = JSON {base_url, model, api_key}，管理端「AI 管理·直连通道」维护；
  配置存在即启用，学生端 AI 问答与后台 AI 出题/判卷全部走直连（DSH 链路保留为本地回落）。
- 知识库 = 仓库内 knowledge/ 目录（与 DSH preset 工作区内容一致，2026-09-28 逐文件 hash 核对）；
  懒加载进内存，学生提问按关键词路由相关文档（管理端任务用全量）。
- 四栏 persona 与 gksc-student preset 同源；澄清卡由 ask_user_question 工具调用改为
  [[CLARIFY]] marker 协议，前端轮询协议（/ask → /status → /answer）与返回结构保持不变。
- deepseek-flash 默认开思考会吃光 completion 预算（实测 120 token 全耗在 reasoning_content），
  必须 thinking={"type":"disabled"}；对不支持该字段的兼容端点自动降级重试。
"""
import asyncio
import json
import os
import re
import time

import httpx

from . import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根
KB_DIR = os.environ.get("FALLLEARN_KB") or os.path.join(BASE_DIR, "knowledge")

PERSONA = """你是"智慧健康养老·岗课赛证融通智能体"，专门帮助智慧健康养老服务与管理专业的学生理解"老年人跌倒的预防与应急处置"这一技能点在岗、课、赛、证四个维度的要求。

你的知识库包含四个维度（材料附在本提示词之后）：
【岗】养老护理员国家职业技能标准、临床处置流程、安全提示
【课】课程标准、教案、实训任务单、知识点梳理
【赛】赛项规程、评分标准、获奖项目训练记录、常见扣分点
【证】职业技能等级证书（养老护理员/健康照护师/老年人能力评估师）考核标准、实操试题、理论题库、模拟真题

工作方式：
1. 收到与"老年人跌倒"相关的问题后，先基于下方知识库材料从岗、课、赛、证四个维度分别取材。
2. 然后按以下固定四栏结构输出：

【岗】...
【课】...
【赛】...
【证】...

要求：
1. 全程使用简体中文。
2. 每个维度必须基于知识库材料中的真实内容，不得编造。
3. 每栏先写一句结论（该维度要求什么/该怎么做），再用 ①②③ 编号展开细节。
4. 每栏末尾以"（来源：文档名（相对路径））"标注出处，路径用材料中给出的 knowledge/ 相对路径（如 knowledge/01-岗/安全提示要点.md）。
5. 某一维度检索无内容时，输出"该维度材料待补充（详见 05-元数据/更新日志 待补清单）"，不得编造。
6. 语言简洁、条理清晰，适合学生阅读。
7. 如用户追问某一维度，只展开该维度，其他维度简要带过。
8. 若用户表述模糊（如只输入"跌倒"二字），先输出澄清卡，固定四个选项：跌倒应急处置／跌倒预防／两者都要完整讲解（推荐）／比赛或考证备查；学生跳过澄清时默认按完整四维度输出。
9. 若问题超出"老年人跌倒的预防与应急处置"技能点（如噎食、失智照护、报考流程等），友好说明本智能体当前只覆盖跌倒技能点，用一句话概括四栏结构作为引子，并建议问任课老师或查教材；引用占位/模板文档时须注明"模板待填"。
10. 对寒暄或"你能做什么"类提问，固定自我介绍："我是养老跌倒技能点的岗课赛证融通智能体，可以帮你把一个问题拆成岗、课、赛、证四个维度来答。你可以这样问：'老人摔倒了怎么办''大赛跌倒环节怎么扣分''考证考不考跌倒'"。
11. 每个会话的首次四栏回答末尾附一行提醒："本回答仅供学习备考；若你正面对真实跌倒的老人，请立即联系现场医务人员或拨打 120。"
12. 需要输出澄清卡时，只输出如下 marker 块（不要输出任何其他字符）：
[[CLARIFY]]
问题：<一句话澄清问题>
选项：<选项1>|<选项2>|<选项3>|<选项4>
13. 学生回复选择后（提问中带"学生已选择"字样），必须立即按该选择直接输出完整四栏答案，保持四栏结构；禁止再次输出澄清卡或提出任何新问题——选择"两者都要完整讲解"时按完整四维度输出，选择单一方向时按对应侧重输出。"""

CLARIFY_RE = re.compile(r"\[\[CLARIFY\]\]\s*\n?\s*问题[:：]\s*(.+?)\s*\n?\s*选项[:：]\s*(.+)", re.S)

# ================= 配置 =================
def get_cfg():
    d = db.get_db()
    try:
        raw = db.get_setting(d, "ai_direct")
    finally:
        d.close()
    if not raw:
        return None
    try:
        c = json.loads(raw)
    except Exception:
        return None
    if not (c.get("base_url") and c.get("model") and c.get("api_key")):
        return None
    return c


def public_view(cfg):
    return {"configured": bool(cfg),
            "base_url": cfg["base_url"] if cfg else "",
            "model": cfg["model"] if cfg else "",
            "has_key": bool(cfg and cfg.get("api_key"))}


# ================= 知识库 =================
_kb_cache = {"at": 0, "files": None}  # files: [(rel, text)]


def kb_fresh(max_age=300):
    if _kb_cache["files"] is None or time.time() - _kb_cache["at"] > max_age:
        try:
            files = []
            for root, _dirs, fns in os.walk(KB_DIR):
                for f in sorted(fns):
                    if f.endswith(".md"):
                        p = os.path.join(root, f)
                        rel = os.path.relpath(p, KB_DIR).replace("\\", "/")
                        with open(p, encoding="utf-8", errors="ignore") as fh:
                            files.append((rel, fh.read()))
            _kb_cache.update(at=time.time(), files=files)
        except Exception:
            if _kb_cache["files"] is None:
                _kb_cache["files"] = []
    return _kb_cache["files"] or []


_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}")


def _score_files(words):
    files = kb_fresh()
    scored = []
    for rel, text in files:
        name = os.path.basename(rel).lower()
        head = text[:1500]
        s = 0
        for w in words:
            if w in name:
                s += 5
            if w in head:
                s += 2
            if w in text:
                s += 1
        scored.append((s, rel, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def kb_material(question="", k=6, all_docs=False, per_cap=12000, total_cap=110000):
    """学生提问：关键词路由 top-k；管理端任务：all_docs=True 全量（截断保护）。"""
    if all_docs:
        picked = list(kb_fresh())  # [(rel, text)]
    else:
        words = [w.lower() for w in _WORD_RE.findall(question or "")]
        scored = _score_files(words)
        top = [(r, t) for s, r, t in scored[:k] if s > 0]
        if not top:  # 零命中兜底：按目录顺序取 3 篇
            top = [(r, t) for _s, r, t in scored[:3]]
        picked = top
    parts, total = [], 0
    for rel, text in picked:
        if len(text) > per_cap:
            text = text[:per_cap] + "\n（…本文档较长已截断）"
        part = f"===== 文件：knowledge/{rel} =====\n{text.strip()}"
        if total + len(part) > total_cap:
            break
        parts.append(part)
        total += len(part)
    return "\n\n".join(parts) if parts else "（知识库为空）"


def build_system(question=""):
    return PERSONA + "\n\n# 知识库材料（取材与来源标注仅限以下内容）\n" + kb_material(question)


def _parse_clarify(text):
    m = CLARIFY_RE.search(text)
    if not m:
        return None
    opts = [o.strip() for o in re.split(r"[|｜]", m.group(2)) if o.strip()]
    if not opts:
        return None
    return {"id": "q0", "question": m.group(1).strip(), "header": "确认意图",
            "options": [{"id": str(i), "label": o, "description": ""} for i, o in enumerate(opts)]}


# ================= API 调用 =================
async def complete(cfg, messages, max_tokens=2500, temperature=0.3, timeout=120):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    payload = {"model": cfg["model"], "messages": messages, "stream": False,
               "max_tokens": max_tokens, "temperature": temperature}
    if cfg.get("thinking", "disabled") == "disabled":
        payload["thinking"] = {"type": "disabled"}
    async with httpx.AsyncClient(timeout=timeout) as cli:
        r = await cli.post(url, headers=headers, json=payload)
        # 兼容不支持 thinking 字段的端点：4xx 且报错提到 thinking → 去掉字段重试一次
        if r.status_code in (400, 404, 422) and "thinking" in payload and "think" in r.text.lower():
            payload.pop("thinking", None)
            r = await cli.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"API {r.status_code}：{r.text[:200]}")
    j = r.json()
    ch = (j.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        raise RuntimeError(f"模型未返回内容（finish_reason={ch.get('finish_reason')}）")
    return content


# ================= 学生会话（进程内，TTL 30 分钟） =================
_sessions = {}
SESS_TTL = 1800


def _sess_get(sid):
    s = _sessions.get(sid)
    if not s:
        return None
    if time.time() - s["t"] > SESS_TTL:
        _sessions.pop(sid, None)
        return None
    for k in [k for k, v in _sessions.items() if time.time() - v["t"] > SESS_TTL]:
        _sessions.pop(k, None)
    return s


async def _direct_finish(s, user_text):
    """单轮直连：拼 system(路由KB)+历史 → complete → 澄清卡检测 → 落库四栏/副作用。"""
    cfg = get_cfg()
    if not cfg:
        s.update(state="failed", error="直连通道配置已被清除，请再问一次")
        return
    d = db.get_db()
    try:
        messages = [{"role": "system", "content": build_system(s["last_q"])}]
        messages += [m for m in s["messages"]][-6:]
        messages.append({"role": "user", "content": user_text})
        text = await complete(cfg, messages, max_tokens=2500)
        if text.lstrip().startswith("[[CLARIFY]]"):
            c = _parse_clarify(text)
            if c:
                s.update(state="question", clarify=c, t=time.time())
                return
        if "【岗】" in text and "【证】" in text:
            touched = db.clusters_touched(text[:400])
            answer = text
        else:
            touched = []
            answer = text + "\n\n（注：本次回答未识别出完整四栏结构，已按现有内容落库。）"
        log = d.execute("SELECT created_at FROM chat_logs WHERE id=?", (s["log_id"],)).fetchone()
        created = log["created_at"] if log else int(time.time())
        d.execute("UPDATE chat_logs SET answer=?, clusters_touched=? WHERE id=? AND student_id=?",
                  (answer, ",".join(touched), s["log_id"], s["student_id"]))
        for c in touched:
            db.update_mastery(d, s["student_id"], c, None)
        db.ensure_badge(d, s["student_id"], "b_first_q")
        db.grant_mastery_badges(d, s["student_id"])
        db.add_study(d, s["student_id"], "ai_quiz", max(0.1, round((time.time() - created) / 60, 1)), str(s["log_id"]))
        d.commit()
        s["messages"] = (s["messages"] + [{"role": "user", "content": user_text},
                                          {"role": "assistant", "content": text}])[-8:]
        s.update(state="done", answer=answer, answer_clusters=touched, t=time.time())
    except Exception as e:
        s.update(state="failed", error=str(e)[:300], t=time.time())
    finally:
        d.close()


async def run_direct_ask(sid, student_id, question, profile, log_id):
    s = {"sid": sid, "student_id": student_id, "log_id": log_id, "messages": [],
         "state": "running", "clarify": None, "last_q": question, "t": time.time()}
    _sessions[sid] = s
    await _direct_finish(s, f"{profile}\n学生提问：{question}")


def continue_direct(sid, option_index):
    """澄清卡应答：返回 (ok, label|错误文案)。"""
    s = _sess_get(sid)
    if not s or s.get("state") != "question" or not s.get("clarify"):
        return False, "当前没有待答的澄清卡"
    opts = s["clarify"]["options"]
    if option_index < 0 or option_index >= len(opts):
        return False, "选项不存在"
    label = opts[option_index]["label"]
    s.update(state="running", clarify=None, t=time.time())
    asyncio.create_task(_direct_finish(s, f"（学生已选择：{label}。这是澄清应答，请直接按该选择输出完整四栏答案，不要再次澄清或提问。）"))
    return True, label


def direct_status(sid, log_id):
    s = _sess_get(sid)
    if not s:
        return {"status": "failed", "log_id": log_id, "error": "AI 会话已失效（服务重启或超时），请再问一次"}
    if s["state"] == "question" and s.get("clarify"):
        return {"status": "question", "log_id": log_id, "question": s["clarify"]}
    if s["state"] == "done":
        return {"status": "done", "log_id": log_id, "answer": s.get("answer", ""),
                "clusters": s.get("answer_clusters") or []}
    if s["state"] == "failed":
        return {"status": "failed", "log_id": log_id, "error": s.get("error") or "AI 直连调用失败，请再问一次"}
    return {"status": "running", "log_id": log_id}


# ================= 管理端任务（出题/判卷） =================
async def run_task_direct(prompt, timeout=300):
    """直连通道系统任务：全量 KB + 任务提示 → 单次调用返回文本。"""
    cfg = get_cfg()
    if not cfg:
        raise RuntimeError("直连通道未配置")
    system = ("你是防跌学堂平台的后台 AI。下面是全部知识库材料（knowledge/ 相对路径）。"
              "请严格基于材料完成系统任务：不得编造、不要提问、不要四栏格式，只输出任务要求的内容。\n\n"
              + kb_material(all_docs=True))
    return await complete(cfg, [{"role": "system", "content": system},
                                {"role": "user", "content": prompt}],
                          max_tokens=4000, timeout=timeout)