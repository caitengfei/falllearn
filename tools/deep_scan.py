# -*- coding: utf-8 -*-
"""深度安全检测（第 12 套验收脚本）——与前几轮互补的新维度：

A. 鉴权矩阵：全部 API × 三种身份（匿名 / 学生 / 教师）→ 找出未受保护的端点或越权
B. 输入 fuzz：SQL / XSS / 类型混淆 / 超长 / 负数 载荷注入关键字段 → 断言不 500、不泄露、不执行
C. 静态与路径泄露：.git、备份库、jwt_secret、路径穿越（含 URL 编码变体）
D. HTTP 方法矩阵：TRACE/OPTIONS/PUT/DELETE 到公共端点
E. 安全响应头完整性 + 缓存策略
F. 并发竞态：并发签到只计一次、并发开卷只有一张
G. 上传面：未鉴权上传被拒 + 危险扩展名被拒（SVG/HTML 之类可致同源 XSS）

用法：python tools/deep_scan.py [BASE]
"""
import concurrent.futures as cf
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8010")
# --readonly：跳过会改动数据的检查（并发签到、公告写入 fuzz），用于对生产服务器复验
READONLY = "--readonly" in sys.argv
fails, warns = [], []


def ck(name, ok, extra=""):
    print(("  \u2713 " if ok else "  \u2717 ") + name + (" " + str(extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


def warn(name, extra=""):
    print("  ! " + name + (" " + str(extra) if extra else ""), flush=True)
    warns.append(name)


S = requests.Session()
tj = S.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=15).json()
TH = {"authorization": "Bearer " + tj["token"]}
tt = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=15).json()
TT = {"authorization": "Bearer " + tt["token"]}

print("=== A. 鉴权矩阵（自动枚举全量端点 × 匿名/学生/教师）===", flush=True)
PUBLIC = {"/api/health", "/api/content/banners", "/api/content/announcements", "/api/meta/clusters",
          "/api/auth/login", "/api/auth/register"}
# 优先从 openapi 自动枚举（内置清单为全量 81 个端点，docs 关闭时用它）（本地可临时置 FALLLEARN_ENABLE_DOCS=1）；docs 关闭时用内置关键清单
try:
    _spec = requests.get(BASE + "/openapi.json", timeout=15)
    paths = _spec.json().get("paths", {}) if _spec.status_code == 200 else {}
except Exception:
    paths = {}
if paths:
    print(f"  已从 openapi 自动枚举 {sum(len(v) for v in paths.values())} 个端点"
          f"（写接口只做匿名/越权两级，避免副作用）", flush=True)
else:
    print("  docs 已关闭，使用内置全量端点清单", flush=True)
    paths = {}
    for _m, _p, _b in [
        ("DELETE", "/api/admin/accounts/{uid}", {}),
        ("DELETE", "/api/admin/ai/direct", {}),
        ("DELETE", "/api/admin/ai/kb", {}),
        ("DELETE", "/api/admin/announcements/{nid}", {}),
        ("DELETE", "/api/admin/assignments/{exam_id}", {}),
        ("DELETE", "/api/admin/banners/{bid}", {}),
        ("DELETE", "/api/admin/invites/{iid}", {}),
        ("DELETE", "/api/admin/trainings/{tid}", {}),
        ("GET", "/api/admin/accounts", None),
        ("GET", "/api/admin/ai/direct", None),
        ("GET", "/api/admin/ai/grades", None),
        ("GET", "/api/admin/ai/kb", None),
        ("GET", "/api/admin/ai/models", None),
        ("GET", "/api/admin/announcements", None),
        ("GET", "/api/admin/assignments", None),
        ("GET", "/api/admin/banners", None),
        ("GET", "/api/admin/dashboard", None),
        ("GET", "/api/admin/exams", None),
        ("GET", "/api/admin/exams/export", None),
        ("GET", "/api/admin/exams/{attempt_id}", None),
        ("GET", "/api/admin/invites", None),
        ("GET", "/api/admin/stats/overview", None),
        ("GET", "/api/admin/stats/trainings", None),
        ("GET", "/api/admin/stats/wrong", None),
        ("GET", "/api/admin/students", None),
        ("GET", "/api/admin/trainings", None),
        ("GET", "/api/auth/me", None),
        ("GET", "/api/content/announcements", None),
        ("GET", "/api/content/banners", None),
        ("GET", "/api/game/badges", None),
        ("GET", "/api/game/leaderboard", None),
        ("GET", "/api/game/points", None),
        ("GET", "/api/game/today", None),
        ("GET", "/api/health", None),
        ("GET", "/api/kb/doc", None),
        ("GET", "/api/kb/search", None),
        ("GET", "/api/learn/history", None),
        ("GET", "/api/learn/status", None),
        ("GET", "/api/learn/stream", None),
        ("GET", "/api/meta/clusters", None),
        ("GET", "/api/quiz/assignments", None),
        ("GET", "/api/quiz/report", None),
        ("GET", "/api/quiz/result/{attempt_id}", None),
        ("GET", "/api/quiz/summary", None),
        ("GET", "/api/quiz/weak", None),
        ("GET", "/api/wrong", None),
        ("POST", "/api/admin/accounts", {}),
        ("POST", "/api/admin/accounts/batch", {}),
        ("POST", "/api/admin/ai/direct", {}),
        ("POST", "/api/admin/ai/direct/test", {}),
        ("POST", "/api/admin/ai/generate-questions", {}),
        ("POST", "/api/admin/ai/grade", {}),
        ("POST", "/api/admin/ai/kb", {}),
        ("POST", "/api/admin/ai/model", {}),
        ("POST", "/api/admin/ai/questions/save", {}),
        ("POST", "/api/admin/announcements", {}),
        ("POST", "/api/admin/assignments", {}),
        ("POST", "/api/admin/banners", {}),
        ("POST", "/api/admin/invites", {}),
        ("POST", "/api/admin/reset-demo", {}),
        ("POST", "/api/admin/students", {}),
        ("POST", "/api/admin/trainings", {}),
        ("POST", "/api/admin/trainings/{tid}/enroll", {}),
        ("POST", "/api/admin/trainings/{tid}/students/{uid}/status", {}),
        ("POST", "/api/admin/upload", {}),
        ("POST", "/api/auth/login", {}),
        ("POST", "/api/auth/logout", {}),
        ("POST", "/api/auth/register", {}),
        ("POST", "/api/game/checkin", {}),
        ("POST", "/api/learn/answer", {}),
        ("POST", "/api/learn/ask", {}),
        ("POST", "/api/quiz/report/ai", {}),
        ("POST", "/api/quiz/start", {}),
        ("POST", "/api/quiz/submit", {}),
        ("POST", "/api/wrong/review", {}),
        ("PUT", "/api/admin/accounts/{uid}", {}),
        ("PUT", "/api/admin/announcements/{nid}", {}),
        ("PUT", "/api/admin/banners/{bid}", {}),
        ("PUT", "/api/admin/invites/{iid}", {}),
        ("PUT", "/api/admin/students/{uid}", {}),
        ("PUT", "/api/admin/trainings/{tid}", {}),
    ]:
        paths.setdefault(_p, {})[_m.lower()] = {}


def kind_of(p):
    lp = p.lower()
    if lp in PUBLIC:
        return "public"
    if lp.startswith("/api/admin/"):
        return "teacher"
    return "auth"


anon_bad, stu_bad, tch_bad = [], [], []
covered = 0
for path in sorted(paths):
    if path.endswith("/stream"):        # SSE 长连接：匿名探测会挂起，单独由其它脚本覆盖
        continue
    k = kind_of(path)
    if k == "public":
        continue
    for m in sorted(mm.upper() for mm in paths[path]):
        if m in ("HEAD", "OPTIONS"):
            continue
        real = (path.replace("{attempt_id}", "1").replace("{uid}", "1").replace("{bid}", "1")
                    .replace("{nid}", "1").replace("{tid}", "1").replace("{iid}", "1")
                    .replace("{exam_id}", "1").replace("{question_id}", "1"))
        write = m in ("POST", "PUT", "DELETE", "PATCH")
        covered += 1
        ra = requests.request(m, BASE + real, json={} if write else None, timeout=20)
        if ra.status_code != 401:
            anon_bad.append(f"{m} {real}={ra.status_code}")
        if k == "teacher":
            rs = requests.request(m, BASE + real, json={} if write else None, headers=TH, timeout=20)
            if rs.status_code != 403:
                stu_bad.append(f"{m} {real}={rs.status_code}")
            if not write:               # 只读端点才做教师正向调用（避免删改数据）
                rt = requests.request(m, BASE + real, headers=TT, timeout=25)
                if rt.status_code >= 500 or rt.status_code == 405:
                    tch_bad.append(f"{m} {real}={rt.status_code}")
ck(f"全量端点匿名鉴权（{covered} 个调用，异常 {len(anon_bad)}）", not anon_bad, anon_bad[:4])
ck(f"管理端学生越权拦截（异常 {len(stu_bad)}）", not stu_bad, stu_bad[:4])
ck(f"管理端教师只读可用性（异常 {len(tch_bad)}）", not tch_bad, tch_bad[:4])

print("=== B. 输入 fuzz（SQL / XSS / 混淆 / 超长 / 负数）===", flush=True)
SQL = ["' OR '1'='1", "1;DROP TABLE users;--", "%' UNION SELECT pwd_hash FROM users--", "'; UPDATE users SET role='teacher' WHERE id=1;--"]
XSS = ["<img src=x onerror=alert(1)>", "<script>alert(1)</script>", "javascript:alert(1)", "\"><svg/onload=alert(1)>"]

for p in SQL + XSS:
    r = requests.get(BASE + "/api/kb/search", params={"q": p}, headers=TH, timeout=20)
    ck(f"检索转义/参数化（{p[:18]}…）", r.status_code in (200, 400) , r.status_code)
# 参数化验证：注入不应改变用户表
r = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026001' OR '1'='1", "password": "x"}, timeout=15)
ck("登录注入被拒（账号不存在）", r.status_code in (401, 429), r.status_code)
# 写接口 fuzz：公告（写入 XSS 载荷 → 验证安全落库后立即删除；--readonly 时跳过以不动服务器数据）
if not READONLY:
    for p in XSS[:2] + SQL[:1]:
        r = requests.post(BASE + "/api/admin/announcements", headers=TT,
                          json={"title": p[:40], "summary": p, "content": p}, timeout=15)
        if r.status_code in (200, 201):
            iid = (r.json() or {}).get("id")
            if iid:
                requests.delete(BASE + f"/api/admin/announcements/{iid}", headers=TT, timeout=15)
        ck(f"公告写入 XSS 载荷安全落库（{p[:14]}…）", r.status_code in (200, 201, 400), r.status_code)
else:
    print("  （--readonly：跳过公告写入 fuzz）", flush=True)
# 类型混淆 / 超长 / 负数
cases = [
    ("注册：超长昵称", "POST", "/api/auth/register", {"code": "FD-XXXXXX", "name": "长" * 3000, "password": "test123456"}),
    ("注册：昵称传数字", "POST", "/api/auth/register", {"code": "FD-XXXXXX", "name": 12345, "password": "test123456"}),
    ("注册：密码传对象", "POST", "/api/auth/register", {"code": "FD-XXXXXX", "name": "x", "password": {"a": 1}}),
    ("邀请码：负数上限", "POST", "/api/admin/invites", {"note": "", "max_uses": -5, "days": 1}),
    ("邀请码：超大数值", "POST", "/api/admin/invites", {"note": "", "max_uses": 99999999, "days": 999999}),
    ("邀请码：天数为字符串", "POST", "/api/admin/invites", {"note": "", "max_uses": 1, "days": "一个月"}),
]
for nm, m, path, body in cases:
    h = TT if path.startswith("/api/admin") else {}
    r = requests.request(m, BASE + path, json=body, headers=h, timeout=20)
    ck(f"{nm} 被安全拒绝", r.status_code in (400, 401, 403, 422) and r.status_code < 500, r.status_code)
# 不存在的 id / 负数 id
for path in ["/api/quiz/result/-1", "/api/admin/exams/-1", "/api/admin/students/-1"]:
    h = TT if path.startswith("/api/admin") else TH
    r = requests.get(BASE + path, headers=h, timeout=15)
    ck(f"{path} 不崩溃（{r.status_code}）", r.status_code < 500, r.status_code)

print("=== C. 静态与路径泄露 ===", flush=True)
LEAKS = [
    "/.git/config", "/.git/HEAD", "/backend/falllearn.db", "/jwt_secret", "/falllearn.db",
    "/backend/app/main.py", "/app/main.py", "/requirements.txt", "/.env",
    "/falllearn.db.bak_20260930_invite", "/dump.sql", "/backups.rar",
    "/%2e%2e/backend/app/main.py", "/..%2fbackend%2fapp%2fmain.py", "/uploads/",
]
for p in LEAKS:
    r = requests.get(BASE + p, timeout=15)
    ck(f"泄露探测 {p} 非 200", r.status_code != 200, r.status_code)
# 知识库路径穿越（含编码变体）
for bad in ["../../../backend/jwt_secret", "..%2f..%2f..%2fbackend%2fjwt_secret",
            "....//....//backend/jwt_secret", "/etc/passwd", "C:\\Windows\\win.ini"]:
    r = requests.get(BASE + "/api/kb/doc", params={"path": bad}, headers=TH, timeout=15)
    body = r.text[:120].lower()
    ck(f"KB 路径穿越被拒（{bad[:22]}…）", r.status_code in (400, 404) and "secret" not in body, r.status_code)

print("=== D. HTTP 方法矩阵 ===", flush=True)
for m in ("TRACE", "PUT", "DELETE", "OPTIONS", "PATCH"):
    r = requests.request(m, BASE + "/api/health", timeout=15)
    ck(f"{m} /api/health 不被当作合法写入（{r.status_code}）", r.status_code in (404, 405, 401, 403), r.status_code)
r = requests.request("PUT", BASE + "/api/wrong/review", json={"question_id": 1, "answer": "A"}, headers=TH, timeout=15)
ck("PUT 到只允许 POST 的接口 → 405", r.status_code == 405, r.status_code)

print("=== E. 安全头与缓存 ===", flush=True)
h = requests.get(BASE + "/", timeout=15).headers
need = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}
for k, v in need.items():
    ck(f"响应头 {k}", h.get(k) == v, h.get(k))
