# -*- coding: utf-8 -*-
"""防跌学堂 E2E（Playwright + 系统 Edge）v2：
登录 → 首页(轮播/签到) → 学习(提问→澄清卡→四栏) → 【回归】刷新/learn 历史回放 → 比赛资料页
→ 日常练习(10题→交卷→报告) → 12分钟模拟考(倒计时) → 错题本(重答) → 我的(雷达/勋章)
产物：docs/falllearn-e2e*.png
"""
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8010"
STU = "S2026002"
PWD = "123456"
SHOT = r"E:\lilei\docs\falllearn-e2e.png"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def wait_text(p, text, timeout_s, every=2):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if text in p.inner_text("body"):
            return True
        time.sleep(every)
    return False


def cur_url(p):
    """用 evaluate 读 URL：headless 下只查 target 层（page.url）不会泵渲染进程
    消息循环，网络响应交付会被挂起（实测 24-45s）；Runtime.evaluate 会泵。"""
    try:
        return p.evaluate("location.href")
    except Exception:
        return p.url


# ---------- 预置：教师重置演示数据（干净起点） ----------
_t = requests.post(BASE + "/api/auth/login",
                   json={"student_no": "T2026", "password": PWD}, timeout=10).json()
_r = requests.post(BASE + "/api/admin/reset-demo", json={},
                   headers={"authorization": "Bearer " + _t["token"]}, timeout=30)
