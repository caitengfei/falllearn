# -*- coding: utf-8 -*-
"""登录鉴权：bcrypt + JWT（30 天），student/teacher 角色"""
import os
import secrets as _secrets
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, APIRouter, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from . import db

# JWT 签名密钥：环境变量优先；否则自动生成随机密钥并持久化（跨重启稳定）。
# 不写死在源码里——源码会公开（比赛仓库），硬编码签名密钥等于允许任何人伪造教师 token。
_SECRET_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jwt_secret")


def _load_secret():
    env = os.environ.get("FALLLEARN_JWT_SECRET")
    if env:
        return env
    try:
        with open(_SECRET_FILE, "r", encoding="utf-8") as f:
            s = f.read().strip()
        if len(s) >= 32:
            return s
    except OSError:
        pass
    s = _secrets.token_urlsafe(32)
    try:
        with open(_SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(s)
        os.chmod(_SECRET_FILE, 0o600)  # 尽力而为（Windows 下忽略）
    except OSError:
        pass  # 只读文件系统：退回内存随机（重启后旧 token 失效，需重新登录）
    return s


SECRET = _load_secret()
ALG = "HS256"
TTL = 30 * 86400

# 登录防爆破（公网演示保护）：同 IP 10 分钟内失败 5 次 → 锁定 10 分钟（内存计数，单实例够用）
FAIL_MAX = 5
FAIL_WINDOW = 600
FAIL_LOCK_SEC = 600
_FAIL_LOGINS: dict = {}   # ip -> [失败时间戳...]
_LOCKED: dict = {}        # ip -> 解锁时间戳

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    student_no: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)  # 上限防超长密码拖慢 bcrypt


def _token(user):
    return jwt.encode(
        {"sub": str(user["id"]), "sno": user["student_no"], "role": user["role"],
         "exp": int(time.time()) + TTL},
        SECRET, ALG,
    )


def _pub(user):
    return {"id": user["id"], "student_no": user["student_no"], "name": user["name"], "role": user["role"]}


@router.post("/login")
def login(body: LoginIn, request: Request):
    ip = request.client.host if request.client else "?"
    now = int(time.time())
    locked_until = _LOCKED.get(ip, 0)
    if locked_until > now:
        raise HTTPException(429, f"登录失败次数过多，请 {max(1, (locked_until - now) // 60)} 分钟后再试")
    d = db.get_db()
    u = d.execute("SELECT * FROM users WHERE student_no=?", (body.student_no.strip(),)).fetchone()
    if not u:
        d.close()
        _login_fail(ip, now)
        raise HTTPException(401, "账号不存在（学号/工号）")
    if not bcrypt.checkpw(body.password.encode(), u["pwd_hash"].encode()):
        d.close()
        _login_fail(ip, now)
        raise HTTPException(401, "密码错误")
    # 停用账号在登录入口即拦截（否则拿到 token 后处处 403，用户卡死；不计入失败计数）
    if not u["enabled"]:
        d.close()
        raise HTTPException(403, "账号已停用，请联系管理员")
    d.close()
    _FAIL_LOGINS.pop(ip, None)
    return {"token": _token(u), "user": _pub(u)}


def _login_fail(ip: str, now: int):
    hist = [t for t in _FAIL_LOGINS.get(ip, []) if now - t < FAIL_WINDOW]
    hist.append(now)
    _FAIL_LOGINS[ip] = hist
    if len(hist) >= FAIL_MAX:
        _LOCKED[ip] = now + FAIL_LOCK_SEC
    # 内存有界：淘汰过期窗口/已解锁的 IP（防大量伪造源 IP 撑爆进程内存）
    if len(_FAIL_LOGINS) > 2000:
        for k in [k for k, ts in _FAIL_LOGINS.items() if not ts or now - ts[-1] > FAIL_WINDOW]:
            _FAIL_LOGINS.pop(k, None)
    if len(_LOCKED) > 2000:
        for k in [k for k, t in _LOCKED.items() if t <= now]:
            _LOCKED.pop(k, None)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "未登录")
    try:
        p = jwt.decode(creds.credentials, SECRET, algorithms=[ALG], options={"require": ["exp"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "token 无效或过期")
    sub = p.get("sub")
    if not sub:
        raise HTTPException(401, "token 无效或过期")
    d = db.get_db()
    try:
        u = d.execute("SELECT * FROM users WHERE id=?", (sub,)).fetchone()
        if not u:
            raise HTTPException(401, "用户不存在")
        if not u["enabled"]:
            raise HTTPException(403, "账号已停用，请联系管理员")
        return dict(u)
    finally:
        d.close()


def require_teacher(u: dict = Depends(current_user)) -> dict:
    if u["role"] != "teacher":
        raise HTTPException(403, "需要教师角色")
    return u


@router.get("/me")
def me(u: dict = Depends(current_user)):
    d = db.get_db()
    points = d.execute("SELECT points FROM points_cache WHERE student_id=?", (u["id"],)).fetchone()
    mastery = d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()
    badge_count = d.execute("SELECT COUNT(*) c FROM user_badges WHERE student_id=?", (u["id"],)).fetchone()["c"]
    practice_count = d.execute("SELECT COUNT(*) c FROM attempts WHERE student_id=? AND status='done'",
                               (u["id"],)).fetchone()["c"]
    last = d.execute("SELECT score FROM attempts WHERE student_id=? AND status='done' "
                     "ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    wrong_due = d.execute(
        "SELECT COUNT(*) c FROM wrong_records WHERE student_id=? AND status='active' AND due_at<=?",
        (u["id"], int(time.time()))).fetchone()["c"]
    hours = db.student_hours(d, u["id"])
    d.close()
    return {
        **_pub(u),
        "points": points["points"] if points else 0,
        "mastery": {m["cluster_id"]: m["level"] for m in mastery},
        "badge_count": badge_count,
        "practice_count": practice_count,
        "last_score": last["score"] if last else None,
        "wrong_due": wrong_due,
        "hours": hours,
    }


@router.post("/logout")
def logout(u: dict = Depends(current_user)):
    return {"ok": True}