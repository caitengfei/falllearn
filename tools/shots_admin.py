# -*- coding: utf-8 -*-
"""B 期交付截图：管理后台 4 页 + 学生端首页（含公告条）。"""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\tools\shots"
import os
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    pg = b.new_page(viewport={"width": 1500, "height": 940})
    pg.on("dialog", lambda d: d.accept())

    def login(sno):
        pg.goto(BASE + "/login", wait_until="networkidle")
        pg.evaluate("localStorage.clear()")
        pg.reload(wait_until="networkidle")
        pg.locator(".dh-btn").filter(has_text=sno).first.click()
        pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
        pg.wait_for_timeout(1200)

    # 教师 4 页
    login("T2026")
    pages = [
        ("/admin", "admin-1-overview"),
        ("/admin/content", "admin-2-content"),
        ("/admin/stats", "admin-3-stats"),
        ("/admin/ai", "admin-4-ai"),
    ]
    for path, name in pages:
        pg.goto(BASE + path, wait_until="networkidle")
        pg.wait_for_timeout(2600)  # AI 页等模型目录
        pg.screenshot(path=f"{OUT}\\{name}.png", full_page=(name == "admin-1-overview"))
        print("shot", name)

    # 学生端首页
    login("S2026001")
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(1800)
    pg.screenshot(path=f"{OUT}\\student-home.png", full_page=True)
    print("shot student-home")
    b.close()
print("DONE")