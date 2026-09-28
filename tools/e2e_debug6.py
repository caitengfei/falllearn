# -*- coding: utf-8 -*-
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: print(f"CON[{m.type}]: {m.text}", flush=True) if m.type in ("error", "warning") else None)
    p.on("framenavigated", lambda f: print(f"NAV: {f.url}", flush=True) if f == p.main_frame else None)
    p.on("request", lambda r: print(f"REQ: {r.method} {r.url}", flush=True) if "/api/quiz" in r.url or "/exam" in r.url else None)

    p.goto("http://127.0.0.1:8010/login", wait_until="domcontentloaded")
    p.wait_for_selector(".login-card", timeout=15000)
    p.locator(".field input").nth(0).fill("S2026003")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    print("t0 home:", flush=True)
    p.locator(".navtabs a", has_text="练习考试").click()
    p.wait_for_selector(".card .btn", timeout=10000)
    btns = p.locator(".card .btn")
    print(f"btn count: {btns.count()}, texts:", flush=True)
    for i in range(btns.count()):
        print("  btn", i, repr(btns.nth(i).inner_text()), "disabled:", btns.nth(i).is_disabled(), flush=True)
    print("clicking first 开始...", flush=True)
    btns.first.click()
    t0 = time.time()
    for i in range(20):
        time.sleep(1)
        print(f"t={1*(i+1)}s url={p.url}", flush=True)
    b.close()