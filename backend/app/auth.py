# -*- coding: utf-8 -*-
"""登录鉴权：bcrypt + JWT（30 天），student/teacher 角色；含邀请码自助注册。"""
import os
import secrets as _secrets
import sqlite3
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


def _audit(d, sno, user_id, ip, ua, ok):
    """登录审计（安全专家意见）：记录成功/失败的登录尝试，便于公网演示账号场景下的安全追溯。
    审计写入失败不阻断登录主流程。"""
    try:
        d.execute("INSERT INTO login_audit(user_id,sno,ip,ua,ok,at) VALUES(?,?,?,?,?,?)",
                  (user_id, (sno or "")[:64], ip, ua, ok, int(time.time())))
        d.commit()
    except Exception:
        pass


@router.post("/login")
def login(body: LoginIn, request: Request):
    ip = request.client.host if request.client else "?"
    ua = (request.headers.get("user-agent") or "")[:160]
    now = int(time.time())
    locked_until = _LOCKED.get(ip, 0)
    if locked_until > now:
        raise HTTPException(429, f"登录失败次数过多，请 {max(1, (locked_until - now) // 60)} 分钟后再试")
    d = db.get_db()
    u = d.execute("SELECT * FROM users WHERE student_no=?", (body.student_no.strip(),)).fetchone()
    if not u:
        _audit(d, body.student_no, None, ip, ua, 0)
        d.close()
        _login_fail(ip, now)
        raise HTTPException(401, "账号不存在（学号/工号）")
    if not bcrypt.checkpw(body.password.encode(), u["pwd_hash"].encode()):
        _audit(d, body.student_no, u["id"], ip, ua, 0)
        d.close()
        _login_fail(ip, now)
        raise HTTPException(401, "密码错误")
    # 停用账号在登录入口即拦截（否则拿到 token 后处处 403，用户卡死；不计入失败计数）
    if not u["enabled"]:
        _audit(d, body.student_no, u["id"], ip, ua, 0)
        d.close()
        raise HTTPException(403, "账号已停用，请联系管理员")
    _audit(d, u["student_no"], u["id"], ip, ua, 1)
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


# ---------- 邀请码自助注册（学生批量加入 · 最小化隐私采集） ----------
# 限流口径（重要）：**成功注册不计数、成功即清零**，只限制「失败尝试」。
# 原因：学校机房/教室几十名学生常共用同一出口 IP，若按尝试次数限流会误伤整班注册；
# 邀请码本身已有人数上限，爆破风险由「失败次数上限」覆盖。
REG_FAIL_MAX = 20      # 同 IP 10 分钟内失败尝试上限（防脚本猜邀请码）
REG_WINDOW = 600
_REG_FAIL: dict = {}
# 昵称禁用词：防止用「管理员 / 老师」等字样冒充身份（不做实名要求，鼓励使用昵称）
_RESERVED_NAMES = ("管理员", "老师", "教师", "admin", "teacher", "系统", "官方")


class RegisterIn(BaseModel):
    code: str = Field(min_length=4, max_length=32)
    name: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=6, max_length=128)


def _reg_fail_allow(ip: str, now: int) -> bool:
    """失败尝试限流：记录一次尝试；连续失败达上限则拒绝（10 分钟窗口）。"""
    hist = [t for t in _REG_FAIL.get(ip, []) if now - t < REG_WINDOW]
    if len(hist) >= REG_FAIL_MAX:
        _REG_FAIL[ip] = hist
        return False
    hist.append(now)
    _REG_FAIL[ip] = hist
    if len(_REG_FAIL) > 2000:  # 内存有界（防伪造源 IP 撑爆进程内存）
        for k in [k for k, ts in _REG_FAIL.items() if not ts or now - ts[-1] > REG_WINDOW]:
            _REG_FAIL.pop(k, None)
    return True


def _gen_student_no(d) -> str:
    """生成平台内学号（S + 年份 + 3 位序号，如 S2026004）。

    隐私设计：不要求学生填真实学号——平台内编号与学校学籍号解耦，教师通过线下名单对应即可。
    """
    prefix = "S" + time.strftime("%Y")
    mx = 0
    for r in d.execute("SELECT student_no FROM users WHERE student_no LIKE ?", (prefix + "%",)):
        s = str(r["student_no"])[len(prefix):]
        if s.isdigit():
            mx = max(mx, int(s))
    return f"{prefix}{mx + 1:03d}"


@router.post("/register")
def register(body: RegisterIn, request: Request):
    """用邀请码自助注册（学生）：只需昵称 + 自设密码，注册成功即自动登录。

    隐私：不采集手机号、邮箱、身份证、真实姓名；密码 bcrypt 哈希存储；数据仅存服务器本地。
    """
    ip = request.client.host if request.client else "?"
    now = int(time.time())
    if not _reg_fail_allow(ip, now):
        raise HTTPException(429, "注册尝试过于频繁，请稍后再试")
    code = body.code.strip().upper().replace(" ", "")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "请填写昵称")
    low = name.lower()
    if any(w in low for w in _RESERVED_NAMES):
        raise HTTPException(400, "昵称不能包含「管理员 / 老师」等字样")
    d = db.get_db()
    try:
        inv = d.execute("SELECT * FROM invite_codes WHERE code=?", (code,)).fetchone()
        if not inv or not inv["enabled"]:
            raise HTTPException(400, "邀请码无效，请向老师确认")
        if int(inv["expires_at"]) < now:
            raise HTTPException(400, "邀请码已过期，请向老师索取新的邀请码")
        if int(inv["used_count"]) >= int(inv["max_uses"]):
            raise HTTPException(400, "邀请码使用人数已达上限，请向老师索取新的邀请码")
        h = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(10)).decode()
        # 并发闸门①：条件更新占名额——多人同时注册时只有前 max_uses 个能成功（避免名额超发）
        cur = d.execute("UPDATE invite_codes SET used_count=used_count+1 "
                        "WHERE id=? AND used_count < max_uses", (inv["id"],))
        if cur.rowcount == 0:
            d.rollback()
            raise HTTPException(400, "邀请码使用人数已达上限，请向老师索取新的邀请码")
        # 并发闸门②：学号由「当前最大序号 +1」生成，两个并发请求可能算出同一号 → 唯一约束冲突自动换号重试
        sno = ""
        for _ in range(4):
            sno = _gen_student_no(d)
            try:
                d.execute("INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at) VALUES(?,?,?,?,1,?)",
                          (sno, name, "student", h, now))
                break
            except sqlite3.IntegrityError:
                sno = ""
        if not sno:
            d.rollback()
            raise HTTPException(503, "当前注册人数较多，请稍后重试")
        uid = d.execute("SELECT id FROM users WHERE student_no=?", (sno,)).fetchone()["id"]
        d.commit()
        u = d.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    except HTTPException:
        d.close()
        raise
    d.close()
    _REG_FAIL.pop(ip, None)  # 注册成功即清零失败计数（共享出口 IP 下允许整班连续注册）
    return {"token": _token(u), "user": _pub(u), "generated_student_no": sno}