# -*- coding: utf-8 -*-
"""UX 交互体验测试 2/3 (v2)：学习中心。
背景：/learn 的 load() 存在 .map() 缺陷——只要有学习历史，页面渲染即崩溃（S2026001/2/3 全部复现）。
本脚本：① S2026001 记录破损态；② S2026002 用浏览器端路由拦截把 /api/learn/history 置空，
        验证其余 UI（空态/知识地图/簇抽屉）+ 发 1 次真实提问走完整闭环（后端真实调用）；
        ③ 移除拦截后刷新，复现『问完一题、刷新即空白』。
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_learn_log2.jsonl")
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
    except Exception as e:
        log("logout_fail", err=str(e)[:150])

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text.split("\n")[0]), print("CONSOLE", m.type, m.text[:200].replace("\n", " "), flush=True)) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: (reqfails.append(r.url), print("REQFAIL", r.url, flush=True)))
    p.on("dialog", lambda d: (print("DIALOG", d.type, d.message[:100], flush=True), d.accept()))

    def mock_empty_history(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"items": []}))

    try:
        # ========== 段 1：S2026001 /learn 破损态 ==========
        do_login(p, "S2026001")
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        log("learn_s2026001", broken=p.locator(".chat-wrap").count() == 0,
            body_text_len=p.evaluate("document.body.innerText.length"),
            note="有 1 条学习历史即渲染失败：全页空白（仅顶栏），学习中心不可用")
        p.screenshot(path=os.path.join(OUT, "learn_broken.png"))

        # ========== 段 2：S2026002，拦截 history 置空 ==========
        do_logout(p)
        do_login(p, "S2026002")
        p.route("**/api/learn/history", mock_empty_history)
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        rendered = p.locator(".chat-wrap").count() > 0
        p.screenshot(path=os.path.join(OUT, "learn.png"))
        log("learn_s2026002_mock_empty", rendered=rendered, chat_msgs=p.evaluate("document.querySelectorAll('.chat-flow .msg').length"),
            note="拦截 history 为空后页面正常渲染 → 证实破损仅由 .map() 缺陷触发")
        p.screenshot(path=os.path.join(OUT, "learn_empty.png"))
        log("learn_empty_state", chat_msgs=p.evaluate("document.querySelectorAll('.chat-flow .msg').length"),
            note="聊天区全空：无欢迎语/示例问题/引导，新用户无起点（placeholder 仅提示一句示例问法）")

        # 发送按钮禁用态
        send_btn = p.locator(".chat-input .btn")
        log("send_btn_disabled_when_empty", disabled=send_btn.is_disabled())

        # 知识地图
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
            log("knowledge_map", total=total, filter_env=one, filter_all=back, only_weak=weak,
                note="新学生掌握度全 0：『仅看薄弱(<60)』过滤后仍 6 卡（可用，但无『全部薄弱』提示）")
        except Exception as e:
            log("error", what="kmap", err=str(e)[:200])

        # 簇抽屉
        try:
            p.locator(".kcard").nth(1).click()
            p.wait_for_timeout(500)
            drawer = p.locator(".card:has-text('岗课赛证详解')")
            log("cluster_drawer", opened=drawer.count() == 1,
                text=drawer.inner_text().replace("\n", " | ")[:160] if drawer.count() else "")
            p.screenshot(path=os.path.join(OUT, "learn_drawer.png"))
            drawer.locator("button:has-text('帮我讲这一簇')").click()
            p.wait_for_timeout(500)
            val = p.locator(".chat-input textarea").input_value()
            log("drawer_btn", input_filled=val, drawer_closed=p.locator(".card:has-text('岗课赛证详解')").count() == 0,
                note="『帮我讲这一簇』只把『X 要点』填入输入框、不自动发送，用户须再点发送（两步操作，易漏）")
            p.locator(".chat-input textarea").fill("")
        except Exception as e:
            log("error", what="drawer", err=str(e)[:200])

        # ========== 段 3：真实提问闭环（唯一 1 次） ==========
        t0 = time.time()
        n0 = p.evaluate("document.body.innerText.split('【岗】').length - 1")
        p.locator(".chat-input textarea").fill("什么是跌倒")
        p.screenshot(path=os.path.join(OUT, "learn_ask_input.png"))
        p.locator(".chat-input .btn", has_text="发送").click()
        log("ask_sent", question="什么是跌倒", account="S2026002")
        got_q = wait_until(p, "!!document.querySelector('.qcard')", 150000)
        t_q = int(time.time() - t0)
        if got_q:
            qt = p.locator(".qcard .qt").inner_text()
            nopts = p.locator(".qcard .qopt").count()
            p.screenshot(path=os.path.join(OUT, "learn_clarify.png"))
            log("clarify", waited_s=t_q, text=qt[:200], options=nopts)
            p.locator(".qcard .qopt").first.click()
            log("clarify_picked", option="第 1 项")
        else:
            log("clarify", waited_s=t_q, appeared=False)
        done = wait_until(p, "document.body.innerText.split('【岗】').length - 1 > " + str(n0), 240000)
        t_done = int(time.time() - t0)
        if done:
            p.wait_for_timeout(800)
            p.screenshot(path=os.path.join(OUT, "learn_answer.png"))
            cols_n = p.evaluate("document.querySelectorAll('.msg.ai .col').length")
            src = p.evaluate("""() => { const s=[...document.querySelectorAll('.msg.ai .src')]; return s.length ? s[s.length-1].innerText : '' }""")
            log("answer_done", total_s=t_done, clarify_wait_s=t_q, four_cols_rendered=cols_n, source_line=src[:200],
                note="真实回答按【岗】【课】【赛】【证】四栏渲染，附来源标注")
        else:
            log("answer_done", total_s=t_done, appeared=False, note="240s 未等到含【岗】的回答")

        # ========== 段 4：移除拦截，刷新复现破损 ==========
        p.unroute("**/api/learn/history")
        p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(3000)
        broken2 = p.locator(".chat-wrap").count() == 0
        p.screenshot(path=os.path.join(OUT, "learn_after_reload.png"))
        log("learn_after_reload", broken=broken2,
            note="提问完成后刷新：学习历史非空 → 页面再次渲染失败，刚问完的答案也看不到")

        log("console_summary", count=len(console_msgs),
            msgs=json.dumps(list(dict.fromkeys(console_msgs))[:10], ensure_ascii=False)[:900])
        log("reqfail_summary", count=len(reqfails), msgs=json.dumps(reqfails[:10], ensure_ascii=False)[:400])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-600:])
    finally:
        b.close()
print("DONE learn2", flush=True)