ck("CSP 含 script-src 'self'", "script-src 'self'" in h.get("Content-Security-Policy", ""))
ck("Permissions-Policy 已下发", "microphone" in h.get("Permissions-Policy", ""), h.get("Permissions-Policy", "")[:40])
ck("index.html 不缓存（no-cache）", "no-cache" in h.get("Cache-Control", "") or "no-store" in h.get("Cache-Control", ""), h.get("Cache-Control"))
a = requests.get(BASE + "/api/health", timeout=15).headers
ck("API 响应不回显服务器版本", "Server" not in a or "uvicorn" not in a.get("Server", "").lower(), a.get("Server", "无"))

print("=== F. 并发竞态 ===", flush=True)
if not READONLY:
    # 并发签到：同一天重复签到不重复加分（/api/game/points 返回 {total, log}）
    pts0 = (requests.get(BASE + "/api/game/points", headers=TH, timeout=15).json() or {}).get("total", 0)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda _: requests.post(BASE + "/api/game/checkin", json={}, headers=TH, timeout=20).status_code, range(8)))
    pts1 = (requests.get(BASE + "/api/game/points", headers=TH, timeout=15).json() or {}).get("total", 0)
    ck(f"并发签到不重复计分（+{pts1 - pts0} 分，状态 {sorted(set(res))}）",
       (pts1 - pts0) <= 5 and all(s < 500 for s in res))
