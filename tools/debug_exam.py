# -*- coding: utf-8 -*-
import sys, time
import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"

_t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + _t["token"]}, timeout=30)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errors = []
    p.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
    p.on("console", lambda m: errors.append("CONSOLE " + m.type + ": " + m.text) if m.type == "error" else None)
    p.on("dialog", lambda d: d.accept())
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    time.sleep(2)
    p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".card .btn", timeout=10000)
    p.locator(".card .btn", has_text="开始").first.click()
    time.sleep(3)
    url = p.evaluate("location.href")
    print("URL:", url, flush=True)
    print("opt count:", p.locator(".opt").count(), flush=True)
    body = p.inner_text("body")[:600]
    print("BODY:", body.replace("\n", " | ")[:600], flush=True)
    time.sleep(5)
    print("after 5s opt count:", p.locator(".opt").count(), flush=True)
    print("AFTER BODY:", p.inner_text("body")[:400].replace("\n", " | "), flush=True)
    print("ERRORS:", errors[:10], flush=True)
    p.screenshot(path=r"E:\lilei\docs\debug-exam.png", full_page=True)
    b.close()