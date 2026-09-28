# -*- coding: utf-8 -*-
"""学生端 + 教师端 全流程只读演示：逐页打开并截图（不产生任何数据）。
用法：D:\\python123\\python.exe E:\\lilei\\platform\\tools\\demo_run.py
截图输出：E:\\lilei\\platform\\tools\\shots\\demo-run\\
"""
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = Path(r"E:\lilei\platform\tools\shots\demo-run")
OUT.mkdir(parents=True, exist_ok=True)

STUDENT_PAGES = [
    ("home", "/", "首页（轮播+九宫格+知识卡）"),
    ("learn", "/learn", "学习中心（AI 老师+知识地图）"),
    ("competition", "/competition", "比赛资料"),
    ("practice", "/practice", "练习考试"),
    ("wrong", "/wrong", "错题本"),
    ("mine", "/mine", "我的（雷达图+勋章+学时）"),
]
TEACHER_PAGES = [
    ("admin", "/admin", "数据总览（指标卡+趋势+排行）"),
    ("content", "/admin/content", "业务管理（预告+轮播）"),
    ("exams", "/admin/exams", "考试管理（记录+CSV 导出）"),
    ("students", "/admin/students", "学生管理"),
    ("accounts", "/admin/accounts", "账号管理"),
    ("trainings", "/admin/trainings", "培训管理"),
    ("stats", "/admin/stats", "培训统计"),
    ("ai", "/admin/ai", "AI 管理（模型/知识库/出题/判卷）"),
]


def login(pg, sno):
    pg.goto(f"{BASE}/login", wait_until="load")
    pg.wait_for_timeout(600)
    pg.locator(".dh-btn", has_text=sno).first.click()
    pg.wait_for_timeout(200)
    pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
    pg.wait_for_timeout(1800)


def visit(pg, name, path, desc, extra_wait=1200):
    url = BASE + path
    pg.goto(url, wait_until="load")
    pg.wait_for_timeout(extra_wait)
    title = pg.evaluate("document.title || ''")
    shot = OUT / f"{name}.png"
    pg.screenshot(path=str(shot), full_page=False)
    print(f"  [ok] {path}  {desc}  -> {shot.name}")
    return shot


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        print("== 登录页 ==")
        pg.goto(f"{BASE}/login", wait_until="load")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(OUT / "00-login.png"))
        print(f"  [ok] /login  登录页（一键体验按钮） -> 00-login.png")

        print("== 学生端 S2026001 ==")
        login(pg, "S2026001")
        landed = pg.evaluate("location.pathname")
        print(f"  登录后落地页: {landed}")
        for name, path, desc in STUDENT_PAGES:
            visit(pg, f"student-{name}", path, desc)

        print("== 教师端 T2026 ==")
        pg.evaluate("Object.keys(localStorage).forEach(k => localStorage.removeItem(k))")
        login(pg, "T2026")
        landed = pg.evaluate("location.pathname")
        print(f"  登录后落地页: {landed}")
        for name, path, desc in TEACHER_PAGES:
            # AI 页模型目录冷启动稍慢
            visit(pg, f"teacher-{name}", path, desc, extra_wait=2500 if name == "ai" else 1200)

        b.close()

        js_errors = [e for e in errors if "404" not in e and "favicon" not in e]
        print(f"\n页面 JS 报错: {len(js_errors)}")
        for e in js_errors[:5]:
            print("   ", e[:120])
        print(f"\n截图目录: {OUT}")
        return 0 if not js_errors else 1


if __name__ == "__main__":
    sys.exit(main())