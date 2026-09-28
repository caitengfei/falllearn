# -*- coding: utf-8 -*-
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errors = []
    p.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
    p.on("console", lambda m: errors.append(f"CONSOLE[{m.type}]: {m.text}") if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: errors.append(f"REQFAIL: {r.url} {r.failure}"))
    p.goto("http://127.0.0.1:8010/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(8)
    print("url:", p.url)
    print("body len:", len(p.inner_text("body")))
    print("body head:", p.inner_text("body")[:200].replace("\n", " | "))
    for e in errors[:15]:
        print(e)
    b.close()