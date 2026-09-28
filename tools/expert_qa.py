# -*- coding: utf-8 -*-
"""FallLearn 功能测试(QA) — 只读测试。
禁止项遵守: 不修改项目文件、不调 POST /api/admin/reset-demo、不跑 build。
S2026002 交卷产生真实数据(任务允许)。"""
import sys, os, re, json, time
sys.stdout.reconfigure(encoding="utf-8")

import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\docs\expert-test\qa"
os.makedirs(OUT, exist_ok=True)

R = {}
CONSOLE = []
HTTP = []
DIALOGS = []

def log(msg):
    print(msg, flush=True)

def shot(page, name):
    try:
        page.screenshot(path=os.path.join(OUT, name))
        log(f"  [shot] {name}")
    except Exception as e:
        log(f"  [shot FAIL] {name}: {e}")

def wait_path(page, path, timeout=20):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            last = page.evaluate("location.pathname")
        except Exception:
            last = None
        if last == path:
            return last
        time.sleep(0.2)
    return last

def wait_path_starts(page, prefix, timeout=20):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            last = page.evaluate("location.pathname")
        except Exception:
            last = None
        if last and last.startswith(prefix):
            return last
        time.sleep(0.2)
    return last

def wait_text(page, selector, timeout=20):
    try:
        page.wait_for_selector(selector, timeout=timeout * 1000, state="visible")
        return True
    except Exception:
        return False

def attach(p, label):
    def on_console(m):
        if m.type in ("error", "warning"):
            CONSOLE.append([label, m.type, m.text[:300]])
            if m.type == "error":
                log(f"CONSOLE[{label}] {m.type}: {m.text[:220]}")
    def on_resp(r):
        if r.status >= 400:
            HTTP.append([label, r.status, r.url])
            log(f"HTTP[{label}] {r.status} {r.url}")
    def on_reqfail(r):
        HTTP.append([label, 0, r.url + " | " + str(r.failure)])
        log(f"REQFAIL[{label}] {r.url} {r.failure}")
    def on_dialog(d):
        DIALOGS.append([label, d.message])
        log(f"DIALOG[{label}] {d.message[:150]}")
        d.accept()
    p.on("console", on_console)
    p.on("response", on_resp)
    p.on("requestfailed", on_reqfail)
    p.on("dialog", on_dialog)

def login(p, sno, pwd="123456"):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill(pwd)
    p.locator(".login-body .btn").click()
    cur = wait_path(p, "/", 25)
    ok = wait_text(p, ".stu-card", 20)
    log(f"  login {sno}: path={cur} home_card={ok}")
    return ok

