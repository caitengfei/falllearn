# -*- coding: utf-8 -*-
"""交付截图：S2026001（种子基线）桌面 1440 + 移动 390，无 DSH 提问。"""
import sys, time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
D = r"E:\lilei\docs\final"


def cur_url(p):
    try:
        return p.evaluate("location.href")
    except Exception:
        return p.url


with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)

    # ---------- 桌面 ----------
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(0.8)
    p.screenshot(path=D + "-login.png")
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    time.sleep(2.5)
    p.screenshot(path=D + "-home.png", full_page=True)
    for name, path in [("learn", "/learn"), ("competition", "/competition"),
                       ("practice", "/practice"), ("wrong", "/wrong"), ("mine", "/mine")]:
        p.goto(BASE + path, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2.2)
        p.screenshot(path=f"{D}-{name}.png", full_page=True)
    p.close()

    # ---------- 移动 390 ----------
    m = b.new_page(viewport={"width": 390, "height": 844})
    m.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(0.8)
    m.screenshot(path=D + "-m-login.png")
    m.locator(".field input").nth(0).fill("S2026001")
    m.locator(".field input").nth(1).fill("123456")
    m.locator(".login-body .btn").click()
    time.sleep(2.5)
    m.screenshot(path=D + "-m-home.png")
    m.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.2)
    m.screenshot(path=D + "-m-learn.png")
    m.close()
    b.close()
print("SCREENSHOTS DONE")