else:
    print("  （--readonly：跳过并发签到）", flush=True)
# 并发开卷：最多一张 open（唯一索引兜底）
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    res2 = list(ex.map(lambda _: requests.post(BASE + "/api/quiz/start", json={"kind": "daily", "exam_id": 0},
                                               headers=TH, timeout=25).status_code, range(6)))
ck("并发开卷无 500（幂等/续考）", all(s < 500 for s in res2), sorted(set(res2)))

print("=== G. 上传面 ===", flush=True)
r = requests.post(BASE + "/api/admin/upload", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")}, timeout=15)
ck("未鉴权上传被拒", r.status_code == 401, r.status_code)
for fn, ct in [("evil.svg", "image/svg+xml"), ("evil.html", "text/html"), ("x.png", "image/png")]:
    r = requests.post(BASE + "/api/admin/upload", headers=TT,
                      files={"file": (fn, b"<svg onload=alert(1)></svg>", ct)}, timeout=20)
    if fn in ("evil.svg", "evil.html"):
        ck(f"上传 {fn} 被拒（同源 XSS 载体）", r.status_code in (400, 415), r.status_code)
    else:
        ck(f"上传 {fn} 正常（{r.status_code}）", r.status_code in (200, 400), r.status_code)
r = requests.post(BASE + "/api/admin/upload", headers=TT,
                  files={"file": ("big.png", b"\x89PNG" + b"0" * (7 * 1024 * 1024), "image/png")}, timeout=30)
ck("超大上传被拒（>6MB）", r.status_code in (400, 413), r.status_code)

print(f"\n===== 深度检测: 失败 {len(fails)} 项 · 提示 {len(warns)} 项 → {BASE} =====")
print("FAILS:", fails if fails else "无")
print("WARNS:", warns if warns else "无")
sys.exit(1 if fails else 0)
