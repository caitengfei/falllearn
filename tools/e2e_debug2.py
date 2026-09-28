# -*- coding: utf-8 -*-
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.goto("http://127.0.0.1:8010/", wait_until="networkidle", timeout=30000)
    time.sleep(3)
    print("t0 url:", p.url)
    print("history.state:", p.evaluate("JSON.stringify(history.state)"))
    # 点导航「首页」
    p.locator(".navtabs a", has_text="首页").click()
    time.sleep(1.5)
    print("after click 首页:", p.url)
    # 直接跳 /practice
    p.goto("http://127.0.0.1:8010/practice", wait_until="networkidle")
    time.sleep(2.5)
    print("after goto /practice:", p.url)
    print("body head:", p.inner_text("body")[:120].replace("\n", " | "))
    b.close()