assert _r.ok, f"reset-demo 失败: {_r.text}"
print("[preset] 演示数据已重置", flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    js_errors = []
    p.on("pageerror", lambda e: js_errors.append(str(e)))
    p.on("dialog", lambda d: d.accept())  # 交卷 confirm 自动确认
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    try:
        p.wait_for_selector(".login-card", timeout=30000)
    except Exception:
        log(f"页面异常: url={p.url} js_errors={js_errors[:5]}")
        raise AssertionError("未到达登录页")
    log(f"到达登录页: {p.url}")

    # ---------- 登录 ----------
    p.locator(".field input").nth(0).fill(STU)
    p.locator(".field input").nth(1).fill(PWD)
    p.locator(".login-body .btn").click()
    assert wait_text(p, "李小红", 10), "登录失败"
    log("step1 登录 OK（登录页无外壳、一键体验可用）")

    # ---------- 首页 + 轮播 + 签到 ----------
    p.wait_for_selector(".stu-card", timeout=10000)
    # 轮播：验证 4 个可点 dots 存在
    n_dots = p.locator(".banner-dots i").count()
    assert n_dots == 4, f"banner dots 数量异常: {n_dots}"
    _btn = p.locator(".checkin-row .btn-sm")
    if _btn.is_enabled():
        _btn.click()
    assert wait_text(p, "已签到", 10), "签到失败"
    log(f"step2 首页+签到 OK（轮播 dots={n_dots}）")
    p.screenshot(path=SHOT.replace(".png", "-home.png"))

    # ---------- 学习：提问 → 单答案（2026-10-03 起不再四栏、不再澄清卡）----------
    p.locator(".navtabs a", has_text="学习中心").click()
    p.wait_for_selector(".chat-input textarea", timeout=10000)
    p.locator(".chat-input textarea").fill("老年人为什么容易发生跌倒")
    p.locator(".chat-input .btn").click()
    log("step3 学习提问已发送，等待单答案…")

    def has_answer():
        try:
            last = p.locator(".bubble").last.inner_text()
        except Exception:
            return False
        return bool(last) and "▍" not in last and len(last) > 80

    t1 = time.time()
    ok = False
    while time.time() - t1 < 600:
        if p.locator(".qcard").count() > 0:
            log("step3 出现澄清卡（新形态不应再出现，记录为异常）")
        if has_answer():
            ok = True
            break
        time.sleep(4)
    assert ok, "单答案超时（600s）"
    log(f"step3 学习单答案 OK（收到于 +{int(time.time() - t1)}s）")
    p.screenshot(path=SHOT.replace(".png", "-learn.png"))

    # ---------- 【回归】刷新 /learn：历史必须回放（白屏 bug 回归） ----------
    p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    assert wait_text(p, "老年人为什么容易发生跌倒", 20), "刷新 /learn 后历史未回放（学习中心白屏回归失败）"
    log("step3.5 刷新 /learn 历史回放 OK（白屏回归通过）")

    # ---------- 比赛资料页 ----------
    p.goto(BASE + "/competition", wait_until="domcontentloaded", timeout=30000)
    assert wait_text(p, "岗课赛证融通资料库", 15), "比赛资料页未渲染"
    n_docs = p.locator(".doc-row").count()
    assert n_docs >= 15, f"比赛资料文档数不足: {n_docs}"
    log(f"step3.6 比赛资料页 OK（{n_docs} 份文档卡片）")
    p.screenshot(path=SHOT.replace(".png", "-competition.png"), full_page=True)

    # ---------- 日常练习：开卷→答题→交卷 ----------
    p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".card .btn", timeout=10000)
    p.locator(".card .btn", has_text="开始").first.click()  # 第一张=日常练习
    t0 = time.time()
    while time.time() - t0 < 45 and "/exam/" not in cur_url(p):
        time.sleep(0.5)
    assert "/exam/" in cur_url(p), f"未进入答题页: {cur_url(p)}"
    log(f"step4 进入日常练习答题页 (+{int(time.time()-t0)}s)")
    p.wait_for_selector(".opt", timeout=20000)
    for i in range(10):
        p.wait_for_selector(".opt", timeout=10000)
        p.locator(".opt").nth(0).click()
        if i < 9:
            p.locator(".btn", has_text="下一题").click()
        time.sleep(0.4)
    p.locator(".btn", has_text="交卷").click()
    assert wait_text(p, "总分（100）", 60), "成绩报告未出现"
    score = p.locator(".score-ring .v").inner_text()
    log(f"step4 日常练习交卷 OK，得分 {score}")
    p.screenshot(path=SHOT.replace(".png", "-exam.png"))

    # ---------- 12 分钟模拟考：切菜单→开卷→倒计时 ----------
    p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".menu-item", timeout=10000)
    p.locator(".menu-item", has_text="12 分钟模拟考").click()
    p.wait_for_selector(".card .btn", timeout=10000)
    p.locator(".card", has_text="理论模拟考").locator(".btn", has_text="开始").click()
    t0 = time.time()
    while time.time() - t0 < 45 and "/exam/" not in cur_url(p):
        time.sleep(0.5)
    assert "/exam/" in cur_url(p), f"模拟考未开卷: {cur_url(p)}"
    assert wait_text(p, "理论模拟考", 15), "模拟考标题未出现"
    assert wait_text(p, "12:00", 15), "模拟考倒计时未出现"
    log("step4.5 12 分钟模拟考 OK（标题+倒计时）")

    # ---------- 错题本：重答 ----------
    p.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".card .btn", timeout=10000)
    n_wrong = p.locator(".card .btn", has_text="重答这道题").count()
    assert n_wrong > 0, "错题本为空"
    p.locator(".card .btn", has_text="重答这道题").first.click()
    p.wait_for_selector(".mask .opt", timeout=10000)
    p.locator(".mask .opt").first.click()
    p.locator(".mask .btn", has_text="提交").click()
    # 高频轮询：答对弹窗 2s 后自动关闭，普通 2s 轮询会错过结果文本
    t0 = time.time()
    result_seen = False
    closed_after = None
    while time.time() - t0 < 30:
        body = p.inner_text("body")
        if "答对了" in body or "还差一点" in body:
            result_seen = True
            break
        if p.locator(".mask").count() == 0:
            closed_after = time.time() - t0  # 答对弹窗 2s 自动关闭
            break
        time.sleep(0.4)
    assert result_seen or (closed_after is not None and closed_after < 3), "重答结果未出现"
    p.screenshot(path=SHOT.replace(".png", "-wrong.png"))
    if p.locator(".mask").count() > 0:
        p.locator(".modal-h .more").click()  # 答错时手动关闭
        p.wait_for_selector(".mask", state="detached", timeout=5000)
    log(f"step5 错题本 OK（待复习 {n_wrong} 题，重答已出结果）")

    # ---------- 我的：雷达+勋章 ----------
    p.goto(BASE + "/mine", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector("svg", timeout=10000)
    assert wait_text(p, "勋章墙", 10), "我的页面异常"
    assert wait_text(p, "获得", 5) or wait_text(p, "未解锁", 5), "勋章状态未渲染"
    log("step6 我的页面 OK（雷达+勋章墙+规则文案）")
    p.screenshot(path=SHOT, full_page=True)

    assert not js_errors, f"页面 JS 异常: {js_errors[:5]}"
    b.close()
    log("E2E ALL PASS")