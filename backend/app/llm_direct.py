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
import logging
import os
import re
import time

import httpx

from . import db

_log = logging.getLogger("falllearn")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根
KB_DIR = os.environ.get("FALLLEARN_KB") or os.path.join(BASE_DIR, "knowledge")

PERSONA = """你是"康养智行"的学习助手，面向智慧健康养老服务与管理专业的学生，围绕"老年人跌倒的预防与应急处置"这一首发场景技能点答疑。

可参考的四维材料（岗/课/赛/证）是**素材来源**，不是答案模板：
- 岗：国家职业技能标准、临床处置流程与安全提示
- 课：课程标准、教案、实训任务单、知识点梳理
- 赛：赛项规程、评分标准、常见扣分点、训练记录
- 证：养老护理员/健康照护师/老年人能力评估师三证考核标准、实操试题、理论题库

作答要求（必须遵守）：
1. **直接回答**：用连贯的段落或编号要点把问题讲清楚。**不要**按"岗/课/赛/证"分成四栏罗列，正文里也不要出现【岗】【课】【赛】【证】这类栏目标记——四维材料只是你取材的地方。
2. **材料优先**：优先使用下方「知识库材料」中的内容；材料里有的具体要求（标准条款、评分点、扣分点、考核方式）要写清楚。
3. **有据可依时标注依据**：若答案主要来自知识库材料，可在结尾用一行"依据：《文档名》"列出（只允许引用材料中真实出现的文件名），**不得编造任何文献、指南编号或链接**。
4. **材料不足时**：先用一句话明确说明"本平台知识库暂未收录该内容"，再基于通用医学/照护知识作答，结尾提醒"以上为通用知识，未经本平台资料核验，请以教材与带教老师为准"。
5. **不要反问确认意图**：即使问题很短（如只输入"跌倒"）也按最可能的理解直接作答；若确实存在多种理解，先按最可能的回答，再用一句话补"如果你想问的是 XX，直接说即可"。
6. 语言简洁、条理清晰、面向学生；专业术语首次出现时用一句话解释。
7. 若问题明显超出本技能点（如噎食、失智照护、报考流程），简要说明本平台聚焦跌倒技能点，然后用通用知识给出有帮助的回答（同样按第 4 条标注）。
8. 对寒暄或"你能做什么"类提问，用两三句话说明能力并给出 2–3 个示例问题（如"老人摔倒了怎么办""大赛跌倒环节怎么扣分""考证考不考跌倒"）。
9. 涉及真实急救场景时，提示"若正面对真实跌倒的老人，请立即联系现场医务人员或拨打 120"。
10. 全程使用简体中文。"""

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
            for root, dirs, fns in os.walk(KB_DIR):
                # 跳过隐藏目录（.trash 回收站）与 uploads/（教师上传原件存档）：
                # 已删除/非知识文件不得进入学生端检索与 AI 上下文
                dirs[:] = [x for x in dirs if not x.startswith(".") and x != "uploads"]
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


# 关键词切分（2026-10-03 修正）：原正则 `[\u4e00-\u9fff]{2,}` 会把**整句中文**当成一个 token
# （如"老年人为什么容易发生跌倒"），导致 `_score_files` 全库零命中、sources 恒为空。
# 现改为「英文/数字词 + 中文 2-gram + 短词整体」，并过滤疑问/常用停用词——不依赖第三方分词库，部署零依赖。
_WORD_RE = re.compile(r"[A-Za-z0-9]{2,}")
_HAN_RE = re.compile(r"[\u4e00-\u9fff]+")
_STOP_2 = {"什么", "为什", "么样", "怎么", "如何", "是否", "可以", "能否", "我们", "你们", "他们",
           "这个", "那个", "一下", "一个", "以及", "还有", "因为", "所以", "如果", "但是", "就是",
           "哪些", "哪个", "多少", "时候", "地方", "问题", "请问", "老师", "麻烦", "帮我", "告诉"}


