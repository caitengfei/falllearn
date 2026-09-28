# -*- coding: utf-8 -*-
"""UX 交互体验测试 3/3：练习考试→答题→交卷→成绩报告；错题本重答弹窗；我的页；教师 /admin（只看不重置）"""
import sys, os, json, time, re
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_practice_log.jsonl")
console_msgs = []
reqfails = []
dialogs = []

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

def wait_until(p, expr, timeout_ms=30000, interval=400):
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

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text.split("\n")[0]), print("CONSOLE", m.type, m.text[:200].replace("\n", " "), flush=True)) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: (reqfails.append(r.url), print("REQFAIL", r.url, flush=True)))
    p.on("dialog", lambda d: (dialogs.append(d.type + " " + d.message), print("DIALOG", d.type, d.message[:120], flush=True), d.accept()))

    try:
        do_login(p, "S2026001")

        # ========== 练习考试页 ==========
        p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(1200)
        p.screenshot(path=os.path.join(OUT, "practice.png"))
        for m in ["日常练习", "12分钟模拟考", "教师布置", "错题重练"]:
            try:
                p.locator(".menu-item", has_text=m).first.click()
                p.wait_for_timeout(500)
                cards = p.locator(".page .card").all()
                # 任务卡 = 含 .rthumb 的卡
                task_cards = [c for c in cards if c.locator(".rthumb").count()]
                empty = p.locator(".card.empty").count()
                log("practice_menu", menu=m, tasks=len(task_cards), empty_state=empty > 0)
            except Exception as e:
                log("error", what="menu_" + m, err=str(e)[:150])
        # pills
        for pill in ["全部", "未开始", "进行中", "已完成"]:
            try:
                p.locator(".menu-item", has_text="日常练习").first.click()
                p.wait_for_timeout(300)
                p.locator(".pill", has_text=pill).first.click()
                p.wait_for_timeout(400)
                task_cards = [c for c in p.locator(".page .card").all() if c.locator(".rthumb").count()]
                log("practice_pill", pill=pill, tasks=len(task_cards))
            except Exception as e:
                log("error", what="pill_" + pill, err=str(e)[:150])
        p.locator(".pill", has_text="全部").first.click()

        # 模拟考『开始』→ 实际开出什么卷
        try:
            p.locator(".menu-item", has_text="12分钟模拟考").first.click()
            p.wait_for_timeout(400)
            p.locator(".card", has_text="模拟考 · 跌倒风险评估").locator("button:has-text('开始')").click()
            wait_until(p, "location.pathname.indexOf('/exam/') === 0", 15000)
            p.wait_for_timeout(1200)
            header = p.locator(".card").first.inner_text().replace("\n", " | ")[:160]
            log("mock_start", url=p.evaluate("location.pathname"), header=header,
                note="标称『12 分钟·100 分·对标竞赛』的模拟考，实际开出的卷面标题与题目形态")
            p.screenshot(path=os.path.join(OUT, "exam_mock_header.png"))
        except Exception as e:
            log("error", what="mock_start", err=str(e)[:200])

        # ========== 日常练习：开卷 → 答 2 题 → 返回 ==========
        p.goto(BASE + "/practice", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_selector(".card:has-text('今日练习')", timeout=20000)
        p.locator(".card:has-text('今日练习')").locator("button:has-text('开始')").click()
        ok = wait_until(p, "location.pathname.indexOf('/exam/') === 0", 15000)
        p.wait_for_selector(".opt", timeout=15000)
        total_txt = p.evaluate("document.body.innerText.match(/第 \\d+ \\/ (\\d+) 题/)?.[1] || '?'")
        p.screenshot(path=os.path.join(OUT, "exam.png"))
        log("exam_started", url=p.evaluate("location.pathname"), total_questions=total_txt)

        # 第 1 题作答
        p.locator(".opt").first.click()
        p.wait_for_timeout(300)
        ans1 = p.evaluate("document.body.innerText.match(/已答 (\\d+)/)?.[1]")
        on1 = p.locator(".opt.on").count()
        log("answer_q1", answered=ans1, highlighted_options=on1)
        # 下一题
        p.locator("button:has-text('下一题')").click()
        p.wait_for_timeout(300)
        p.locator(".opt").nth(1).click()
        p.wait_for_timeout(300)
        ans2 = p.evaluate("document.body.innerText.match(/已答 (\\d+)/)?.[1]")
        log("answer_q2", answered=ans2)
        # 返回上一题验证回退
        p.locator("button:has-text('上一题')").click()
        p.wait_for_timeout(300)
        q1_on = p.locator(".opt.on").count()
        log("back_to_q1", q1_highlighted=q1_on, note="回到第 1 题，之前选择是否保留")
        p.screenshot(path=os.path.join(OUT, "exam_ans2.png"))

        # 返回练习页（本卷保持 open）
        p.locator(".navtabs a", has_text="练习考试").click()
        p.wait_for_timeout(800)
        log("return_to_practice")

        # ========== 再开一卷 → 交卷（带未答确认） ==========
        p.locator(".card:has-text('今日练习')").locator("button:has-text('开始')").click()
        wait_until(p, "location.pathname.indexOf('/exam/') === 0", 15000)
        p.wait_for_selector(".opt", timeout=15000)
        # 跳到最后一题
        for _ in range(9):
            nxt = p.locator("button:has-text('下一题')")
            if nxt.count() == 0:
                break
            nxt.first.click()
            p.wait_for_timeout(250)
        pos = p.evaluate("document.body.innerText.match(/第 (\\d+) \\/ \\d+ 题/)?.[1] || '?'")
        log("jump_to_last", position=pos)
        submit_btn = p.locator("button", has_text=re.compile(r"交\s*卷"))
        log("submit_btn", visible=submit_btn.count() > 0, disabled=submit_btn.is_disabled() if submit_btn.count() else None)
        submit_btn.click()
        # confirm 弹窗自动 accept
        p.wait_for_timeout(500)
        ok = wait_until(p, "!!document.querySelector('.score-ring')", 60000)
        p.wait_for_timeout(800)
        p.screenshot(path=os.path.join(OUT, "exam_result.png"))
        if ok:
            score = p.locator(".score-ring .sv").inner_text().strip()
            correct = p.evaluate("document.body.innerText.match(/答对 (\\d+) \\/ \\d+ 题/)?.[0] || '?'")
            detail_cards = p.evaluate("document.querySelectorAll('.page .card').length")
            log("exam_result", score=score, correct=correct, detail_cards=detail_cards,
                confirm_dialog=any("交卷" in d for d in dialogs),
                note="交卷后成绩报告：分数环 + 逐题解析（正确答案/你的选择/反馈/来源）")
            # 报告页两个按钮
            p.locator("button:has-text('再练一组薄弱题')").click()
            wait_until(p, "location.pathname === '/practice'", 10000)
            log("report_btn_1", btn="再练一组薄弱题", dest=p.evaluate("location.pathname"),
                note="跳转 /practice 但不自动开卷、不带薄弱簇上下文，需用户自己再点开始")
            p.screenshot(path=os.path.join(OUT, "practice_after_report.png"))
        else:
            log("exam_result", appeared=False, note="60s 未出现成绩环")

        # ========== 错题本 ==========
        p.locator(".navtabs a", has_text="错题本").click()
        p.wait_for_timeout(150)
        p.screenshot(path=os.path.join(OUT, "wrong_flash.png"))  # 尝试抓空态闪烁
        p.wait_for_selector(".row-item, .empty", timeout=15000)
        p.wait_for_timeout(400)
        p.screenshot(path=os.path.join(OUT, "wrong.png"))
        pill_txts = [p.locator(".pill").nth(i).inner_text().strip() for i in range(p.locator(".pill").count())]
        n_items = p.locator(".row-item").count()
        banner = p.locator(".card div", has_text="复习到期").count()
        log("wrong_page", pills=pill_txts, active_items=n_items, due_banner=bool(banner),
            note="S2026001 有 6 条待复习错题、0 条今日到期（到期横幅不显示）")

        # 重答弹窗 → 关闭
        try:
            p.locator(".row-item").first.locator("button:has-text('重答')").click()
            p.wait_for_selector(".modal-mask", timeout=10000)
            p.wait_for_timeout(400)
            p.screenshot(path=os.path.join(OUT, "wrong_modal.png"))
            modal_title = p.locator(".modal-mask .card-title").inner_text().replace("\n", " | ")[:100]
            sub_disabled = p.locator(".modal-mask button", has_text="提交").is_disabled()
            log("wrong_modal", title=modal_title, submit_disabled_when_no_answer=sub_disabled,
                opts=p.locator(".modal-mask .opt").count())
            p.locator(".modal-mask .more", has_text="关闭").click()
            p.wait_for_timeout(400)
            closed = p.locator(".modal-mask").count() == 0
            items_after = p.locator(".row-item").count()
            log("wrong_modal_closed", closed=closed, items_intact=items_after == n_items)
        except Exception as e:
            log("error", what="wrong_modal", err=str(e)[:200])

        # 讲解按钮 + 点遮罩关闭
        try:
            p.locator(".row-item").nth(1).locator("button:has-text('讲解')").click()
            p.wait_for_selector(".modal-mask", timeout=10000)
            p.mouse.click(30, 900)
            p.wait_for_timeout(400)
            log("wrong_modal_mask_close", closed=p.locator(".modal-mask").count() == 0)
        except Exception as e:
            log("error", what="wrong_mask", err=str(e)[:200])

        # 已掌握 tab
        try:
            p.locator(".pill", has_text="已掌握").click()
            p.wait_for_selector(".row-item, .empty", timeout=10000)
            p.wait_for_timeout(400)
            log("wrong_mastered_tab", items=p.locator(".row-item").count(),
                empty_txt=p.locator(".empty").inner_text().strip() if p.locator(".empty").count() else "(有列表)")
        except Exception as e:
            log("error", what="wrong_mastered", err=str(e)[:200])

        # ========== 我的 ==========
        p.locator(".navtabs a", has_text="我的").click()
        p.wait_for_selector(".radar-box, .card", timeout=15000)
        p.wait_for_timeout(800)
        p.screenshot(path=os.path.join(OUT, "mine.png"))
        radar_labels = p.evaluate("[...document.querySelectorAll('.radar-box text')].map(t => t.textContent).join(' | ')")
        earned = p.evaluate("""() => { const c=[...document.querySelectorAll('.card')].find(x=>x.textContent.includes('勋章墙')); if(!c) return ''; const flex=[...c.children].find(d=>d.tagName==='DIV' && d.children.length>0 && !d.className.includes('card-title')); return flex ? [...flex.children].map(x=>x.textContent.replace(/\\s+/g,' ')).join(' | ') : '' }""")
        points_rows = p.evaluate("""() => { const c=[...document.querySelectorAll('.card')].find(x=>x.textContent.includes('积分明细')); return c ? [...c.querySelectorAll('.row-item')].slice(0,3).map(r=>r.innerText.replace(/\\n/g,' ')) : [] }""")
        log("mine_page", radar=radar_labels, earned_badges=earned[:300], points_log_head=points_rows,
            note="我的页 = 雷达+勋章墙+概览+积分明细，无 tab；『学习日历/学习榜单/我的报告』三个首页入口落在此页但均无对应内容")

        # ========== 教师 /admin（只看不重置） ==========
        p.locator(".topbar .btn", has_text="退出").click()
        p.wait_for_selector(".login-card", timeout=15000)
        p.locator(".field input").nth(0).fill("T2026")
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        p.wait_for_selector(".navtabs", timeout=20000)
        p.wait_for_timeout(600)
        admin_link = p.locator(".navtabs a", has_text="管理看板")
        log("teacher_nav", admin_link_visible=admin_link.count() > 0)
        admin_link.click()
        p.wait_for_selector("table tbody tr", timeout=15000)
        p.wait_for_timeout(600)
        p.screenshot(path=os.path.join(OUT, "admin.png"))
        rows = p.locator("table tbody tr").count()
        row1 = p.locator("table tbody tr").first.inner_text().replace("\n", " | ")[:150] if rows else ""
        weak = p.evaluate("""() => { const c=[...document.querySelectorAll('.card')].find(x=>x.textContent.includes('班级弱项')); return c ? c.innerText.slice(0,300).replace(/\\n+/g,' | ') : '' }""")
        reset_btn = p.locator("button", has_text="一键重置演示账号")
        log("admin_page", student_rows=rows, first_row=row1, weak_clusters=weak[:280],
            reset_btn_present=reset_btn.count() > 0,
            note="管理看板可正常加载；『一键重置演示账号』按钮存在但按测试纪律未点击")

        log("console_summary", count=len(console_msgs),
            msgs=json.dumps(list(dict.fromkeys(console_msgs))[:10], ensure_ascii=False)[:900])
        log("reqfail_summary", count=len(reqfails), msgs=json.dumps(reqfails[:10], ensure_ascii=False)[:400])
        log("dialogs_summary", dialogs=json.dumps(dialogs[:10], ensure_ascii=False)[:400])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-600:])
    finally:
        b.close()
print("DONE practice", flush=True)