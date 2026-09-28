# -*- coding: utf-8 -*-
"""EXPERT-ux shared helpers for Playwright black-box tests."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8010"
DOCS = r"E:\lilei\platform\docs\expert-admin"
os.makedirs(DOCS, exist_ok=True)

PREFIX = "EXPERT-ux-"


def log(msg):
    print(msg, flush=True)


def shot(page, name):
    p = os.path.join(DOCS, name)
    page.screenshot(path=p, full_page=False)
    log(f"[shot] {p}")
    return p


def launch():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    dialogs = []
    page.on("dialog", lambda d: dialogs.append(d.message) or d.accept())
    return pw, browser, ctx, page, dialogs


def login(page, sno="T2026", pwd="123456"):
    page.goto(BASE + "/login", wait_until="domcontentloaded")
    page.fill('input[placeholder^="如 S2026001"]', sno)
    page.fill('input[placeholder="密码"]', pwd)
    page.click("button:has-text('登')")
    page.wait_for_timeout(1200)
    return page.evaluate("location.href")


def login_api(sno="T2026", pwd="123456"):
    import requests
    r = requests.post(BASE + "/api/auth/login", json={"student_no": sno, "password": pwd}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def api(token, method, path, body=None):
    import requests
    h = {"authorization": "Bearer " + token}
    r = requests.request(method, BASE + path, json=body, headers=h, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = r.text[:200]
    return r.status_code, data


def dump(name, obj):
    p = os.path.join(DOCS, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    log(f"[dump] {p}")
    return p