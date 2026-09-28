# -*- coding: utf-8 -*-
"""前端架构专家 UI 只读抽查：登录 S2026001，逐页截图（只导航+只读请求，不点任何写操作）。"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\feqa"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: print("CONSOLE", m.type, m.text[:200], flush=True) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: print("REQFAIL", r.url, r.failure, flush=True))

    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.screenshot(path=OUT + r"\login.png")
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    p.wait_for_timeout(1500)  # 等 7 个串行 API 渲染完
    p.screenshot(path=OUT + r"\home.png")

    # 顶栏搜索框：输入 + 回车，验证无行为（无 handler）
    before = p.evaluate("location.href")
    p.locator(".searchbox input").fill("Morse 量表")
    p.locator(".searchbox input").press("Enter")
    p.wait_for_timeout(800)
    after = p.evaluate("location.href")
    print("搜索框输入+回车: URL 变化 =", before != after, flush=True)
    p.screenshot(path=OUT + r"\home_search.png")

    for path, name in [("/practice", "practice"), ("/wrong", "wrong"), ("/mine", "mine"), ("/learn", "learn")]:
        p.goto(BASE + path, wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(1200)
        p.screenshot(path=OUT + rf"\{name}.png")

    # 学生直接访问 /admin（前端无路由守卫，后端应 403）
    p.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_timeout(1000)
    p.screenshot(path=OUT + r"\admin_as_student.png")
    err = p.locator(".card.err").count()
    print("学生访问 /admin 是否出现错误卡:", err, flush=True)

    b.close()
print("done")