def answered_count(p):
    try:
        txt = p.evaluate("document.querySelector('.page') ? document.querySelector('.page').innerText : ''")
    except Exception:
        return (None, None)
    m = re.search(r"已答\s*(\d+)\s*/\s*(\d+)", txt)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def api_login(s, sno):
    r = s.post(BASE + "/api/auth/login", json={"student_no": sno, "password": "123456"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]

# ================= API 阶段 =================
def api_phase():
    s = requests.Session()
    log("== API 阶段 ==")
    r = s.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "111111"}, timeout=15)
    R["A1_wrong_pwd"] = {"status": r.status_code, "body": r.text[:200]}
    r = s.post(BASE + "/api/auth/login", json={"student_no": "S999999", "password": "123456"}, timeout=15)
    R["A2_unknown_sno"] = {"status": r.status_code, "body": r.text[:200]}
    r = s.post(BASE + "/api/auth/login", json={"student_no": "", "password": ""}, timeout=15)
    R["A3_empty_login"] = {"status": r.status_code, "body": r.text[:200]}
    r = s.get(BASE + "/api/auth/me", timeout=15)
    R["A4a_me_no_token"] = {"status": r.status_code, "body": r.text[:200]}
    r = s.get(BASE + "/api/auth/me", headers={"Authorization": "Bearer garbagetoken123"}, timeout=15)
    R["A4b_me_bad_token"] = {"status": r.status_code, "body": r.text[:200]}
    r = s.get(BASE + "/api/quiz/weak", timeout=15)
    R["A4c_weak_no_token"] = {"status": r.status_code}
    r = s.get(BASE + "/api/wrong", timeout=15)
    R["A4d_wrong_no_token"] = {"status": r.status_code}

    t1 = api_login(s, "S2026001")
    t2 = api_login(s, "S2026002")
    t3 = api_login(s, "S2026003")
    tT = api_login(s, "T2026")
    h1, h2, h3, hT = ({"Authorization": f"Bearer {t}"} for t in (t1, t2, t3, tT))

    R["A5_s002_me"] = s.get(BASE + "/api/auth/me", headers=h2, timeout=15).json()
    R["A5_s002_weak"] = s.get(BASE + "/api/quiz/weak", headers=h2, timeout=15).json()
    R["A5_s002_wrong_before"] = s.get(BASE + "/api/wrong?status=active", headers=h2, timeout=15).json()
    R["A5_s002_points_before"] = s.get(BASE + "/api/game/points", headers=h2, timeout=15).json()
    R["A5_s002_badges_before"] = s.get(BASE + "/api/game/badges", headers=h2, timeout=15).json()
    R["A5_s002_leaderboard_before"] = s.get(BASE + "/api/game/leaderboard", headers=h2, timeout=15).json()
    R["A5_s002_today_before"] = s.get(BASE + "/api/game/today", headers=h2, timeout=15).json()

    R["A6_s001_me"] = s.get(BASE + "/api/auth/me", headers=h1, timeout=15).json()
    R["A6_s001_weak"] = s.get(BASE + "/api/quiz/weak", headers=h1, timeout=15).json()
    R["A6_s001_points"] = s.get(BASE + "/api/game/points", headers=h1, timeout=15).json()
    R["A6_s001_badges"] = s.get(BASE + "/api/game/badges", headers=h1, timeout=15).json()
    R["A6_s001_wrong"] = s.get(BASE + "/api/wrong?status=active", headers=h1, timeout=15).json()
    R["A6_s001_learn_history"] = s.get(BASE + "/api/learn/history", headers=h1, timeout=15).json()

    # 组卷边界: 空白学生(无掌握度)
    r = s.post(BASE + "/api/quiz/start", headers=h2, timeout=30)
    st1 = r.json()
    items = st1.get("items", [])
    VALID_T = {"单选", "多选", "判断"}
    VALID_C = {"morse", "env", "five", "fracture", "record", "cpr", "general"}
    probs = []
    if st1.get("count") != 10 or len(items) != 10:
        probs.append(f"count={st1.get('count')} len={len(items)}")
    for i, it in enumerate(items):
        if it.get("seq") != i + 1:
            probs.append(f"seq 错乱 #{i}: {it.get('seq')}")
        if not it.get("stem", "").strip():
            probs.append(f"第{i+1}题题干为空")
        if it.get("type") not in VALID_T:
            probs.append(f"第{i+1}题题型异常: {it.get('type')}")
        if it.get("cluster") not in VALID_C:
            probs.append(f"第{i+1}题簇异常: {it.get('cluster')}")
        opts = it.get("options") or []
        if it.get("type") in ("单选", "多选") and not (2 <= len(opts) <= 4):
            probs.append(f"第{i+1}题选项数异常: {len(opts)}")
        if it.get("type") == "多选" and len(opts) < 2:
            probs.append(f"第{i+1}题多选选项不足")
    R["A7a_start_blank_student"] = {
        "status": r.status_code, "attempt_id": st1.get("attempt_id"),
        "count": st1.get("count"), "problem": probs,
        "types": [it["type"] for it in items],
        "clusters": [it["cluster"] for it in items],
        "first_stem": items[0]["stem"][:60] if items else None,
        "sample_opts": (items[0].get("options") or [])[:4] if items else None,
    }
    r = s.post(BASE + "/api/quiz/start", headers=h2, timeout=30)
    st2 = r.json()
    R["A7b_start_second"] = {"status": r.status_code, "attempt_id": st2.get("attempt_id"),
                             "same_attempt_as_first": st2.get("attempt_id") == st1.get("attempt_id")}

    # 跨用户交卷
    r = s.post(BASE + "/api/quiz/submit", headers=h3,
               json={"attempt_id": st1["attempt_id"], "answers": {}}, timeout=20)
    R["A7c_submit_cross_user"] = {"status": r.status_code, "body": r.text[:150]}
    # 本人交卷(空答案)
    r = s.post(BASE + "/api/quiz/submit", headers=h2,
               json={"attempt_id": st1["attempt_id"], "answers": {}}, timeout=30)
    R["A7d_submit_empty"] = {"status": r.status_code,
                             "score": r.json().get("score") if r.status_code == 200 else None,
                             "correct_n": (sum(1 for d in r.json().get("detail", []) if d.get("correct"))
                                           if r.status_code == 200 else None)}
    # 重复交卷
    r = s.post(BASE + "/api/quiz/submit", headers=h2,
               json={"attempt_id": st1["attempt_id"], "answers": {}}, timeout=20)
    R["A7e_submit_twice"] = {"status": r.status_code, "body": r.text[:150]}
    # 不存在 attempt
    r = s.post(BASE + "/api/quiz/submit", headers=h2,
               json={"attempt_id": 99999999, "answers": {}}, timeout=20)
    R["A7f_submit_unknown"] = {"status": r.status_code, "body": r.text[:150]}

    r = s.get(BASE + "/api/nope", timeout=15)
    R["A8a_api_404"] = {"status": r.status_code, "body": r.text[:150]}
    r = s.get(BASE + "/xyz", timeout=15)
    R["A8b_spa_fallback"] = {"status": r.status_code, "is_html": "html" in r.headers.get("content-type", "")}

    r = s.get(BASE + "/api/admin/dashboard", headers=h2, timeout=15)
    R["A9a_admin_as_student"] = {"status": r.status_code, "body": r.text[:150]}
    r = s.get(BASE + "/api/admin/dashboard", headers=hT, timeout=15)
    dash = r.json() if r.status_code == 200 else {}
    R["A9b_admin_as_teacher"] = {"status": r.status_code,
                                 "students": [(x["student_no"], x["points"], x["last_score"], x["active_wrong"])
                                              for x in dash.get("students", [])],
                                 "weak_clusters": dash.get("weak_clusters", [])[:3]}
    R["_tokens"] = {"S2026001": t1, "S2026002": t2, "S2026003": t3, "T2026": tT}
    R["_attempt_st2_orphan"] = st2.get("attempt_id")
    log(f"  A7a: {json.dumps(R['A7a_start_blank_student'], ensure_ascii=False)[:400]}")
    log(f"  A7d empty-submit: {R['A7d_submit_empty']}")

