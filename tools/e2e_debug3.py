# -*- coding: utf-8 -*-
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.goto("http://127.0.0.1:8010/", wait_until="domcontentloaded", timeout=30000)
    for i in range(12):
        try:
            loc = p.evaluate("window.location.href")
        except Exception as e:
            loc = f"eval-err {e}"
        print(f"t={i+1}s  p.url={p.url}  location={loc}", flush=True)
        time.sleep(1)
    b.close()