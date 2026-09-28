# -*- coding: utf-8 -*-
"""移动视口逐页测量横向溢出(只读)"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    m = b.new_context(viewport={"width": 390, "height": 844})
    p = m.new_page()
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)

    def measure():
        return p.evaluate("""(() => {
            const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
            const bad = [];
            if (sw > cw) {
                document.querySelectorAll('*').forEach((el) => {
                    const r = el.getBoundingClientRect();
                    if (r.width > cw + 1 || r.right > cw + 1) {
                        const cls = (el.className && typeof el.className === 'string') ? el.className.slice(0, 40) : el.tagName;
                        bad.push(el.tagName + '.' + cls + ' w=' + Math.round(r.width) + ' right=' + Math.round(r.right));
                    }
                });
            }
            return { sw, cw, bad: bad.slice(0, 12) };
        })()""")

    for url in ["/login", "/", "/learn", "/practice", "/wrong", "/mine"]:
        if url == "/login":
            # 已在登录页之前; 直接量登录页
            pass
        p.goto(BASE + url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.2)
        r = measure()
        print(url, "sw=", r["sw"], "cw=", r["cw"], "overflow=" + str(r["sw"] > r["cw"]))
        for x in r["bad"]:
            print("   ", x)
    b.close()
    print("DONE")