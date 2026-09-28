# -*- coding: utf-8 -*-
"""第二轮：S2026003(干净账号) 验证学习闭环 —— 全测试唯一一次真实 AI 提问。
不交卷、不签到、不重答错题、不调 reset-demo。"""
import sys, os, time, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\content"
LOG = open(os.path.join(OUT, "test_log2.txt"), "w", encoding="utf-8")

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n")
    LOG.flush()

BASE = "http://127.0.0.1:8010"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: log("CONSOLE", m.type, m.text[:200]) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: log("REQFAIL", r.url, r.failure))

    # 登录 S2026003
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026003")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=20000)
    p.wait_for_timeout(1200)
    home3 = p.evaluate("""() => ({
        stats: [...document.querySelectorAll('.stu-card .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
        timeline: (document.querySelector('.tl')||{}).innerText || '(空)',
        kcards: [...document.querySelectorAll('.kcard')].map(e=>e.innerText.replace(/\\n/g,' '))
    })""")
    log("HOME_S3 ==", json.dumps(home3, ensure_ascii=False, indent=1))
    p.screenshot(path=os.path.join(OUT, "home_s3_blank.png"))

    # 学习中心：无历史应正常渲染
    p.goto(BASE + "/learn", wait_until="domcontentloaded")
    try:
        p.wait_for_selector(".chat-input", timeout=12000)
        log("LEARN_S3_RENDER_OK (无历史，输入框可见)")
    except Exception as e:
        log("LEARN_S3_RENDER_FAIL", e)
    p.wait_for_timeout(500)
    p.screenshot(path=os.path.join(OUT, "learn_s3_before.png"))

    # 唯一一次真实提问
    p.locator(".chat-input textarea").fill("什么是跌倒")
    p.locator(".chat-input .btn").click()
    log("ASK_SENT(什么是跌倒, S2026003) t0=", time.strftime("%H:%M:%S"))
    t_clarify = time.time()
    try:
        p.wait_for_selector(".qopt", timeout=150000)
        log("CLARIFY_AFTER", round(time.time() - t_clarify, 1), "s")
    except Exception:
        log("CLARIFY_TIMEOUT_150s; 继续等四栏")
    p.wait_for_timeout(400)
    qcard = p.evaluate("""() => {
        const q = document.querySelector('.qcard');
        return q ? q.innerText.trim().replace(/\\n+/g,' ¶ ') : null;
    }""")
    log("CLARIFY_CARD ==", qcard)
    p.screenshot(path=os.path.join(OUT, "learn_s3_clarify.png"))
    if qcard:
        p.locator(".qopt").first.click()
        log("OPTION_CLICKED t=", time.strftime("%H:%M:%S"))
    t0 = time.time()
    try:
        p.wait_for_function("!!document.querySelector('.chat-flow .col')", timeout=180000)
        log("FOUR_COL_DONE elapsed=", round(time.time() - t0, 1), "s")
    except Exception:
        log("FOUR_COL_TIMEOUT_180s")
    p.wait_for_timeout(1000)
    ans = p.evaluate("""() => {
        const ms = [...document.querySelectorAll('.chat-flow .msg.ai')];
        const last = ms[ms.length-1];
        return last ? last.innerText.trim() : '';
    }""")
    log("AI_ANSWER_S3_HEAD ==", ans.replace("\n", " ¶ ")[:600])
    p.screenshot(path=os.path.join(OUT, "learn_s3_done.png"), full_page=True)
    with open(os.path.join(OUT, "ai_answer_s3.txt"), "w", encoding="utf-8") as f:
        f.write(ans)

    # 我的页：首答之章
    p.goto(BASE + "/mine", wait_until="domcontentloaded")
    p.wait_for_selector(".radar-box", timeout=15000)
    p.wait_for_timeout(600)
    mine3 = p.evaluate("""() => ({
        stats: [...document.querySelectorAll('.stu-stats .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
        badges: ([...document.querySelectorAll('.card')].find(c=>c.innerText.includes('勋章墙'))||{}).innerText.replace(/\\n+/g,' ¶ ') || ''
    })""")
    log("MINE_S3 ==", json.dumps(mine3, ensure_ascii=False, indent=1))
    p.screenshot(path=os.path.join(OUT, "mine_s3.png"))
    b.close()
LOG.close()
log("ALL_DONE_2")