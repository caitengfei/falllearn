# -*- coding: utf-8 -*-
"""学生端知识库：46 份岗课赛证文档全文检索 + 原文阅读。
数据源 = knowledge/ 目录（与 AI 直连通道同一来源，llm_direct 懒加载缓存）。"""
import os

from fastapi import APIRouter, Depends, HTTPException

from . import llm_direct
from .auth import current_user

router = APIRouter(prefix="/api/kb", tags=["kb"])

DIMS = ["01-岗", "02-课", "03-赛", "04-证", "05-元数据"]


def _dim_of(rel: str) -> str:
    top = rel.split("/", 1)[0]
    return top if top in DIMS else "其他"


@router.get("/search")
def kb_search(q: str = "", dim: str = "", u: dict = Depends(current_user)):
    """q 为空=目录清单（按维度）；q 非空=分词全文检索（空白分词，任一词命中即得，
    标题×10 + 正文出现次数（封顶 20），总分排序，附首命中词片段）。"""
    q = q.strip().lower()[:100]        # 输入上限：防超长查询串放大全库扫描开销
    toks = q.split()[:8]               # 分词上限：最多 8 个检索词
    out = []
    for rel, text in llm_direct.kb_fresh():
        d = _dim_of(rel)
        if dim and d != dim:
            continue
        title = rel.rsplit("/", 1)[-1].rsplit(".md", 1)[0]
        score, snippet, hit = 0, "", -1
        if q:
            tlow = title.lower()
            low = text.lower()
            for tok in toks:
                n_t, n_b = tlow.count(tok), low.count(tok)
                if n_t or n_b:
                    score += n_t * 10 + min(n_b, 20)
                    if hit < 0:
                        hit = low.find(tok)
            if score <= 0:
                continue
            if hit >= 0:
                s0 = max(0, hit - 40)
                snippet = ("…" if s0 > 0 else "") + text[s0:hit + 60].replace("\n", " ") + "…"
        else:
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    snippet = line[:80]
                    break
        out.append({"path": rel, "title": title, "dim": d, "score": score,
                    "snippet": snippet, "size": len(text)})
    # P2.15：向量 + 重排融合（仅当教师配置了嵌入模型且已向量时启用；任何异常静默退回关键词结果）
    if q and toks:
        try:
            out = _vector_enhance(q, out)
        except Exception:
            pass
    out.sort(key=lambda x: (-x["score"], x["path"]))
    return {"items": out[:50], "total": len(out)}


def _vector_enhance(q: str, out: list) -> list:
    """关键词结果之上叠加向量余弦（sim>0.30 的漏检文档补入），再按配置调用 rerank 重排。
    重排后按位置重写分值，保证最终 sort 保持重排顺序。"""
    from . import db as _db
    from .kb_admin import _from_blob, _load_cfg, _post_json, embed_query

    ecfg = _load_cfg("embed")
    if not ecfg:
        return out
    model = ecfg["model"]
    d = _db.get_db()
    rows = d.execute(
        "SELECT doc_path, chunk_idx, chunk_text, vector FROM kb_embeddings WHERE model=?",
        (model,)).fetchall()
    d.close()
    if not rows:
        return out  # 尚未向量化 → 维持纯关键词
    qv = embed_query(ecfg, q)
    qn = sum(x * x for x in qv) ** 0.5
    if qn <= 0:
        return out
    best = {}  # path -> (sim, chunk_text)
    for r in rows:
        v = _from_blob(r["vector"])
        if len(v) != len(qv):
            continue
        dot = sum(a * b for a, b in zip(qv, v))
        vn = sum(x * x for x in v) ** 0.5
        if vn <= 0:
            continue
        sim = dot / (qn * vn)
        p = r["doc_path"]
        if p not in best or sim > best[p][0]:
            best[p] = (sim, r["chunk_text"] or "")
    if not best:
        return out
    # 融合：关键词已有文档加向量分 + 补入向量高分漏检文档
    kw_paths = {x["path"] for x in out}
    for x in out:
        b = best.get(x["path"])
        if b:
            x["score"] += b[0] * 50
    for p, (sim, chunk) in best.items():
        if p not in kw_paths and sim > 0.30:
            top = p.split("/", 1)[0]
            dim = top if top in DIMS else "其他"
            title = p.rsplit("/", 1)[-1].rsplit(".md", 1)[0]
            out.append({"path": p, "title": title, "dim": dim,
                        "score": round(sim * 50, 1),
                        "snippet": "…" + chunk.replace("\n", " ")[:90] + "…",
                        "size": len(chunk)})
    # 重排：取 top15 调 rerank API（Jina/Cohere 兼容格式），失败不阻塞
    rcfg = _load_cfg("rerank")
    if rcfg and len(out) >= 2:
        try:
            top = sorted(out, key=lambda x: -x["score"])[:15]
            url = rcfg["base_url"].rstrip("/")
            if not url.endswith("/rerank"):
                url = url + "/rerank"
            r = _post_json(url, {"authorization": f"Bearer {rcfg['api_key']}"},
                           {"model": rcfg["model"], "query": q,
                            "documents": [f"{x['title']}。{(x['snippet'] or '')[:150]}" for x in top]},
                           timeout=45)
            order = sorted(r.get("results", []), key=lambda x: -x.get("relevance_score", 0))
            if len(order) == len(top) and all(0 <= it.get("index", -1) < len(top) for it in order):
                top_ids = {id(x) for x in top}
                rem = [x for x in out if id(x) not in top_ids]
                out = [top[it["index"]] for it in order] + rem
                for i, x in enumerate(top):  # 重写分值：最终 sort 保持重排顺序
                    x["score"] = 10000 - i
        except Exception:
            pass
    return out


@router.get("/doc")
def kb_doc(path: str, u: dict = Depends(current_user)):
    """按相对路径读原文（限定知识库内 .md，防目录穿越）。"""
    rel = path.replace("\\", "/").lstrip("/")
    parts = rel.split("/")
    if len(parts) != 2 or not rel.endswith(".md") or ".." in parts or "/" in parts[0]:
        raise HTTPException(400, "非法路径")
    if parts[0] not in DIMS:
        raise HTTPException(400, "非法目录")
    full = os.path.join(llm_direct.KB_DIR, *parts)
    # realpath 严格包含判定：既防 ../ 变体，也防目录内符号链接指向库外
    base = os.path.realpath(llm_direct.KB_DIR)
    real = os.path.realpath(full)
    try:
        if os.path.commonpath([base, real]) != base:
            raise HTTPException(400, "非法路径")
    except ValueError:
        raise HTTPException(400, "非法路径")
    if not os.path.isfile(real):
        raise HTTPException(404, "文档不存在")
    full = real
    with open(full, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    return {"path": rel, "content": text}