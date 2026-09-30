# -*- coding: utf-8 -*-
"""邀请码自助注册验收（本地或远程）。

覆盖：教师生成邀请码 → 学生自助注册（自动登录）→ 新账号可用（me/练习）→
无效码/重复码/超长昵称/弱口令/昵称冒充/停用码/用尽码 全部被正确拒绝 → 清理测试数据。

用法：python tools/invite_check.py [BASE]
"""
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
fails = []
created_users = []
created_invites = []


def check(name, ok, extra=""):
    print(("  \u2713 " if ok else "  \u2717 ") + name + (" " + str(extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


def tlogin(sno, pwd):
    r = requests.post(BASE + "/api/auth/login", json={"student_no": sno, "password": pwd}, timeout=15)
    return r.json() if r.status_code == 200 else None


TH = {"authorization": "Bearer " + tlogin("T2026", "123456")["token"]}

print("=== A. 教师生成邀请码 ===", flush=True)
r = requests.post(BASE + "/api/admin/invites", headers=TH,
                  json={"note": "自动化验收", "max_uses": 2, "days": 1}, timeout=15)
check("生成邀请码 200", r.status_code == 200, r.text[:80])
inv = r.json() if r.status_code == 200 else {}
code = inv.get("code", "")
created_invites.append(inv.get("id"))
check("邀请码格式 FD-XXXXXX", code.startswith("FD-") and len(code) == 9, code)
check("返回注册路径", inv.get("path") == f"/register?code={code}", inv.get("path"))

lst = requests.get(BASE + "/api/admin/invites", headers=TH, timeout=15).json()
check("列表含新建邀请码", any(x["code"] == code for x in lst.get("items", [])), len(lst.get("items", [])))
created_invites = [x["id"] for x in lst.get("items", []) if x["code"] == code]

print("=== B. 学生自助注册（免费额度 2 人）===", flush=True)
suffix = str(int(time.time()))[-4:]
name1 = f"验收甲{suffix}"
r = requests.post(BASE + "/api/auth/register",
                  json={"code": code, "name": name1, "password": "test123456"}, timeout=15)
check("首次注册 200", r.status_code == 200, r.text[:80])
d1 = r.json() if r.status_code == 200 else {}
sno1 = d1.get("generated_student_no", "")
check("平台自动分配学号（S+年份+序号）", bool(sno1) and sno1.startswith("S") and sno1[1:].isdigit(), sno1)
check("注册即返回 token（自动登录）", bool(d1.get("token")))
check("角色为学生", (d1.get("user") or {}).get("role") == "student")
created_users.append((sno1, "test123456"))

print("=== C. 新账号可用性 ===", flush=True)
H1 = {"authorization": "Bearer " + d1.get("token", "")}
me = requests.get(BASE + "/api/auth/me", headers=H1, timeout=15)
check("新账号 /me 可用", me.status_code == 200 and me.json().get("student_no") == sno1, me.status_code)
qs = requests.post(BASE + "/api/quiz/start", headers=H1, json={"kind": "daily", "exam_id": 0}, timeout=20)
check("新账号可开卷练习", qs.status_code == 200, qs.status_code)

print("=== D. 异常与安全拦截 ===", flush=True)
cases = [
    ("无效邀请码被拒", {"code": "FD-ZZZZZZ", "name": "x", "password": "test123456"}, 400),
    # 注：本平台统一把 FastAPI 422 校验错误转为 400 + 中文可读提示（main.py validation_handler）
    ("弱口令（<6 位）被拒", {"code": code, "name": "乙" + suffix, "password": "123"}, 400),
    ("昵称含「管理员」被拒", {"code": code, "name": "管理员甲", "password": "test123456"}, 400),
    ("空昵称被拒", {"code": code, "name": "   ", "password": "test123456"}, 400),
    ("超长昵称（>20）被拒", {"code": code, "name": "很" * 25, "password": "test123456"}, 400),
]
for nm, body, want in cases:
    rr = requests.post(BASE + "/api/auth/register", json=body, timeout=15)
    check(nm, rr.status_code == want, rr.status_code)

# 第 2 个名额（刚好用满） → 之后应报「已达上限」
r2 = requests.post(BASE + "/api/auth/register",
                   json={"code": code, "name": f"验收乙{suffix}", "password": "test123456"}, timeout=15)
check("第 2 人注册成功（用满额度）", r2.status_code == 200, r2.status_code)
if r2.status_code == 200:
    created_users.append((r2.json()["generated_student_no"], "test123456"))
r3 = requests.post(BASE + "/api/auth/register",
                   json={"code": code, "name": f"验收丙{suffix}", "password": "test123456"}, timeout=15)
check("超出人数上限被拒", r3.status_code == 400 and "上限" in r3.text, r3.status_code)

print("=== E. 停用邀请码 ===", flush=True)
r = requests.post(BASE + "/api/admin/invites", headers=TH, json={"note": "停用测试", "max_uses": 1, "days": 1}, timeout=15)
code2 = r.json().get("code", "")
lst = requests.get(BASE + "/api/admin/invites", headers=TH, timeout=15).json()
id2 = [x["id"] for x in lst.get("items", []) if x["code"] == code2]
created_invites += id2
up = requests.put(BASE + f"/api/admin/invites/{id2[0]}", headers=TH, json={"enabled": 0}, timeout=15)
check("停用邀请码 200", up.status_code == 200, up.status_code)
r4 = requests.post(BASE + "/api/auth/register", json={"code": code2, "name": "丁", "password": "test123456"}, timeout=15)
check("停用后注册被拒", r4.status_code == 400, r4.status_code)

print("=== F. 越权与鉴权 ===", flush=True)
check("未登录不能生成邀请码", requests.post(BASE + "/api/admin/invites", json={"note": "", "max_uses": 1, "days": 1},
                                      timeout=15).status_code == 401)
check("学生不能生成邀请码", requests.post(BASE + "/api/admin/invites", headers=H1,
                                     json={"note": "", "max_uses": 1, "days": 1}, timeout=15).status_code == 403)
check("学生不能查邀请码列表", requests.get(BASE + "/api/admin/invites", headers=H1, timeout=15).status_code == 403)

print("=== G. 清理测试数据 ===", flush=True)
accts = requests.get(BASE + "/api/admin/accounts", headers=TH, timeout=15).json().get("items", [])
for sno, _ in created_users:
    hit = [a for a in accts if a["student_no"] == sno]
    if hit:
        dr = requests.delete(BASE + f"/api/admin/accounts/{hit[0]['id']}", headers=TH, timeout=15)
        print(f"  删除 {sno}: {dr.status_code}")
for iid in created_invites:
    if iid:
        requests.delete(BASE + f"/api/admin/invites/{iid}", headers=TH, timeout=15)
print("  邀请码与测试学生已清理")

print(f"\n===== 邀请码注册验收: 失败 {len(fails)} 项 → {BASE} =====")
print("FAILS:", fails if fails else "无")
sys.exit(1 if fails else 0)
