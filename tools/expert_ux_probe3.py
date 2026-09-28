# -*- coding: utf-8 -*-
"""探针3：学生 S2026001 直达 /admin（路由无角色守卫，后端 require_teacher）→ 观察前端表现"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_student_admin_log.jsonl")

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("dialog", lambda d: d.dismiss())
    try:
        p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_selector(".login-card", timeout=30000)
        p.locator(".field input").nth(0).fill("S2026001")
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        p.wait_for_timeout(1500)
        p.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(2500)
        err = p.locator(".card.err")
        err_txt = err.inner_text().strip()[:150] if err.count() else ""
        rows = p.locator("table tbody tr").count()
        reset_btn = p.locator("button", has_text="一键重置演示账号").count()
        log("student_direct_admin", url=p.evaluate("location.pathname"),
            error_card=err_txt or "(无)", student_rows=rows, reset_btn_visible=reset_btn,
            note="学生 URL 直达 /admin：前端无角色守卫，后端 403 时的页面表现")
        p.screenshot(path=os.path.join(OUT, "student_admin.png"))
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-400:])
    finally:
        b.close()
print("DONE student-admin", flush=True)