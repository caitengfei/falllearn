# -*- coding: utf-8 -*-
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\docs\expert-test\qa"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026003")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=20000)
    p.goto(BASE + "/practice", wait_until="domcontentloaded")
    time.sleep(1.5)
    items = p.locator(".menu-item")
    print("menu items:", items.count(), flush=True)
    for i in range(items.count()):
        print(i, items.nth(i).inner_text(), flush=True)
    items.nth(1).click()
    time.sleep(1.0)
    cards = p.locator(".page .card")
    print("cards:", cards.count(), flush=True)
    for i in range(cards.count()):
        t = cards.nth(i).inner_text().replace("\n", "|")[:120]
        print(f"card{i}: {t}", flush=True)
    btns = p.locator(".page .card button")
    print("buttons in cards:", btns.count(), flush=True)
    for i in range(btns.count()):
        bb = btns.nth(i)
        print(f"btn{i}: text={bb.inner_text()!r} disabled={bb.is_disabled()}", flush=True)
    p.screenshot(path=OUT + r"\44_practice_mock_menu.png")
    # 点第一个「开始」
    target = p.locator(".page .card button", has_text="开始").first
    print("target count:", p.locator(".page .card button", has_text="开始").count(), flush=True)
    target.click(timeout=10000)
    t0 = time.time(); last = None
    while time.time() - t0 < 30:
        try: last = p.evaluate("location.pathname")
        except Exception: pass
        if last and last.startswith("/exam/"): break
        time.sleep(0.2)
    time.sleep(1.5)
    page_txt = p.evaluate("document.querySelector('.page') ? document.querySelector('.page').innerText.slice(0, 260) : 'NO .page'")
    print("PATH:", last, flush=True)
    print("PAGE:", page_txt, flush=True)
    print("header_daily:", "日常练习" in page_txt, flush=True)
    p.screenshot(path=OUT + r"\43_mock_exam_actual.png")
    ctx.close(); b.close()