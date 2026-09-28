# -*- coding: utf-8 -*-
"""视觉设计专家 - 只读截图采集 v2(容错: 单页失败不中断)"""
import sys, os, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\visual"
for d in ("1440", "1280", "mobile"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)

BASE = "http://127.0.0.1:8010"
console_msgs = []

def wait_url(p, want, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = p.evaluate("location.href")
        if h and want in h:
            return True
    return False

def snap(p, path, full=True):
    p.screenshot(path=path, full_page=full)
    print("SNAP", path, flush=True)

def login(p, sno, pwd):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill(pwd)
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card, .page", timeout=15000)

def goto_page(p, url, selector, timeout=15000):
    """导航并尽力等 selector; 失败不抛错, 返回是否等到"""
    p.goto(BASE + url, wait_until="domcontentloaded", timeout=30000)
    try:
        p.wait_for_selector(selector, timeout=timeout)
        p.wait_for_timeout(600)
        return True
    except Exception:
        print("WAIT_FAIL", url, selector, "-> 截实际状态", flush=True)
        p.wait_for_timeout(1200)
        return False

def do_exam(p, shot_path):
    goto_page(p, "/practice", ".menu-item")
    p.locator("button:has-text('开始')").first.click()
    p.wait_for_selector(".opt", timeout=20000)
    for _ in range(15):
        if p.evaluate("document.querySelector('.score-ring') !== null"):
            break
        opts = p.locator(".opt")
        if opts.count():
            opts.first.click()
            nxt = p.locator("button:has-text('下一题')")
            if nxt.count() and nxt.first.is_visible():
                nxt.first.click()
            else:
                p.locator("button:has-text('交 卷')").first.click()
        p.wait_for_timeout(600)
    p.wait_for_selector(".score-ring", timeout=30000)
    p.wait_for_timeout(800)
    snap(p, shot_path)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    p.on("console", lambda m: (console_msgs.append(f"[{m.type}] {m.text[:300]} @ {(m.location or {}).get('url','')}"),
                               print("CONSOLE", m.type, m.text[:200], "@", (m.location or {}).get("url", ""), flush=True))
          if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: print("REQFAIL", r.url, r.failure, flush=True))
    p.on("dialog", lambda d: print("DIALOG", d.type, d.message[:100], flush=True) or d.accept())

    # ---------- 登录页(1440) ----------
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.wait_for_timeout(600)
    snap(p, OUT + r"\1440\login.png")

    # ---------- 登录错误态 ----------
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("wrongpass")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".err", timeout=15000)
    p.wait_for_timeout(300)
    snap(p, OUT + r"\1440\login-error.png")

    # ---------- 正确登录 ----------
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    p.wait_for_timeout(800)
    snap(p, OUT + r"\1440\home.png")

    # ---------- 学生各页(1440) ----------
    goto_page(p, "/learn", ".chat-wrap");        snap(p, OUT + r"\1440\learn.png")
    learn_html_len = p.evaluate("document.body ? document.body.innerText.length : 0")
    print("LEARN_BODY_TEXT_LEN", learn_html_len, flush=True)
    if p.evaluate("document.querySelector('.chat-wrap') === null"):
        err_info = p.evaluate("(() => { const c = document.querySelector('#app'); return c ? c.innerText.slice(0, 300) : 'NO APP' })()")
        print("LEARN_RENDER_STATE", repr(err_info), flush=True)
    goto_page(p, "/practice", ".menu-item");     snap(p, OUT + r"\1440\practice.png")
    goto_page(p, "/wrong", ".row-item, .empty"); snap(p, OUT + r"\1440\wrong.png")
    goto_page(p, "/mine", "svg");                snap(p, OUT + r"\1440\mine.png")

    # ---------- 练习 -> 成绩报告(分数环) ----------
    try:
        do_exam(p, OUT + r"\1440\exam-report.png")
    except Exception as e:
        print("EXAM_FAIL", e, flush=True)
        snap(p, OUT + r"\1440\exam-fail-state.png")

    # ---------- 1280x800 视口(同会话重截) ----------
    p.set_viewport_size({"width": 1280, "height": 800})
    p.wait_for_timeout(400)
    if p.evaluate("document.querySelector('.score-ring') !== null"):
        snap(p, OUT + r"\1280\exam-report.png")
    goto_page(p, "/", ".stu-card");              snap(p, OUT + r"\1280\home.png")
    goto_page(p, "/learn", ".chat-wrap");        snap(p, OUT + r"\1280\learn.png")
    goto_page(p, "/practice", ".menu-item");     snap(p, OUT + r"\1280\practice.png")
    goto_page(p, "/wrong", ".row-item, .empty"); snap(p, OUT + r"\1280\wrong.png")
    goto_page(p, "/mine", "svg");                snap(p, OUT + r"\1280\mine.png")

    # ---------- 教师看板 ----------
    try:
        p.locator("button:has-text('退出')").first.click()
        p.wait_for_selector(".login-card", timeout=20000)
    except Exception as e:
        print("LOGOUT_FAIL", e, flush=True)
        p.goto(BASE + "/login", wait_until="domcontentloaded")
        p.wait_for_selector(".login-card", timeout=20000)
    login(p, "T2026", "123456")
    p.wait_for_timeout(500)
    goto_page(p, "/admin", "table")
    snap(p, OUT + r"\1280\admin.png")
    p.set_viewport_size({"width": 1440, "height": 950})
    p.wait_for_timeout(400)
    snap(p, OUT + r"\1440\admin.png")
    b.close()

    # ---------- 移动视口 390x844(新上下文, 全新登录) ----------
    b2 = pw.chromium.launch(channel="msedge", headless=True)
    m = b2.new_context(viewport={"width": 390, "height": 844})
    pm = m.new_page()
    pm.on("console", lambda x: print("MCONSOLE", x.type, x.text[:150], flush=True) if x.type == "error" else None)
    pm.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    pm.wait_for_selector(".login-card", timeout=30000)
    pm.wait_for_timeout(500)
    snap(pm, OUT + r"\mobile\login.png")
    login(pm, "S2026001", "123456")
    pm.wait_for_timeout(600)
    snap(pm, OUT + r"\mobile\home.png")
    for url, sel, name in [("/learn", ".chat-wrap", "learn"), ("/practice", ".menu-item", "practice"),
                           ("/wrong", ".row-item, .empty", "wrong"), ("/mine", "svg", "mine")]:
        goto_page(pm, url, sel)
        snap(pm, os.path.join(OUT, "mobile", name + ".png"))
    sw = pm.evaluate("document.documentElement.scrollWidth")
    cw = pm.evaluate("document.documentElement.clientWidth")
    print("MOBILE_OVERFLOW", sw > cw, "scrollW=", sw, "clientW=", cw, flush=True)
    b2.close()

    print("DONE")
    print("CONSOLE_ERROR_COUNT", len([c for c in console_msgs if c.startswith("[error]")]))
    for c in dict.fromkeys(c for c in console_msgs if c.startswith("[error]")):
        print("  ", c[:220], flush=True)