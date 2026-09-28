# -*- coding: utf-8 -*-
import sys, time
import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errors = []
    p.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
    p.on("console", lambda m: errors.append("CONSOLE " + m.type + ": " + m.text) if m.type == "error" else None)
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    time.sleep(2)
    p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.5)
    cards = p.locator(".card").count()
    btns = [p.locator(".card").nth(i).inner_text()[:60].replace("\n", "|") for i in range(cards)]
    print("cards:", cards, flush=True)
    for i, t in enumerate(btns):
        print(f"  [{i}] {t}", flush=True)
    print("has 理论模拟考:", "理论模拟考" in p.inner_text("body"), flush=True)
    print("ERRORS:", errors[:8], flush=True)
    p.screenshot(path=r"E:\lilei\docs\debug-practice.png", full_page=True)
    b.close()