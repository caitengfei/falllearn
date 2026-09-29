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
    out.sort(key=lambda x: (-x["score"], x["path"]))
    return {"items": out[:50], "total": len(out)}


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