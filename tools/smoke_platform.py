# -*- coding: utf-8 -*-
"""快速冒烟：登录→各路由渲染→移动端溢出→白屏回归→守卫/404。不调 DSH 问答。"""
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8010"
SHOT = r"E:\lilei\docs\smoke"
fails = []


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def cur_url(p):
    try:
        return p.evaluate("location.href")
    except Exception:
        return p.url


def check(name, cond, extra=""):
    if cond:
        log(f"  ✓ {name} {extra}")
    else:
        log(f"  ✗ {name} {extra}")
        fails.append(name)


def overflow(p):
    return p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def wait_text(p, needle, timeout=20):
    """等待页面出现指定文本（远程部署 RTT 高，数据渲染慢于本地，不能 goto 后立刻断言）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if needle in p.inner_text("body"):
            return True
        time.sleep(0.5)
    return False


# 教师重置
_t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + _t["token"]}, timeout=30)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)

    # ---------- 桌面 1440 ----------
    p = b.new_page(viewport={"width": 1440, "height": 950})
    js_errors = []
    p.on("pageerror", lambda e: js_errors.append(str(e)))

    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    check("登录页无外壳", p.locator(".topbar").count() == 0)
    check("登录页一键体验", p.locator(".dh-btn").count() == 4)
    p.screenshot(path=SHOT + "-login.png")

    # 学生登录（S2026001 有种子历史）
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    ok = False
    t0 = time.time()
    while time.time() - t0 < 15:
        if "张小明" in p.inner_text("body"):
            ok = True
            break
        time.sleep(1)
    check("学生登录", ok)
    p.screenshot(path=SHOT + "-home.png")
    check("首页水平溢出=0", overflow(p) <= 0, f"(overflow={overflow(p)})")
    check("首页演示引导卡（首访）", p.locator(".gc-step").count() >= 6, f'({p.locator(".gc-step").count()} steps)')
    check("banner 4 dots", p.locator(".banner-dots i").count() == 4)
    check("轮播第2张可点", (p.locator(".banner-dots i").nth(1).click(), time.sleep(1), p.inner_text(".banner h2"))[2] != "")

    # 学习中心（种子历史 1 条 → 白屏回归关键用例）
    p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    t0 = time.time()
    ok = False
    while time.time() - t0 < 20:
        body = p.inner_text("body")
        if "【岗】" in body:
            ok = True
            break
        time.sleep(1)
    check("/learn 历史回放（白屏回归）", ok)
    check("/learn 水平溢出=0", overflow(p) <= 0, f"(overflow={overflow(p)})")
    p.screenshot(path=SHOT + "-learn.png", full_page=True)
    # 簇抽屉
    p.locator(".kmap .kcard").first.click()
    check("簇抽屉打开", "知识点详解" in p.inner_text("body"))
    p.screenshot(path=SHOT + "-learn-drawer.png")

    # 比赛资料
    p.goto(BASE + "/competition", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    check("/competition 渲染", "岗课赛证融通资料库" in p.inner_text("body"))
    check("/competition 文档数", p.locator(".doc-row").count() >= 15, f"({p.locator('.doc-row').count()} docs)")
    check("/competition 溢出=0", overflow(p) <= 0)
    p.goto(BASE + "/report", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    check("/report 渲染", "我的学习报告" in p.inner_text("body"))
    check("/report 溢出=0", overflow(p) <= 0)
    p.goto(BASE + "/kb", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    check("/kb 渲染", "知识库" in p.inner_text("body"))
    check("/kb 文档卡数", p.locator(".kcard").count() >= 20, f"({p.locator('.kcard').count()} cards)")
    check("/kb 溢出=0", overflow(p) <= 0)
    p.screenshot(path=SHOT + "-competition.png", full_page=True)

    # 练习
    p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
    check("/practice 模拟考卡片", wait_text(p, "12 分钟模拟考"))
    check("/practice 教师布置 tab", wait_text(p, "教师布置"))

    # 错题本（种子 3 题）
    p.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=30000)
    n = 0
    t0 = time.time()
    while time.time() - t0 < 20 and n < 3:
        n = p.locator(".card .btn", has_text="重答这道题").count()
        if n < 3:
            time.sleep(0.5)
    check("/wrong 列表", n >= 3, f"({n} 题)")
    check("/wrong 调度文案", "连对 2 次" in p.inner_text("body"))
    # 讲解弹窗
    p.locator(".card .btn", has_text="看讲解").first.click()
    check("/wrong 讲解弹窗", p.locator(".mask").count() > 0 and "正确答案" in p.inner_text("body"))
    p.screenshot(path=SHOT + "-wrong.png")
    p.locator(".modal-h .more").click()

    # 我的
    p.goto(BASE + "/mine", wait_until="domcontentloaded", timeout=30000)
    check("/mine 勋章规则", wait_text(p, "掌握度 ≥ 60") or wait_text(p, "连对 10"))
    check("/mine 无假学分", "90 天" not in p.inner_text("body"))
    p.screenshot(path=SHOT + "-mine.png", full_page=True)

    # 404（wait_text 轮询：远程 RTT 高，goto 后 SPA 尚未渲染完，不能立刻断言）
    p.goto(BASE + "/nonexist-page", wait_until="domcontentloaded", timeout=30000)
    check("404 页", wait_text(p, "404 · 页面不存在"))
    p.screenshot(path=SHOT + "-404.png")

    # 学生访问 /admin 应被守卫弹回
    p.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1)
    check("学生 /admin 守卫", "/admin" not in cur_url(p), f"(now={cur_url(p)})")

    check("无 JS 异常", not js_errors, f"{js_errors[:3]}")
    p.close()

    # ---------- 移动 390 ----------
    m = b.new_page(viewport={"width": 390, "height": 844})
    m.on("dialog", lambda d: d.accept())
    m.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    m.locator(".field input").nth(0).fill("S2026001")
    m.locator(".field input").nth(1).fill("123456")
    m.locator(".login-body .btn").click()
    t0 = time.time()
    while time.time() - t0 < 15 and "张小明" not in m.inner_text("body"):
        time.sleep(1)
    m.wait_for_selector(".stu-card", timeout=10000)
    time.sleep(1)
    ov = overflow(m)
    check("移动 390 首页溢出=0", ov <= 0, f"(overflow={ov})")
    m.screenshot(path=SHOT + "-m-home.png")
    m.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    ov = overflow(m)
    check("移动 390 /learn 溢出=0", ov <= 0, f"(overflow={ov})")
    m.screenshot(path=SHOT + "-m-learn.png")
    m.goto(BASE + "/competition", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    ov = overflow(m)
    check("移动 390 /competition 溢出=0", ov <= 0, f"(overflow={ov})")
    m.screenshot(path=SHOT + "-m-comp.png")
    m.goto(BASE + "/report", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    ov = overflow(m)
    check("移动 390 /report 溢出=0", ov <= 0, f"(overflow={ov})")
    m.goto(BASE + "/kb", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)
    ov = overflow(m)
    check("移动 390 /kb 溢出=0", ov <= 0, f"(overflow={ov})")
    m.screenshot(path=SHOT + "-m-kb.png")
    m.close()

    b.close()

log("=" * 40)
if fails:
    log(f"SMOKE FAIL: {fails}")
    sys.exit(1)
log("SMOKE ALL PASS")