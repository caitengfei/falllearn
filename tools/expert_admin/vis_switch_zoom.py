# -*- coding: utf-8 -*-
"""vis 追加：switch 放大截图（3x）——on/off 各一，1440 内容页 + 学生页"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\docs\expert-admin"

def main():
    r = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10)
    token = r.json()["token"]
    me = requests.get(BASE + "/api/auth/me", headers={"authorization": f"Bearer {token}"}).json()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=3)
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="domcontentloaded")
        page.evaluate("t => localStorage.setItem('falllearn_token', t)", token)
        page.evaluate("u => localStorage.setItem('falllearn_user', JSON.stringify(u))", me)

        # 学生页（3 个 on 开关）
        page.goto(BASE + "/admin/students", wait_until="domcontentloaded")
        page.wait_for_timeout(600)
        sw = page.locator(".switch").first
        sw.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        box = sw.bounding_box()
        page.screenshot(path=OUT + r"\vis-switch-on-1440.png",
                        clip={"x": max(0, box["x"] - 50), "y": max(0, box["y"] - 30), "width": 200, "height": 90})
        print("on switch box:", box)

        # 内容页：找 off 开关（预告行置顶列），没有则跳过
        page.goto(BASE + "/admin/content", wait_until="domcontentloaded")
        page.wait_for_timeout(600)
        n_off = page.locator(".switch:not(.on)").count()
        if n_off:
            sw2 = page.locator(".switch:not(.on)").first
            sw2.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            box2 = sw2.bounding_box()
            page.screenshot(path=OUT + r"\vis-switch-off-1440.png",
                            clip={"x": max(0, box2["x"] - 50), "y": max(0, box2["y"] - 30), "width": 200, "height": 90})
            print("off switch box:", box2)
        else:
            print("no off switch on content page right now")
        ctx.close()
        browser.close()
    print("done")

if __name__ == "__main__":
    main()