# ================= UI 阶段 =================
def ui_phase(b):
    log("== UI 阶段: S2026002 空白学生 ==")
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    attach(p, "S2026002")

    login(p, "S2026002")
    time.sleep(1.2)
    home_text = p.evaluate("document.querySelector('.stu-card') ? document.querySelector('.stu-card').innerText : ''")
    R["B1_home_blank"] = {"card_text": home_text}
    shot(p, "01_home_blank.png")

    # 签到
    try:
        p.locator(".checkin-row .btn-sm").click()
        time.sleep(1.5)
        R["B1b_checkin"] = {"row": p.locator(".checkin-row").inner_text()}
        shot(p, "02_home_checkin.png")
    except Exception as e:
        R["B1b_checkin"] = {"error": str(e)}

    # 错题本空态
    p.goto(BASE + "/wrong", wait_until="domcontentloaded"); time.sleep(1.5)
    R["B2_wrong_empty"] = {"text": p.locator(".page").inner_text()[:300]}
    shot(p, "03_wrong_empty.png")

    # 我的空态
    p.goto(BASE + "/mine", wait_until="domcontentloaded"); time.sleep(1.5)
    R["B3_mine_empty"] = {"stats": p.evaluate("document.querySelector('.stu-stats') ? document.querySelector('.stu-stats').innerText : ''"),
                          "points_log_empty": "暂无积分记录" in (p.locator(".page").inner_text())}
    shot(p, "04_mine_empty.png")

    # 学习中心空历史
    p.goto(BASE + "/learn", wait_until="domcontentloaded"); time.sleep(1.5)
    R["B4_learn_empty"] = {"msg_count": p.evaluate("document.querySelectorAll('.chat-flow .msg').length")}
    shot(p, "05_learn_empty.png")

    # 练习页
    p.goto(BASE + "/practice", wait_until="domcontentloaded"); time.sleep(1.5)
    shot(p, "06_practice.png")
    # 开始日常练习(如本卷无多选题则重开 1-2 次找多选题, 上限 3 次)
    exam_info = None
    for attempt_round in range(3):
        try:
            p.locator(".card button", has_text="开始").first.click(timeout=5000)
        except Exception as e:
            log(f"  点击开始失败: {e}")
            break
        cur = wait_path_starts(p, "/exam/", 30)
        time.sleep(1.0)
        items = p.evaluate("JSON.parse(sessionStorage.getItem('exam_items')||'[]')")
        exam_id = p.evaluate("sessionStorage.getItem('exam_attempt')")
        types = [it.get("type") for it in items]
        log(f"  开卷 #{attempt_round+1}: path={cur} attempt={exam_id} types={types}")
        if cur and "多选" in types:
            exam_info = {"items": items, "exam_id": exam_id, "types": types}
            break
        if cur and attempt_round == 2:
            exam_info = {"items": items, "exam_id": exam_id, "types": types}
            break
        p.goto(BASE + "/practice", wait_until="domcontentloaded"); time.sleep(1.2)
    if not exam_info:
        R["B5_exam"] = {"error": "开卷失败"}
        return
    shot(p, "07_exam_q1.png")

    # 多选题高亮验证
    multi_idx = next((i for i, it in enumerate(exam_info["items"]) if it.get("type") == "多选"), None)
    if multi_idx is not None:
        for _ in range(multi_idx):
            p.locator("button", has_text="下一题").click(); p.wait_for_timeout(150)
        q_no = p.evaluate("document.querySelector('.page').innerText.match(/第 (\\d+) \\/ (\\d+) 题/)?.[0] || ''")
        p.locator(".opt").nth(0).click(); p.wait_for_timeout(120)
        p.locator(".opt").nth(1).click(); p.wait_for_timeout(120)
        classes = p.evaluate("Array.from(document.querySelectorAll('.opt')).map(o => o.className)")
        on_after = [c for c in classes if " on" in (" " + c + " ")]
        a, t = answered_count(p)
        R["B5b_multi_highlight"] = {
            "q": q_no, "opt_classes": classes, "highlighted_count": len(on_after),
            "answered": [a, t],
            "note": "多选: 点击 2 个选项后 .opt 是否有 .on 高亮",
        }
        shot(p, "08_exam_multi_highlight.png")
        # 回到第 1 题
        for _ in range(multi_idx):
            p.locator("button", has_text="上一题").click(); p.wait_for_timeout(120)
    else:
        R["B5b_multi_highlight"] = {"note": "本次组卷无多选题, 未验证"}

    # 答 2 题后刷新(同 tab): 检查答案是否丢失
    p.locator(".opt").first.click(); p.wait_for_timeout(120)
    p.locator("button", has_text="下一题").click(); p.wait_for_timeout(150)
    p.locator(".opt").first.click(); p.wait_for_timeout(120)
    before_reload = answered_count(p)
    p.reload(wait_until="domcontentloaded")
    wait_text(p, ".opt", 20)
    after_reload = answered_count(p)
    R["B6_reload_mid_exam"] = {"before_reload": list(before_reload), "after_reload": list(after_reload),
                               "url": p.evaluate("location.href")}
    shot(p, "09_exam_after_reload.png")

    # 新 tab 直接访问 /exam/<id> (sessionStorage 失效)
    p2 = b.new_page()
    attach(p2, "S2026002-newtab")
    p2.goto(BASE + "/exam/" + exam_info["exam_id"], wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    body2 = p2.evaluate("document.body ? document.body.innerText : ''")
    R["B7_newtab_direct_exam"] = {
        "url": p2.evaluate("location.href"),
        "has_loading_text": "题目加载中" in body2,
        "has_question": "第 1 / 10 题" in body2,
        "body_head": body2[:260],
    }
    shot(p2, "10_exam_newtab_direct.png")
    p2.close()

    # 交卷(全部未答 → 确认框 → 提交)
    a, t = answered_count(p)
    for _ in range((t or 10) - 1):
        try:
            p.locator("button", has_text="下一题").click(); p.wait_for_timeout(120)
        except Exception:
            break
    time.sleep(0.5)
    d_before = len(DIALOGS)
    p.locator("button", has_text=re.compile(r"交\s*卷")).click()
    wait_text(p, "text=成绩报告", 40)
    report = p.locator(".page").inner_text()
    m_score = re.search(r"(\d+)\s*/\s*100 分", report)
    m_ok = re.search(r"答对\s*(\d+)\s*/\s*(\d+)\s*题", report)
    R["B8_submit_all_blank"] = {
        "confirm_dialog": DIALOGS[d_before:],
        "score": m_score.group(1) if m_score else None,
        "correct": list(m_ok.groups()) if m_ok else None,
        "report_head": report[:300],
    }
    shot(p, "11_exam_report.png")

    # 交卷后 API 校验(错题本数量/积分)
    s = requests.Session()
    t2 = R["_tokens"]["S2026002"]
    h2 = {"Authorization": f"Bearer {t2}"}
    items_types = exam_info["types"]
    non_general = sum(1 for it in exam_info["items"] if it.get("cluster") != "general")
    wrong_after = s.get(BASE + "/api/wrong?status=active", headers=h2, timeout=15).json()
    pts_after = s.get(BASE + "/api/game/points", headers=h2, timeout=15).json()
    me_after = s.get(BASE + "/api/auth/me", headers=h2, timeout=15).json()
    R["D1_after_submit"] = {
        "expected_wrong_new": non_general,
        "wrong_count_now": len(wrong_after.get("items", [])),
        "points_total_now": pts_after.get("total"),
        "points_log_last3": pts_after.get("log", [])[:3],
        "me_mastery": me_after.get("mastery"),
    }

    # 错题本: 重答 2 题(选对) → 验证 1 次答对即掌握(与 UI 宣称"连对 2 次"矛盾) + 积分 +10/题
    p.goto(BASE + "/wrong", wait_until="domcontentloaded"); time.sleep(1.5)
    wait_text(p, ".row-item", 20)
    shot(p, "12_wrong_filled.png")
    wl = s.get(BASE + "/api/wrong?status=active", headers=h2, timeout=15).json()
    pick = [x for x in wl.get("items", []) if x.get("type") != "多选"][:2]
    review_results = []
    for item in pick:
        row = p.locator(".row-item", has_text=item["stem"][:10])
        if row.count() == 0:
            review_results.append({"stem": item["stem"][:20], "error": "未找到对应行"})
            continue
        row.first.locator("button", has_text="重答").click()
        wait_text(p, ".modal-mask .opt", 10)
        letter = item["answer"].strip().upper()
        li = min(ord(letter) - ord("A"), 3)
        p.locator(".modal-mask .opt").nth(li).click()
        p.locator(".modal-mask button", has_text="提交").click()
        wait_text(p, "text=作答结果", 15)
        mtxt = p.locator(".modal-mask").inner_text()
        review_results.append({
            "stem": item["stem"][:24], "letter": letter,
            "mastered_text": "已标记掌握" in mtxt, "still_wrong": "还是错了" in mtxt,
            "text": mtxt[:200],
        })
        shot(p, "13_wrong_review_result.png")
        try:
            p.locator(".modal-mask span.more", has_text="关闭").click()
            p.wait_for_timeout(400)
        except Exception:
            pass
    R["D2_wrong_review"] = review_results

    pts2 = s.get(BASE + "/api/game/points", headers=h2, timeout=15).json()
    wrong2 = s.get(BASE + "/api/wrong?status=active", headers=h2, timeout=15).json()
    R["D3_after_review"] = {
        "points_total": pts2.get("total"),
        "points_log_last4": pts2.get("log", [])[:4],
        "wrong_active_now": len(wrong2.get("items", [])),
    }
    p.goto(BASE + "/mine", wait_until="domcontentloaded"); time.sleep(1.5)
    R["B9_mine_after"] = {"stats": p.evaluate("document.querySelector('.stu-stats') ? document.querySelector('.stu-stats').innerText : ''")}
    shot(p, "14_mine_after.png")

    # ---- 异常流 ----
    p.goto(BASE + "/admin", wait_until="domcontentloaded"); time.sleep(2)
    err_count = p.locator(".err").count()
    R["C1_admin_as_student"] = {
        "url": p.evaluate("location.href"),
        "err_card": p.locator(".err").first.inner_text() if err_count else None,
        "reset_btn_visible": p.locator("button", has_text="一键重置演示账号").count() > 0,
        "page_head": p.locator(".page").inner_text()[:200],
    }
    shot(p, "15_admin_as_student.png")

    p.goto(BASE + "/login", wait_until="domcontentloaded")
    cur = wait_path(p, "/", 15)
    R["C2_login_when_loggedin"] = {"final_path": cur, "redirected_home": cur == "/"}

    p.goto(BASE + "/xyz", wait_until="domcontentloaded")
    cur = wait_path(p, "/", 15)
    R["C3_unknown_route"] = {"final_path": cur, "redirected_home": cur == "/"}

    # ---- AI 学习闭环(唯一一次真实提问) ----
    p.goto(BASE + "/learn", wait_until="domcontentloaded")
    p.wait_for_selector("textarea", timeout=20000)
    p.locator("textarea").fill("什么是跌倒")
    p.locator("button", has_text="发送").click()
    got_q = got_col = False
    t0 = time.time()
    while time.time() - t0 < 150:
        if p.locator(".qcard").count() > 0:
            got_q = True; break
        if p.locator(".chat-flow .col").count() > 0:
            got_col = True; break
        time.sleep(2)
    if got_q:
        qtext = p.locator(".qcard").inner_text()
        shot(p, "18_learn_ai_question_card.png")
        p.locator(".qcard .qopt").first.click()
        t0 = time.time()
        while time.time() - t0 < 240:
            if p.locator(".chat-flow .col").count() > 0:
                got_col = True; break
            time.sleep(3)
    R["B10_ai_loop"] = {"clarification_card": got_q, "four_col_answer": got_col,
                        "qcard_text": qtext[:300] if got_q else None}
    if got_col:
        time.sleep(1)
        domtext = p.evaluate("document.querySelector('.chat-flow') ? document.querySelector('.chat-flow').innerText : ''")
        R["B10_ai_loop"]["answer_tags"] = {k: (k in domtext) for k in ["【岗】", "【课】", "【赛】", "【证】"]}
        R["B10_ai_loop"]["answer_head"] = domtext[:400]
        shot(p, "19_learn_ai_answer_4col.png")

    # AI 完成后 API 校验: 历史落库/首答徽章/掌握度+2
    hist = s.get(BASE + "/api/learn/history", headers=h2, timeout=20).json()
    badges = s.get(BASE + "/api/game/badges", headers=h2, timeout=15).json()
    me3 = s.get(BASE + "/api/auth/me", headers=h2, timeout=15).json()
    R["B10b_ai_loop_api"] = {
        "history_items": len(hist.get("items", [])),
        "history_head": (hist.get("items", [{}])[0].get("question", "") if hist.get("items") else "")[:50],
        "b_first_q_earned": next((x["earned"] for x in badges if x["id"] == "b_first_q"), None),
        "me_mastery_after_ai": me3.get("mastery"),
    }

    # /learn 重载(历史非空) → 渲染崩溃检查
    c_before = len(CONSOLE)
    p.reload(wait_until="domcontentloaded")
    time.sleep(3)
    msgs = p.evaluate("document.querySelectorAll('.chat-flow .msg').length")
    new_console = CONSOLE[c_before:]
    R["B11_learn_reload_history"] = {
        "msg_count": msgs,
        "new_console_errors": [x for x in new_console if x[1] == "error"][:4],
        "body_head": p.evaluate("document.querySelector('.chat-flow') ? document.querySelector('.chat-flow').innerText.slice(0, 200) : 'NO .chat-flow'"),
    }
    shot(p, "20_learn_reload_history.png")

    ctx.close()
    log("== S2026002 UI 完成 ==")


def ui_phase_s1(b):
    log("== UI 阶段: S2026001 完整数据学生 ==")
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    attach(p, "S2026001")
    login(p, "S2026001")
    time.sleep(1.2)
    R["E1_home_s001"] = {"card_text": p.evaluate("document.querySelector('.stu-card') ? document.querySelector('.stu-card').innerText : ''")}
    shot(p, "21_home_full_S2026001.png")

    c0 = len(CONSOLE)
    p.goto(BASE + "/learn", wait_until="domcontentloaded")
    time.sleep(3)
    msgs = p.evaluate("document.querySelectorAll('.chat-flow .msg').length")
    new_console = CONSOLE[c0:]
    R["E2_learn_s001"] = {
        "msg_count": msgs,
        "console_errors": [x for x in new_console if x[1] == "error"][:4],
        "flow_inner": p.evaluate("(document.querySelector('.chat-flow') ? document.querySelector('.chat-flow').innerText : 'NO .chat-flow').slice(0, 200)"),
    }
    shot(p, "22_learn_S2026001.png")

    p.goto(BASE + "/wrong", wait_until="domcontentloaded"); time.sleep(1.5)
    R["E3_wrong_s001"] = {"rows": p.locator(".row-item").count(),
                          "head": p.locator(".page").inner_text()[:200]}
    shot(p, "23_wrong_S2026001.png")

    p.goto(BASE + "/mine", wait_until="domcontentloaded"); time.sleep(1.5)
    R["E4_mine_s001"] = {"stats": p.evaluate("document.querySelector('.stu-stats') ? document.querySelector('.stu-stats').innerText : ''"),
                         "earned_text_count": p.locator("text=已获得").count()}
    shot(p, "24_mine_S2026001.png")
    ctx.close()


def ui_phase_t(b):
    log("== UI 阶段: T2026 教师(只读, 不点重置) ==")
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    attach(p, "T2026")
    login(p, "T2026")
    time.sleep(1)
    nav = p.evaluate("document.querySelector('.navtabs') ? document.querySelector('.navtabs').innerText : ''")
    R["F1_teacher_nav"] = {"nav": nav, "admin_tab": "管理看板" in nav}
    p.goto(BASE + "/admin", wait_until="domcontentloaded"); time.sleep(2)
    R["F2_admin_dash"] = {"has_table": p.locator("table").count() > 0,
                          "page_head": p.locator(".page").inner_text()[:300]}
    shot(p, "25_admin_teacher.png")
    ctx.close()


def main():
    api_phase()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        ui_phase(b)
        ui_phase_s1(b)
        ui_phase_t(b)
        b.close()

    R["E_console_all"] = CONSOLE
    R["E_http_4xx_5xx"] = HTTP
    R["E_dialogs"] = DIALOGS
    out = os.path.join(OUT, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    log(f"\n== SUMMARY ==\n{json.dumps({k: v for k, v in R.items() if not k.startswith('E_')}, ensure_ascii=False, indent=1)[:6000]}")
    log(f"console={len(CONSOLE)} http4xx={len(HTTP)} dialogs={len(DIALOGS)}")
    log(f"results saved: {out}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log("FATAL: " + traceback.format_exc())
        try:
            with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
                json.dump(R, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        sys.exit(1)