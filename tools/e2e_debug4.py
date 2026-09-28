# -*- coding: utf-8 -*-
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errs = []
    p.on("pageerror", lambda e: errs.append(f"PAGEERR: {e}"))
    p.on("console", lambda m: errs.append(f"CON[{m.type}]: {m.text}") if m.type == "error" else None)
    p.goto("http://127.0.0.1:8010/login", wait_until="domcontentloaded")
    p.wait_for_selector(".login-card", timeout=15000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    print("home OK:", p.url)
    p.locator(".navtabs a", has_text="学习中心").click()
    time.sleep(3)
    print("after click:", p.url)
    print("has chat-input:", p.locator(".chat-input").count())
    print("has textarea:", p.locator("textarea").count())
    print("body head:", p.inner_text("body")[:150].replace("\n", " | "))
    for e in errs[:10]:
        print(e)
    b.close()