# -*- coding: utf-8 -*-
"""探针2：复刻首测登录序列，观察顶栏是否在 10s 内自行更新（不刷新）"""
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
        print("no login card yet", flush=True)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card, .navtabs", timeout=20000)
    print("wait passed; url =", p.evaluate("location.pathname"), flush=True)
    for i in range(20):
        p.wait_for_timeout(500)
        s = p.evaluate("""() => ({
            url: location.pathname,
            uname: (document.querySelector('.uname')||{}).textContent || '',
            avatar: (document.querySelector('.userchip .avatar')||{}).textContent || '',
            adminLink: [...document.querySelectorAll('.navtabs a')].some(a=>a.textContent.includes('管理看板')),
            bellDot: (document.querySelector('.bell .dot')||{}).textContent || ''
        })""")
        print("+%ds" % ((i+1)//2), s, flush=True)
        if s["uname"] and i > 3:
            break
    b.close()
print("DONE probe2", flush=True)