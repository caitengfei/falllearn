# -*- coding: utf-8 -*-
"""登录鉴权：bcrypt + JWT（30 天），student/teacher 角色"""
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import db

SECRET = "falllearn-dev-secret-2026"  # 演示用；生产走环境变量
ALG = "HS256"
TTL = 30 * 86400

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    student_no: str
    password: str


def _token(user):
    return jwt.encode(
        {"sub": str(user["id"]), "sno": user["student_no"], "role": user["role"],
         "exp": int(time.time()) + TTL},
        SECRET, ALG,
    )


def _pub(user):
    return {"id": user["id"], "student_no": user["student_no"], "name": user["name"], "role": user["role"]}


@router.post("/login")
def login(body: LoginIn):
    d = db.get_db()
    u = d.execute("SELECT * FROM users WHERE student_no=?", (body.student_no.strip(),)).fetchone()
    if not u:
        raise HTTPException(401, "账号不存在（学号/工号）")
    if not bcrypt.checkpw(body.password.encode(), u["pwd_hash"].encode()):
        raise HTTPException(401, "密码错误")
    # 停用账号在登录入口即拦截（否则拿到 token 后处处 403，用户卡死）
    if not u["enabled"]:
        d.close()
        raise HTTPException(403, "账号已停用，请联系管理员")
    d.close()
    return {"token": _token(u), "user": _pub(u)}


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "未登录")
    try:
        p = jwt.decode(creds.credentials, SECRET, ALG)
    except jwt.PyJWTError:
        raise HTTPException(401, "token 无效或过期")
    d = db.get_db()
    u = d.execute("SELECT * FROM users WHERE id=?", (p["sub"],)).fetchone()
    if not u:
        raise HTTPException(401, "用户不存在")
    if not u["enabled"]:
        raise HTTPException(403, "账号已停用，请联系管理员")
    return dict(u)


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