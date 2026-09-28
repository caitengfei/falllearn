# -*- coding: utf-8 -*-
import sys, time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    time.sleep(2.5)

    # 1) 点第一张知识卡 → 原地弹详解
    p.locator(".kcard").first.click()
    time.sleep(0.6)
    modal_ok = p.locator(".mask .modal").count() > 0
    modal_text = p.locator(".mask .modal").inner_text() if modal_ok else ""
    print("modal:", modal_ok, "| 含知识点:", "Morse 量表 6 条目" in modal_text, "| 含掌握度:", "掌握度" in modal_text)
    p.screenshot(path=r"E:\lilei\docs\final-home-kcard.png")

    # 2) 点「问 AI 讲这一簇」→ /learn 自动发送
    p.locator(".mask .modal .btn", has_text="问 AI").click()
    time.sleep(3)
    body = p.inner_text("body")
    url = p.evaluate("location.href")
    print("url:", url)
    print("问题气泡出现:", "Morse评估 要点" in body)
    print("思考中指示:", "思考中" in body)
    p.screenshot(path=r"E:\lilei\docs\final-home-kcard-ask.png")
    print("JS errors:", errors[:5])
    b.close()
print("VERIFY DONE")