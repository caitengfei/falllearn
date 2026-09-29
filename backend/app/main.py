# -*- coding: utf-8 -*-
"""防跌学堂后端入口：FastAPI + SQLite + DSH 转发"""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import db
from .auth import router as auth_router  # noqa: F401
from .quiz import router as quiz_router
from .wrong import router as wrong_router
from .game import router as game_router
from .learn import router as learn_router
from .admin import router as admin_router
from .manage import router as manage_router, content_router, meta_router  # noqa: F401
from .aiops import router as aiops_router
from .kb import router as kb_router

app = FastAPI(title="防跌学堂", version="1.2.0")
# CORS 收敛：仅允许本平台来源（生产同源为主；5173 为本地 vite 开发）。
# 不开放 "*"：虽为 token 鉴权（无 cookie 窃取面），收敛后杜绝跨域探测面，审计可解释。
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://121.199.161.117:8010", "http://localhost:8010",
                                  "http://127.0.0.1:8010", "http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)  # JS/HTML 传输体积 -60%+（校园网/公网演示收益）


@app.middleware("http")
async def security_headers(_: Request, call_next):
    """基础安全响应头（防 MIME 嗅探 / 点击劫持 / 信息外泄）。"""
    resp = await call_next(_)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


_MSG_CN = {
    "Field required": "缺少必填项",
    "Input should be a valid string": "应为字符串",
    "Input should be a valid integer": "应为整数",
    "Input should be a valid number": "应为数字",
    "Input should be a valid boolean": "应为布尔值",
    "Input should be a valid list": "应为列表",
    "Input should be an valid list": "应为列表",
    "Input should be a valid dict": "应为对象",
    "String should have at least": "字符串太短（",
    "String should have at most": "字符串太长（",
    "Value error,": "取值不合法（",
}


def _cn_msg(msg: str) -> str:
    for k, v in _MSG_CN.items():
        if msg.startswith(k):
            rest = msg[len(k):]
            if k in ("String should have at least", "String should have at most", "Value error,"):
                return v + rest + "）"
            return v
    return msg


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    """FastAPI 422 → 400 + 中文可读错误（防御性：前端 api.js 也会再规整一层）。"""
    parts = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body",))
        m = _cn_msg(e.get("msg", "参数错误"))
        parts.append(f"{loc} {m}" if loc else m)
    return JSONResponse({"detail": "参数错误：" + "；".join(parts)}, status_code=400)

db.init_db()

for r in (auth_router, quiz_router, wrong_router, game_router, learn_router, admin_router,
          manage_router, content_router, meta_router, aiops_router, kb_router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "falllearn"}


# 上传文件（管理后台轮播图）——必须定义在 SPA 回退之前
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")


def _within(base: str, candidate: str) -> bool:
    """路径包含判定（commonpath 严格版，规避 startswith 的前缀兄弟目录误判）。"""
    try:
        return os.path.commonpath([base, candidate]) == base
    except ValueError:
        return False


@app.get("/uploads/{name}", include_in_schema=False)
async def upload_file(name: str):
    candidate = os.path.normpath(os.path.join(UPLOADS, name))
    if _within(os.path.normpath(UPLOADS), candidate) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return JSONResponse({"detail": "文件不存在"}, status_code=404)


# 前端 dist（构建后挂载；开发期走 vite dev server 5173）
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    """SPA 静态资源 + 路由回退（必须定义在 API 路由之后）。"""
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "接口不存在（API 404）"}, status_code=404)
    if os.path.isdir(DIST):
        candidate = os.path.normpath(os.path.join(DIST, full_path))
        if full_path and _within(DIST, candidate) and os.path.isfile(candidate):
            # 带 hash 的 /assets/* 长缓存；其余（如 index.html）不缓存，保证发版即生效
            if full_path.startswith("assets/"):
                return FileResponse(candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"})
            return FileResponse(candidate)
        # 安全收敛（2026-09-29 观测到 58.251.94.154 扫描 /dump.sql.lz、/backups.rar、
        # /core/config/databases.yml、/pmd/index.php 等）：带文件扩展名的路径不可能是
        # 前端客户端路由，一律 404，避免对扫描探测返回 200+index.html。
        if "." in full_path.rsplit("/", 1)[-1]:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        idx = os.path.join(DIST, "index.html")
        if os.path.isfile(idx):
            return FileResponse(idx, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "页面或资源不存在（404）"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)