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
    p.on("console", lambda m: print(f"CON[{m.type}]: {m.text}", flush=True))
    reqs = []
    p.on("request", lambda r: reqs.append(r.url) if "/api/learn" in r.url else None)
    def _on_resp(r):
        if "/api/learn" not in r.url:
            return
        print(f"RESP {r.status} {r.url}", flush=True)
        if "/api/learn/ask" in r.url:
            try:
                print("  BODY:", r.text()[:300], flush=True)
            except Exception as e:
                print("  body-err:", e, flush=True)
    p.on("response", _on_resp)

    p.goto("http://127.0.0.1:8010/login", wait_until="domcontentloaded")
    p.wait_for_selector(".login-card", timeout=15000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    p.locator(".navtabs a", has_text="学习中心").click()
    p.wait_for_selector(".chat-input textarea", timeout=10000)
    p.locator(".chat-input textarea").fill("老年人跌倒")
    print("clicking send...", flush=True)
    p.locator(".chat-input .btn").click()
    for i in range(12):
        time.sleep(2)
        if i == 1:
            try:
                html = p.locator(".chat-flow").inner_html()
                print("CHATFLOW:", html[:600], flush=True)
            except Exception as e:
                print("chatflow-err:", e, flush=True)
        print(f"t={2*(i+1)}s url={p.url} qcards={p.locator('.qcard').count()} typing={p.locator('.typing').count()} body_has_岗={'【岗】' in p.inner_text('body')}", flush=True)
    print("--- learn requests:", reqs[:20])
    for e in errs[:10]:
        print(e)
    b.close()