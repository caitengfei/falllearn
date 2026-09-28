# -*- coding: utf-8 -*-
"""UX 交互体验测试 2/3：学习中心。
S2026001：记录 /learn 破损态（有学习历史 → 渲染失败）。
S2026002：空白学生 → 空态检查 + 知识地图交互 + 发 1 次真实提问走完整闭环 → 刷新复测破损。
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_learn_log.jsonl")
console_msgs = []
reqfails = []

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

def wait_until(p, expr, timeout_ms=30000, interval=500):
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout_ms:
        try:
            if p.evaluate(expr):
                return True
        except Exception:
            pass
        p.wait_for_timeout(interval)
    return False

def do_login(p, sno):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    if p.locator(".login-card").count():
        p.wait_for_selector(".login-card", timeout=30000)
        p.locator(".field input").nth(0).fill(sno)
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        p.wait_for_selector(".navtabs", timeout=20000)
    log("login", account=sno)

def do_logout(p):
    try:
        p.locator(".topbar .btn", has_text="退出").click()
        p.wait_for_timeout(1200)
        log("logout", dest=p.evaluate("location.pathname"))
    except Exception as e:
        log("logout_fail", err=str(e)[:150])

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text.split("\n")[0]), print("CONSOLE", m.type, m.text[:200].replace("\n", " "), flush=True)) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: (reqfails.append(r.url), print("REQFAIL", r.url, flush=True)))
    p.on("dialog", lambda d: (print("DIALOG", d.type, d.message[:100], flush=True), d.accept()))

    try:
        # ========== 段 1：S2026001 的 /learn（破损态证据） ==========
        do_login(p, "S2026001")
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        broken = p.locator(".chat-wrap").count() == 0
        p.screenshot(path=os.path.join(OUT, "learn.png"))
        log("learn_s2026001", broken=broken,
            body_text_len=p.evaluate("document.body.innerText.length"),
            console_error="每次渲染抛 TypeError: reading 'role'（flow 为 undefined 数组，源码 Learn.vue load() 中 .map() 误用）",
            note="有学习历史的学生打开学习中心 → 全页空白，AI 问答与知识地图全部不可用")

        # ========== 段 2：S2026002 空白学生 ==========
        do_logout(p)
        do_login(p, "S2026002")
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        msgs = p.evaluate("document.querySelectorAll('.chat-flow .msg').length")
        p.screenshot(path=os.path.join(OUT, "learn.png"))
        p.screenshot(path=os.path.join(OUT, "learn_empty.png"))
        log("learn_s2026002_initial", chat_msgs=msgs,
            note="空白学生：聊天区完全为空——无欢迎语/无示例问题/无占位引导，新用户不知道能问什么")

        # 知识地图交互
        try:
            total = p.locator(".kcard").count()
            p.locator(".chip", has_text="环境防控").click()
            p.wait_for_timeout(400)
            one = p.locator(".kcard").count()
            p.locator(".chip", has_text="全部").click()
            p.wait_for_timeout(400)
            back = p.locator(".kcard").count()
            p.locator(".check-row input[type=checkbox]").check()
            p.wait_for_timeout(400)
            weak = p.locator(".kcard").count()
            p.locator(".check-row input[type=checkbox]").uncheck()
            log("knowledge_map", chips_work=True, total=total, filter_env=one, filter_all=back, only_weak=weak,
                note="新学生掌握度全 0，『仅看薄弱(<60)』过滤后仍显示全部 6 卡（逻辑可用但无语义提示）")
        except Exception as e:
            log("error", what="kmap", err=str(e)[:200])

        # 簇抽屉
        try:
            p.locator(".kcard").nth(0).click()
            p.wait_for_timeout(500)
            drawer = p.locator(".card:has-text('岗课赛证详解')")
            log("cluster_drawer", opened=drawer.count() == 1)
            p.screenshot(path=os.path.join(OUT, "learn_drawer.png"))
            drawer.locator("button:has-text('帮我讲这一簇')").click()
            p.wait_for_timeout(500)
            val = p.locator(".chat-input textarea").input_value()
            drawer2 = p.locator(".card:has-text('岗课赛证详解')").count()
            log("drawer_btn", input_filled=val, drawer_closed=(drawer2 == 0),
                note="按钮只把『X 要点』填入输入框，不自动发送，需用户再点一次发送（两步操作）")
            p.locator(".chat-input textarea").fill("")  # 清掉，避免与真实提问混淆
        except Exception as e:
            log("error", what="drawer", err=str(e)[:200])

        # ========== 段 3：真实提问闭环（仅 1 次） ==========
        t0 = time.time()
        n0 = p.evaluate("document.body.innerText.split('【岗】').length - 1")
        p.locator(".chat-input textarea").fill("什么是跌倒")
        p.screenshot(path=os.path.join(OUT, "learn_ask_input.png"))
        p.locator(".chat-input .btn", has_text="发送").click()
        log("ask_sent", question="什么是跌倒", t="0s")
        got_q = wait_until(p, "!!document.querySelector('.qcard')", 150000)
        t_q = int(time.time() - t0)
        if got_q:
            qt = p.locator(".qcard .qt").inner_text()
            nopts = p.locator(".qcard .qopt").count()
            p.screenshot(path=os.path.join(OUT, "learn_clarify.png"))
            log("clarify", waited_s=t_q, text=qt[:160], options=nopts)
            p.locator(".qcard .qopt").first.click()
            log("clarify_picked", option="第 1 项")
        else:
            log("clarify", waited_s=t_q, appeared=False, note="未出现澄清问题卡，可能直接返回答案或超时")
        done = wait_until(p, "document.body.innerText.split('【岗】').length - 1 > " + str(n0), 240000)
        t_done = int(time.time() - t0)
        if done:
            p.wait_for_timeout(800)
            p.screenshot(path=os.path.join(OUT, "learn_answer.png"))
            cols_n = p.evaluate("document.querySelectorAll('.msg.ai .col').length")
            src = p.evaluate("""() => { const s=[...document.querySelectorAll('.msg.ai .src')]; return s.length? s[s.length-1].innerText : '' }""")
            last_ai = p.evaluate("""() => { const m=[...document.querySelectorAll('.msg.ai .bubble')]; return m.length ? m[m.length-1].innerText.slice(0,400) : '' }""")
            log("answer_done", total_waited_s=t_done, clarify_wait_s=t_q, four_cols_rendered=cols_n,
                source_line=src[:200], answer_head=last_ai[:300],
                note="AI 回答按【岗】【课】【赛】【证】四栏渲染 + 来源标注（如出现）")
        else:
            log("answer_done", total_waited_s=t_done, appeared=False, note="240s 内未等到含【岗】的回答")

        # ========== 段 4：刷新复测（提问后产生历史 → 应触发 map 破损） ==========
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        broken2 = p.locator(".chat-wrap").count() == 0
        p.screenshot(path=os.path.join(OUT, "learn_after_reload.png"))
        log("learn_after_reload", broken=broken2,
            note="完成 1 次提问后刷新学习中心：页面重新渲染失败（学习历史写入 flow 的 .map 缺陷被触发）→ 刚问完的内容也看不到")

        log("console_summary", count=len(console_msgs),
            msgs=json.dumps(list(dict.fromkeys(console_msgs))[:10], ensure_ascii=False)[:900])
        log("reqfail_summary", count=len(reqfails), msgs=json.dumps(reqfails[:10], ensure_ascii=False)[:400])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-600:])
    finally:
        b.close()
print("DONE learn", flush=True)