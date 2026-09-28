# -*- coding: utf-8 -*-
"""探针：登录后顶栏（用户名/管理看板 tab）的更新时机——学生 vs 教师 vs 整页刷新"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_topbar_probe_log.jsonl")

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:260], flush=True)

def snapshot(p, tag):
    s = p.evaluate("""() => ({
        url: location.pathname,
        uname: (document.querySelector('.uname')||{}).textContent || '',
        udept: (document.querySelector('.udept')||{}).textContent || '',
        avatar: (document.querySelector('.userchip .avatar')||{}).textContent || '',
        adminLink: !!document.querySelector('.navtabs a') && [...document.querySelectorAll('.navtabs a')].some(a=>a.textContent.includes('管理看板')),
        stuBadge: (document.querySelector('.stu-badge')||{}).textContent || ''
    })""")
    log("snap", tag=tag, **s)
    return s

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("dialog", lambda d: d.dismiss())
    try:
        # --- 学生登录 ---
        p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_selector(".login-card", timeout=30000)
        p.locator(".field input").nth(0).fill("S2026001")
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        t0 = time.time()
        for i in range(15):
            p.wait_for_timeout(200)
            s = snapshot(p, "student t=+%dms" % int((time.time()-t0)*1000))
            if s["uname"]:
                break
        # --- 页面内退出 → 教师登录（无整页刷新） ---
        p.locator(".topbar .btn", has_text="退出").click()
        p.wait_for_selector(".login-card", timeout=15000)
        p.wait_for_timeout(300)
        snapshot(p, "after_logout")
        p.locator(".field input").nth(0).fill("T2026")
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        t0 = time.time()
        for i in range(15):
            p.wait_for_timeout(200)
            s = snapshot(p, "teacher t=+%dms" % int((time.time()-t0)*1000))
            if s["uname"]:
                break
        # --- 整页刷新 ---
        p.reload(wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(1500)
        snapshot(p, "after_reload")
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-500:])
    finally:
        b.close()
print("DONE topbar-probe", flush=True)