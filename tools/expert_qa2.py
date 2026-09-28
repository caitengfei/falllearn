# -*- coding: utf-8 -*-
"""FallLearn 功能测试(QA) 第二轮 — 补测:
1) S2026003 真空白学生: 首页/错题本/我的/学习中心空态 + 空白组卷策略
2) 同 context 新标签页直接访问 /exam/<id> (已登录但 sessionStorage 无题) → 卡死/白屏验证
3) AI 学习闭环(唯一一次真实提问, 走 API: ask→澄清→answer→status done)
4) S2026001 UI 抽查(首页/学习中心崩溃/错题本/我的)
5) T2026 教师看板(只读, 不点重置)
"""
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
    ok = False
    try:
        p.wait_for_selector(".stu-card", timeout=20000)
        ok = True
    except Exception:
        pass
    log(f"  login {sno}: path={cur} home_card={ok}")
    return ok

def main():
    s = requests.Session()
    def api_login(sno):
        r = s.post(BASE + "/api/auth/login", json={"student_no": sno, "password": "123456"}, timeout=15)
        r.raise_for_status()
        return r.json()["token"]
    t3 = api_login("S2026003")
    t2 = api_login("S2026002")
    h3 = {"Authorization": f"Bearer {t3}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    # ---------- 1) S2026003 真空白 ----------
    log("== 1) S2026003 真空白学生 ==")
    R["G1_s003_me"] = s.get(BASE + "/api/auth/me", headers=h3, timeout=15).json()
    R["G1b_s003_weak"] = s.get(BASE + "/api/quiz/weak", headers=h3, timeout=15).json()
    R["G1c_s003_wrong"] = s.get(BASE + "/api/wrong?status=active", headers=h3, timeout=15).json()
    R["G1d_s003_points"] = s.get(BASE + "/api/game/points", headers=h3, timeout=15).json()
    R["G1e_s003_badges"] = s.get(BASE + "/api/game/badges", headers=h3, timeout=15).json()
    R["G1f_s003_leaderboard"] = s.get(BASE + "/api/game/leaderboard", headers=h3, timeout=15).json()
    R["G1g_s003_today"] = s.get(BASE + "/api/game/today", headers=h3, timeout=15).json()
    r = s.post(BASE + "/api/quiz/start", headers=h3, timeout=30)
    st3 = r.json()
    R["G2_s003_quiz_start"] = {
        "status": r.status_code, "count": st3.get("count"),
        "types": [it["type"] for it in st3.get("items", [])],
        "clusters": [it["cluster"] for it in st3.get("items", [])],
        "attempt_id": st3.get("attempt_id"),
        "all_items_valid": all(it.get("stem") and it.get("type") in {"单选", "多选", "判断"}
                               and (it["type"] == "判断" or 2 <= len(it.get("options") or []) <= 4)
                               for it in st3.get("items", [])),
    }

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)

        # ---------- 2) 同 context 新标签页 /exam/<id> ----------
        log("== 2) 同 context 新标签页直接访问 /exam/<id> (S2026002 孤儿卷 5) ==")
        ctx2 = b.new_context(viewport={"width": 1440, "height": 950})
        p2 = ctx2.new_page()
        attach(p2, "S2026002-newtab2")
        login(p2, "S2026002")
        time.sleep(0.8)
        # 确认 attempt 5 服务端仍 open
        r = s.get(BASE + "/api/auth/me", headers=h2, timeout=15)
        p2b = ctx2.new_page()   # 同 context: 共享 localStorage(已登录), 无 sessionStorage
        attach(p2b, "S2026002-newtab2b")
        p2b.goto(BASE + "/exam/5", wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)
        body = p2b.evaluate("document.body ? document.body.innerText : ''")
        R["H1_newtab_exam_open_attempt"] = {
            "url": p2b.evaluate("location.href"),
            "has_loading_text": "题目加载中" in body,
            "has_question1": "第 1 / 10 题" in body,
            "page_head": p2b.evaluate("document.querySelector('.page') ? document.querySelector('.page').innerText.slice(0, 300) : 'NO .page'"),
        }
        shot(p2b, "10b_exam_newtab_same_context.png")
        # 无恢复手段? 检查页面按钮
        R["H1b_recover_buttons"] = {
            "buttons": p2b.evaluate("Array.from(document.querySelectorAll('.page button')).map(x=>x.innerText)"),
        }
        # 服务端状态: 直接交卷该孤儿卷(空答案) → 应 200(仍 open)
        r = s.post(BASE + "/api/quiz/submit", headers=h2, json={"attempt_id": 5, "answers": {}}, timeout=30)
        R["H2_orphan_attempt_still_open"] = {"submit_status": r.status_code, "score": r.json().get("score") if r.status_code == 200 else None}
        p2b.close()

        # ---------- 3) S2026003 UI 空态 ----------
        log("== 3) S2026003 UI 空态 ==")
        ctx3 = b.new_context(viewport={"width": 1440, "height": 950})
        p3 = ctx3.new_page()
        attach(p3, "S2026003")
        login(p3, "S2026003")
        time.sleep(1.2)
        R["G3_home_blank"] = {"card_text": p3.evaluate("document.querySelector('.stu-card') ? document.querySelector('.stu-card').innerText : ''"),
                              "calendar_text": p3.locator(".tl, .empty").first.inner_text() if p3.locator(".tl, .empty").count() else None,
                              "page_head": p3.locator(".page").inner_text()[:400]}
        shot(p3, "31_home_blank_S2026003.png")

        p3.goto(BASE + "/wrong", wait_until="domcontentloaded"); time.sleep(1.5)
        R["G4_wrong_blank"] = {"text": p3.locator(".page").inner_text()[:200], "rows": p3.locator(".row-item").count()}
        shot(p3, "32_wrong_blank_S2026003.png")

        p3.goto(BASE + "/mine", wait_until="domcontentloaded"); time.sleep(1.5)
        R["G5_mine_blank"] = {"stats": p3.evaluate("document.querySelector('.stu-stats') ? document.querySelector('.stu-stats').innerText : ''"),
                              "points_log_empty": "暂无积分记录" in p3.locator(".page").inner_text()}
        shot(p3, "33_mine_blank_S2026003.png")

        c0 = len(CONSOLE)
        p3.goto(BASE + "/learn", wait_until="domcontentloaded"); time.sleep(2.5)
        R["G6_learn_blank"] = {
            "msg_count": p3.evaluate("document.querySelectorAll('.chat-flow .msg').length"),
            "has_textarea": p3.locator("textarea").count(),
            "console_errors": [x for x in CONSOLE[c0:] if x[1] == "error"][:3],
        }
        shot(p3, "34_learn_blank_S2026003.png")

        # 练习开卷(空白学生) → 单选高亮对照组
        p3.goto(BASE + "/practice", wait_until="domcontentloaded"); time.sleep(1.2)
        try:
            p3.locator(".card button", has_text="开始").first.click(timeout=8000)
        except Exception as e:
            R["G7_exam_s003"] = {"error": str(e)}
        cur = wait_path_starts(p3, "/exam/", 30)
        time.sleep(1.2)
        items = p3.evaluate("JSON.parse(sessionStorage.getItem('exam_items')||'[]')")
        R["G7_exam_s003"] = {"path": cur, "count": len(items),
                             "types": [it.get("type") for it in items]}
        shot(p3, "35_exam_s003.png")
        # 第一题点一个选项 → 单选/判断应有 .on 高亮(对照组, 证明高亮机制本身存在)
        first_type = items[0].get("type") if items else None
        try:
            p3.locator(".opt").first.click(); p3.wait_for_timeout(200)
            classes = p3.evaluate("Array.from(document.querySelectorAll('.opt')).map(o=>o.className)")
            R["G7b_single_highlight_control"] = {
                "first_type": first_type, "opt_classes": classes,
                "highlighted": sum(1 for c in classes if " on" in (" " + c + " ")),
            }
            shot(p3, "36_exam_single_highlight_control.png")
        except Exception as e:
            R["G7b_single_highlight_control"] = {"error": str(e)}
        ctx3.close()

        # ---------- 4) S2026001 UI 抽查 ----------
        log("== 4) S2026001 UI 抽查 ==")
        ctx1 = b.new_context(viewport={"width": 1440, "height": 950})
        p1 = ctx1.new_page()
        attach(p1, "S2026001")
        login(p1, "S2026001")
        time.sleep(1.2)
        R["E1_home_s001"] = {"card_text": p1.evaluate("document.querySelector('.stu-card') ? document.querySelector('.stu-card').innerText : ''")}
        shot(p1, "21_home_full_S2026001.png")

        c0 = len(CONSOLE)
        p1.goto(BASE + "/learn", wait_until="domcontentloaded"); time.sleep(3)
        R["E2_learn_s001"] = {
            "msg_count": p1.evaluate("document.querySelectorAll('.chat-flow .msg').length"),
            "has_textarea": p1.locator("textarea").count(),
            "console_errors": [x for x in CONSOLE[c0:] if x[1] == "error"][:4],
            "flow_inner": p1.evaluate("(document.querySelector('.chat-flow') ? document.querySelector('.chat-flow').innerText : 'NO .chat-flow').slice(0, 150)"),
        }
        shot(p1, "22_learn_S2026001.png")

        p1.goto(BASE + "/wrong", wait_until="domcontentloaded"); time.sleep(1.5)
        R["E3_wrong_s001"] = {"rows": p1.locator(".row-item").count(),
                              "head": p1.locator(".page").inner_text()[:200]}
        shot(p1, "23_wrong_S2026001.png")

        p1.goto(BASE + "/mine", wait_until="domcontentloaded"); time.sleep(1.5)
        R["E4_mine_s001"] = {"stats": p1.evaluate("document.querySelector('.stu-stats') ? document.querySelector('.stu-stats').innerText : ''"),
                             "earned_text_count": p1.locator("text=已获得").count()}
        shot(p1, "24_mine_S2026001.png")
        ctx1.close()

        # ---------- 5) T2026 教师 ----------
        log("== 5) T2026 教师看板(只读) ==")
        ctxt = b.new_context(viewport={"width": 1440, "height": 950})
        pt = ctxt.new_page()
        attach(pt, "T2026")
        login(pt, "T2026")
        time.sleep(1)
        nav = pt.evaluate("document.querySelector('.navtabs') ? document.querySelector('.navtabs').innerText : ''")
        R["F1_teacher_nav"] = {"nav": nav, "admin_tab": "管理看板" in nav}
        pt.goto(BASE + "/admin", wait_until="domcontentloaded"); time.sleep(2)
        R["F2_admin_dash"] = {"has_table": pt.locator("table").count() > 0,
                              "page_head": pt.locator(".page").inner_text()[:300]}
        shot(pt, "25_admin_teacher.png")
        ctxt.close()
        b.close()

    # ---------- 6) AI 学习闭环(唯一一次真实提问, API 链路) ----------
    log("== 6) AI 学习闭环 (S2026002, API, 唯一真实提问) ==")
    r = s.post(BASE + "/api/learn/ask", headers=h2, json={"question": "什么是跌倒"}, timeout=60)
    ask = r.json() if r.status_code == 200 else {}
    R["I1_ask"] = {"status": r.status_code, "body": ask}
    if r.status_code == 200:
        sid, lid = ask["session_id"], ask["log_id"]
        status = None
        t0 = time.time()
        while time.time() - t0 < 300:
            rs = s.get(BASE + f"/api/learn/status?session_id={sid}&log_id={lid}", headers=h2, timeout=60)
            if rs.status_code != 200:
                R["I2_status_error"] = {"status": rs.status_code, "body": rs.text[:200]}
                break
            j = rs.json()
            st = j.get("status")
            if st == "question" and status != "question":
                R["I2_clarification"] = {"question": (j.get("question") or {}).get("question"),
                                         "header": (j.get("question") or {}).get("header"),
                                         "options": [(o.get("label") or "")[:40] for o in (j.get("question") or {}).get("options", [])]}
                ra = s.post(BASE + "/api/learn/answer", headers=h2, json={"log_id": lid, "option_index": 0}, timeout=60)
                R["I3_answer"] = {"status": ra.status_code, "body": ra.json() if ra.status_code == 200 else ra.text[:200]}
            if st == "done":
                status = "done"
                R["I4_done"] = {"clusters": j.get("clusters"),
                                "answer_tags": {k: (k in (j.get("answer") or "")) for k in ["【岗】", "【课】", "【赛】", "【证】"]},
                                "answer_head": (j.get("answer") or "")[:500],
                                "elapsed_sec": round(time.time() - t0, 1)}
                break
            status = st
            time.sleep(4)
        R["I5_final_status"] = status
        R["I6_history"] = s.get(BASE + "/api/learn/history", headers=h2, timeout=20).json()
        R["I7_badges"] = {"b_first_q": next((x["earned"] for x in s.get(BASE + "/api/game/badges", headers=h2, timeout=15).json() if x["id"] == "b_first_q"), None)}
        R["I8_me"] = s.get(BASE + "/api/auth/me", headers=h2, timeout=15).json()
        R["I9_points"] = {"total": s.get(BASE + "/api/game/points", headers=h2, timeout=15).json().get("total")}

    R["E_console_all"] = CONSOLE
    R["E_http_4xx_5xx"] = HTTP
    R["E_dialogs"] = DIALOGS
    out = os.path.join(OUT, "results2.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    log(f"\n== SUMMARY2 ==\n{json.dumps({k: v for k, v in R.items() if not k.startswith('E_') and k not in ('I6_history',)}, ensure_ascii=False, indent=1)[:7000]}")
    log(f"console={len(CONSOLE)} http4xx={len(HTTP)}")
    log(f"results saved: {out}")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        log("FATAL: " + traceback.format_exc())
        try:
            with open(os.path.join(OUT, "results2.json"), "w", encoding="utf-8") as f:
                json.dump(R, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        sys.exit(1)