# -*- coding: utf-8 -*-
"""复现 E2E 失败场景：学习→练习→开始，全程 framenavigated + 每秒 URL 追踪。"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"

_t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
_r = requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + _t["token"]}, timeout=30)
assert _r.ok
print("[preset] reset done", flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("framenavigated", lambda f: print(f"NAV: {f.url}", flush=True) if f == p.main_frame else None)
    p.on("request", lambda r: print(f"REQ: {r.method} {r.url}", flush=True)
           if any(k in r.url for k in ("/api/quiz", "/exam", "/practice")) else None)
    p.on("response", lambda r: print(f"RESP: {r.status} {r.url}", flush=True)
       if any(k in r.url for k in ("/api/quiz", "/exam", "/practice")) else None)

    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    # 签到（如可点）
    _btn = p.locator(".checkin-row .btn-sm")
    if _btn.is_enabled():
        _btn.click()
    print("[step2] home ok", flush=True)

    # 学习：提问
    p.locator(".navtabs a", has_text="学习中心").click()
    p.wait_for_selector(".chat-input textarea", timeout=10000)
    p.locator(".chat-input textarea").fill("老年人跌倒")
    p.locator(".chat-input .btn").click()
    print("[step3] question sent", flush=True)
    t0 = time.time()
    while time.time() - t0 < 150:
        if p.locator(".qcard").count() > 0:
            p.locator(".qopt").first.click()
            print(f"[step3] qcard answered at +{int(time.time()-t0)}s", flush=True)
            break
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body:
            print("[step3] direct fourcol", flush=True)
            break
        time.sleep(3)
    else:
        print("[step3] learn timeout!", flush=True)
    t1 = time.time()
    while time.time() - t1 < 600:
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body and "来源：" in body:
            break
        time.sleep(4)
    print(f"[step3] fourcol ok +{int(time.time()-t1)}s, url={p.url}", flush=True)

    # 练习
    p.locator(".navtabs a", has_text="练习考试").click()
    p.wait_for_selector(".card .btn", timeout=10000)
    print(f"[step4] practice loaded url={p.url}", flush=True)
    p.locator(".card .btn", has_text="开始").first.click()
    print("[step4] clicked 开始", flush=True)
    t0 = time.time()
    for i in range(24):
        time.sleep(1)
        print(f"t={i+1}s url={p.url}", flush=True)
    b.close()