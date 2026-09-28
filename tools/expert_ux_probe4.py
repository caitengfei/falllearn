# -*- coding: utf-8 -*-
"""探针4：完全复刻首测 home.png 的时机（login 后 wait .stu-card +800ms 截图）"""
import sys, os, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("dialog", lambda d: d.dismiss())
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    if p.locator(".login-card").count() == 0:
        print("note: no login card at count() time", flush=True)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card, .navtabs", timeout=20000)
    p.wait_for_timeout(800)
    s = p.evaluate("""() => ({
        url: location.pathname,
        uname: (document.querySelector('.uname')||{}).textContent || '',
        udept: (document.querySelector('.udept')||{}).textContent || '',
        avatar: (document.querySelector('.userchip .avatar')||{}).textContent || ''
    })""")
    print("state at home.png moment:", s, flush=True)
    p.screenshot(path=os.path.join(OUT, "home_probe4.png"))
    b.close()
print("DONE probe4", flush=True)