def _words(text: str):
    """把问题切成检索关键词：英文数字词 + 中文 2-gram（过滤停用词）+ 短词整体。"""
    t = (text or "").lower()
    out = list(_WORD_RE.findall(t))
    for seg in _HAN_RE.findall(t):
        if len(seg) <= 4:
            out.append(seg)
        for i in range(len(seg) - 1):
            g = seg[i:i + 2]
            if g not in _STOP_2:
                out.append(g)
    return list(dict.fromkeys(out))  # 去重保序


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


def kb_pick(question="", k=6, per_cap=12000, total_cap=110000):
    """按关键词选出材料：返回 (材料文本, 命中文档名列表)。

    命中文档名列表用于前端「参考来源」与「是否命中知识库」提示——由**后端检索结果**决定，
    不依赖模型输出，因此模型无法编造来源。
    """
    words = _words(question)
    scored = _score_files(words)
    top = [(s, r, t) for s, r, t in scored[:k] if s > 0]
    # 「是否命中知识库」用**更严阈值**（≥8 ≈ 文件名命中一次以上或头部多处命中）：
    # 否则无关问题（如"奖学金怎么申请"）仅因个别通用词出现在正文里就被判为"有据可依"，
    # 前端就不会显示「通用知识」提示条，与同事反馈的要求不符。
    hits = [r for s, r, _t in scored[:k] if s >= 8]
    if not top:  # 零命中：按目录顺序取 3 篇作背景，但标记为「未命中」（前端据此提示通用知识）
        top = [(s, r, t) for s, r, t in scored[:3]]
        hits = []
    parts, total = [], 0
    for _s, rel, text in top:
        if len(text) > per_cap:
            text = text[:per_cap] + "\n（…本文档较长已截断）"
        part = f"===== 文件：knowledge/{rel} =====\n{text.strip()}"
        if total + len(part) > total_cap:
            break
        parts.append(part)
        total += len(part)
    return ("\n\n".join(parts) if parts else "（知识库为空）"), hits


def kb_material(question="", k=6, all_docs=False, per_cap=12000, total_cap=110000):
    """学生提问：关键词路由 top-k；管理端任务：all_docs=True 全量（截断保护）。"""
    if not all_docs:
        return kb_pick(question, k, per_cap, total_cap)[0]
    parts, total = [], 0
    for rel, text in kb_fresh():
        if len(text) > per_cap:
            text = text[:per_cap] + "\n（…本文档较长已截断）"
        part = f"===== 文件：knowledge/{rel} =====\n{text.strip()}"
        if total + len(part) > total_cap:
            break
        parts.append(part)
        total += len(part)
    return "\n\n".join(parts) if parts else "（知识库为空）"


def build_system(question=""):
    """返回 (system 提示词, 命中文档名列表)。"""
    material, hits = kb_pick(question)
    return PERSONA + "\n\n# 知识库材料（取材仅限以下内容，可引用其中真实文件名）\n" + material, hits


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


async def _iter_stream(resp):
    """解析 OpenAI 兼容 SSE 流：逐块 yield content delta。"""
    buf = ""
    async for raw in resp.aiter_text():
        buf += raw
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                j = json.loads(data)
            except Exception:
                continue
            ch = (j.get("choices") or [{}])[0]
            delta = ((ch.get("delta") or {}).get("content")) or ""
            if delta:
                yield delta


