# -*- coding: utf-8 -*-
"""远程只读验收（不写服务器库）：页面渲染 / 关键数据 / 安全头 / 移动端溢出 / JS 异常。

区别于 remote_suite.py：本脚本**不做任何写操作**（不布置、不交卷、不重置演示数据），
因此可在部署后直接跑，无需按 v3 恢复协议复原数据库。

用法：
    python tools/remote_readonly_check.py [http://IP:8010]
"""
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://121.199.161.117:8010"
fails = []


def check(name, ok, extra=""):
    print(("  \u2713 " if ok else "  \u2717 ") + name + (" " + str(extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


print("=== A. 接口只读探针 ===", flush=True)
r = requests.get(BASE + "/api/health", timeout=15)
check("健康检查", r.status_code == 200 and r.json().get("ok") is True, r.text[:60])
h = requests.get(BASE + "/", timeout=15).headers
check("CSP 安全头", "script-src 'self'" in h.get("Content-Security-Policy", ""), "")
check("Permissions-Policy", "microphone" in h.get("Permissions-Policy", ""), "")
for path in ("/openapi.json", "/docs", "/dump.sql.lz"):
    rr = requests.get(BASE + path, timeout=15)
    check(f"{path} 返回 404", rr.status_code == 404, rr.status_code)

tj = requests.post(BASE + "/api/auth/login",
                   json={"student_no": "T2026", "password": "123456"}, timeout=15).json()
TH = {"authorization": "Bearer " + tj["token"]}
sj = requests.post(BASE + "/api/auth/login",
                   json={"student_no": "S2026001", "password": "123456"}, timeout=15).json()
SH = {"authorization": "Bearer " + sj["token"]}
me = requests.get(BASE + "/api/auth/me", headers=SH, timeout=15).json()
# 断言口径（2026-09-30 修正）：真实班级试用后数据会增长，故只校验「不低于演示基线 / 结构正确」，
# 不锁死具体数值（原写法 =219 / =2 / =6 在试用开始后必然误报）
check("学生档案可访问（积分 ≥ 演示基线 219）", (me.get("points") or 0) >= 219, me.get("points"))
check("完成练习数 ≥ 2", (me.get("practice_count") or 0) >= 2, me.get("practice_count"))
wl = requests.get(BASE + "/api/wrong?status=active", headers=SH, timeout=15).json()
check("错题本接口可用（返回列表）", isinstance(wl.get("items"), list), len(wl.get("items", [])))
kb = requests.get(BASE + "/api/kb/search", params={"q": ""}, headers=SH, timeout=20).json()
check("知识库 46 份", kb.get("total") == 46, kb.get("total"))
acc = requests.get(BASE + "/api/admin/accounts", headers=TH, timeout=15).json()
check("账号 4 个（3 生 1 师）", len(acc.get("items", [])) == 4, len(acc.get("items", [])))

print("=== B. 浏览器只读走查（不点写操作按钮） ===", flush=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))

    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    check("登录页一键体验 4 账号", p.locator(".dh-btn").count() == 4, p.locator(".dh-btn").count())
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    try:
        p.wait_for_url(lambda u: "/login" not in u, timeout=25000)
        check("学生登录跳转", True)
    except Exception:
        check("学生登录跳转", False, p.url)
    time.sleep(2)

    for path, needle in (("/", "学习日历"), ("/learn", "AI 老师"), ("/map", "知识地图"), ("/kb", "知识库"),
                         ("/practice", "练习"), ("/wrong", "错题本"),
                         ("/report", "学习报告"), ("/competition", "岗课赛证"),
                         ("/mine", "掌握度")):
        p.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
        time.sleep(2.2)
        txt = p.inner_text("body")
        check(f"{path} 渲染「{needle}」", needle in txt, "")
        ov = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(f"{path} 桌面无横向溢出", ov <= 0, f"overflow={ov}")

    # 错题本：6 题 + 打印按钮 + 正确答案
    p.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2.2)
    check("错题本打印按钮", p.locator("button:has-text('打印')").count() >= 1)
    check("错题本显示正确答案", p.locator("text=正确答案").count() >= 1)

    # 学习中心：朗读/复制操作条（演示库可能已清空问答历史 → 无历史答案时改检查输入区可用，本脚本保持只读不写库）
    p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2.5)
    n_ops = p.locator(".msg-ops .op").count()
    has_input = p.locator("textarea, input[type=text], .ask-in, .chip-ask").count() >= 1
    check("AI 答案操作条（朗读/复制）或提问区可用", n_ops >= 2 or has_input,
          f"操作条 {n_ops} 个 / 输入区 {'有' if has_input else '无'}")

    # 教师端只读页面
    p2 = b.new_page(viewport={"width": 1440, "height": 950})
    errs2 = []
    p2.on("pageerror", lambda e: errs2.append(str(e)))
    p2.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    p2.locator(".field input").nth(0).fill("T2026")
    p2.locator(".field input").nth(1).fill("123456")
    p2.locator(".login-body .btn").click()
    time.sleep(3)
    for path, needle in (("/admin", "数据总览"), ("/admin/content", "业务管理"), ("/admin/exams", "考试管理"),
                         ("/admin/students", "学生管理"), ("/admin/accounts", "账号管理"),
                         ("/admin/trainings", "培训管理"), ("/admin/stats", "培训情况统计"),
                         ("/admin/ai", "AI 管理")):
        p2.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
        time.sleep(2.2)
        check(f"{path} 渲染「{needle}」", needle in p2.inner_text("body"), "")

    # 移动端 390
    pm = b.new_page(viewport={"width": 390, "height": 844})
    for path in ("/", "/learn", "/wrong", "/kb"):
        pm.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
        time.sleep(2.2)
        ov = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(f"移动 390 {path} 无横向溢出", ov <= 0, f"overflow={ov}")

    check("全程无 JS 异常", not errs and not errs2, str((errs + errs2)[:2]))
    b.close()

print(f"\n===== 远程只读验收: 失败 {len(fails)} 项 → {BASE} =====")
print("FAILS:", fails if fails else "无")
sys.exit(1 if fails else 0)
