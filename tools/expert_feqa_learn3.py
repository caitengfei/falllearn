# -*- coding: utf-8 -*-
"""验证 /learn 崩溃触发条件：S2026003（无历史）应正常渲染。只读导航。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errs = []
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.goto("http://127.0.0.1:8010/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026003")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    p.goto("http://127.0.0.1:8010/learn", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_timeout(1500)
    has_chat = p.locator(".chat-flow").count()
    p.screenshot(path=r"E:\lilei\docs\expert-test\feqa\learn_s2026003.png")
    print("S2026003 /learn chat-flow 存在:", has_chat, " 控制台错误:", errs)
    b.close()