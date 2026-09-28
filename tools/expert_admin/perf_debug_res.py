# -*- coding: utf-8 -*-
"""debug：/admin 导航的完整 resource timing + index.html 引用"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
BASE = "http://127.0.0.1:8010"
html = requests.get(BASE + "/admin", timeout=10).text
print("index.html scripts/links:")
for line in html.splitlines():
    if "assets" in line:
        print("  ", line.strip())

r = requests.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=15)
tok, user = r.json()["token"], r.json()["user"]

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.goto(f"{BASE}/login", wait_until="domcontentloaded")
    pg.evaluate("([t,u])=>{localStorage.setItem('falllearn_token',t);localStorage.setItem('falllearn_user',JSON.stringify(u));}", [tok, user])
    pg.goto(f"{BASE}/admin", wait_until="load")
    res = pg.evaluate("""() => performance.getEntriesByType('resource').map(e => ({
        name: e.name, start: Math.round(e.startTime), dur: Math.round(e.duration),
        size: e.transferSize, enc: e.encodedBodySize }))""")
    for x in sorted(res, key=lambda z: z["start"]):
        print(f"{x['start']:6d} dur={x['dur']:5d} trans={x['size']:8d} enc={x['enc']:8d} {x['name']}")
    b.close()