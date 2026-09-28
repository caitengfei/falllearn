# -*- coding: utf-8 -*-
"""FallLearn QA 第三轮 — 两个精确复现:
1) 教师登录后导航栏是否有「管理看板」tab; 刷新后是否出现(验证 computed 缓存 bug)
2) 点「12分钟模拟考」卡片是否真的开始模拟考(还是开了日常练习卷)
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\docs\expert-test\qa"
R = {}

def log(m):
    print(m, flush=True)

def shot(p, name):
    try:
        p.screenshot(path=os.path.join(OUT, name)); log(f"  [shot] {name}")
    except Exception as e:
        log(f"  [shot FAIL] {name}: {e}")

def wait_path(p, path, timeout=20):
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        try: last = p.evaluate("location.pathname")
        except Exception: last = None
        if last == path: return last
        time.sleep(0.2)
    return last

def nav_tabs(p):
    return p.evaluate("document.querySelector('.navtabs') ? document.querySelector('.navtabs').innerText : 'NO .navtabs'")

def login(p, sno):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    return wait_path(p, "/", 25)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)

    # ---- 1) 教师管理看板 tab ----
    log("== 1) T2026 管理看板 tab ==")
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    p.on("console", lambda m: log(f"CONSOLE {m.type}: {m.text[:150]}") if m.type == "error" else None)
    login(p, "T2026")
    time.sleep(1.5)
    R["T1_nav_after_login"] = {"path": p.evaluate("location.pathname"), "nav": nav_tabs(p),
                               "admin_tab": "管理看板" in nav_tabs(p)}
    shot(p, "41_teacher_after_login.png")
    p.reload(wait_until="domcontentloaded")
    time.sleep(2)
    R["T2_nav_after_reload"] = {"path": p.evaluate("location.pathname"), "nav": nav_tabs(p),
                                "admin_tab": "管理看板" in nav_tabs(p)}
    shot(p, "42_teacher_after_reload.png")
    ctx.close()

    # ---- 2) 模拟考卡片 ----
    log("== 2) 12分钟模拟考卡片(S2026003) ==")
    ctx2 = b.new_context(viewport={"width": 1440, "height": 950})
    p2 = ctx2.new_page()
    p2.on("console", lambda m: log(f"CONSOLE {m.type}: {m.text[:150]}") if m.type == "error" else None)
    login(p2, "S2026003")
    p2.goto(BASE + "/practice", wait_until="domcontentloaded")
    time.sleep(1.5)
    # 找到「模拟考」卡片并点开始
    card = p2.locator(".card", has_text="模拟考 · 跌倒风险评估")
    R["M1_mock_card_found"] = card.count() > 0
    if card.count():
        card.locator("button", has_text="开始").click()
        t0 = time.time(); last = None
        while time.time() - t0 < 30:
            try: last = p2.evaluate("location.pathname")
            except Exception: pass
            if last and last.startswith("/exam/"): break
            time.sleep(0.2)
        time.sleep(1.5)
        page_txt = p2.evaluate("document.querySelector('.page') ? document.querySelector('.page').innerText.slice(0, 200) : 'NO .page'")
        R["M2_mock_exam_actual"] = {
            "path": last,
            "header_has_daily": "日常练习" in page_txt,
            "page_head": page_txt,
        }
        shot(p2, "43_mock_exam_actual.png")
    ctx2.close()
    b.close()

with open(os.path.join(OUT, "results3.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1)
log(json.dumps(R, ensure_ascii=False, indent=1))