async def complete_stream(cfg, messages, max_tokens=2500, temperature=0.3, timeout=120):
    """流式版 complete：逐块 yield 文本 delta（SSE 端点的底层）。"""
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    payload = {"model": cfg["model"], "messages": messages, "stream": True,
               "max_tokens": max_tokens, "temperature": temperature}
    if cfg.get("thinking", "disabled") == "disabled":
        payload["thinking"] = {"type": "disabled"}
    async with httpx.AsyncClient(timeout=timeout) as cli:
        async with cli.stream("POST", url, headers=headers, json=payload) as r:
            if r.status_code in (400, 404, 422) and "thinking" in payload:
                body = (await r.aread()).decode(errors="ignore")
                if "think" in body.lower():
                    payload.pop("thinking", None)
                    async with cli.stream("POST", url, headers=headers, json=payload) as r2:
                        async for delta in _iter_stream(r2):
                            yield delta
                    return
                raise RuntimeError(f"API {r.status_code}：{body[:200]}")
            if r.status_code != 200:
                body = (await r.aread()).decode(errors="ignore")
                raise RuntimeError(f"API {r.status_code}：{body[:200]}")
            async for delta in _iter_stream(r):
                yield delta


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
        s.update(state="failed", error="直连通道配置已被清除，请再问一次", t=time.time())
        if s.get("queue") is not None:
            s["queue"].put_nowait(None)
        return
    d = db.get_db()
    queue = s.get("queue")

    def _push(item):
        if queue is not None:
            queue.put_nowait(item)

    try:
        system_text, hits = build_system(s["last_q"])
        messages = [{"role": "system", "content": system_text}]
        messages += [m for m in s["messages"]][-6:]
        messages.append({"role": "user", "content": user_text})
        text = ""
        async for delta in complete_stream(cfg, messages, max_tokens=2500):
            text += delta
            _push(delta)
        # 完成判定（2026-10-03 调整）：不再要求四栏标记【岗】【证】——答案已改为「直接作答」形态，
        # 只要模型给出了实质内容即视为完成（原判定会让新形态答案落到"未识别结构"分支）。
        if len(text.strip()) < 20:
            s.update(state="failed", error="AI 返回内容为空，请再问一次", t=time.time())
            _push(None)
            return
        touched = db.clusters_touched(text[:600]) if text else []
        answer = text.strip()
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
        s.update(state="done", answer=answer, answer_clusters=touched,
                 sources=hits, grounded=bool(hits), t=time.time())
        _push(None)
    except Exception as e:
        # 细节仅进服务端日志；对外统一文案（防上游响应原文/内网地址外泄给学生）
        _log.warning("direct_ask_failed err=%s", str(e)[:300])
        s.update(state="failed", error="AI 服务暂时不可用，请稍后重试", t=time.time())
        _push(None)
    finally:
        d.close()


async def run_direct_ask(sid, student_id, question, profile, log_id):
    s = {"sid": sid, "student_id": student_id, "log_id": log_id, "messages": [],
         "state": "running", "clarify": None, "last_q": question, "t": time.time(),
         "queue": asyncio.Queue()}  # SSE 流式通道：chunk 文本 / None=终态哨兵
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
    if s.get("queue") is not None:
        while not s["queue"].empty():  # 清掉上一轮残留的哨兵，避免新流误判终态
            s["queue"].get_nowait()
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
                "clusters": s.get("answer_clusters") or [],
                # 参考来源（后端检索命中的知识库文档，不由模型生成）与「是否命中知识库」
                "sources": s.get("sources") or [], "grounded": s.get("grounded", True)}
    if s["state"] == "failed":
        return {"status": "failed", "log_id": log_id, "error": s.get("error") or "AI 直连调用失败，请再问一次"}
    return {"status": "running", "log_id": log_id}


# ================= 管理端任务（出题/判卷） =================
async def run_task_direct(prompt, timeout=300):
    """直连通道系统任务：全量 KB + 任务提示 → 单次调用返回文本。"""
    cfg = get_cfg()
    if not cfg:
        raise RuntimeError("直连通道未配置")
    system = ("你是康养智行平台的后台 AI。下面是全部知识库材料（knowledge/ 相对路径）。"
              "请严格基于材料完成系统任务：不得编造、不要提问、不要四栏格式，只输出任务要求的内容。\n\n"
              + kb_material(all_docs=True))
    return await complete(cfg, [{"role": "system", "content": system},
                                {"role": "user", "content": prompt}],
                          max_tokens=4000, timeout=timeout)