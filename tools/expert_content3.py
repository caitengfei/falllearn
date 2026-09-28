# -*- coding: utf-8 -*-
"""第三轮：S2026003 完成首次提问后再次进入 /learn —— 验证白屏崩溃复现。只读。"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errs = []
    p.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026003")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=20000)
    p.goto(BASE + "/learn", wait_until="domcontentloaded")
    time.sleep(4)
    chat = p.evaluate("!!document.querySelector('.chat-flow')")
    cards = p.evaluate("document.querySelectorAll('.page .card').length")
    body = p.evaluate("document.querySelector('.page') ? document.querySelector('.page').innerText.trim().slice(0,120) : '(page 无内容)'")
    print("S3 再次进入 /learn: chat-flow可见=", chat, " page内card数=", cards)
    print("page内容:", repr(body))
    print("console errors:", errs)
    p.screenshot(path=r"E:\lilei\docs\expert-test\content\learn_s3_revisit_crash.png")
    b.close()
print("DONE3")