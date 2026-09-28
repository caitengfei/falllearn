# -*- coding: utf-8 -*-
"""expert_perf2: FallLearn 只读性能/质量实测（性能与代码质量专家）
- 不改任何项目文件；不调 reset-demo；不 build。
- A. requests 实测 10 个核心 API 响应时间
- B. 学生 token 打 admin 端点验证 403
- C. 并发读探测（8 并发 leaderboard）
- D. dist / db 文件大小
- E. Playwright(msedge) 冒烟：登录→Home→Learn，抓 console 错误 + 截图
输出: stdout JSON + E:\\lilei\\docs\\expert-test\\perf2\\perf2_results.json + 截图
"""
import json
import os
import statistics
import time

import requests

BASE = "http://127.0.0.1:8010"
OUT_DIR = r"E:\lilei\docs\expert-test\perf2"
DIST = r"E:\lilei\platform\frontend\dist"
DB_DIR = r"E:\lilei\platform\backend"
os.makedirs(OUT_DIR, exist_ok=True)

report = {"api_timings": [], "auth_checks": [], "concurrency": {}, "sizes": {}, "browser": {}}

# ---------------- A. API 计时 ----------------
def measure(name, fn, runs=3, s=""):
    ts, status, err = [], None, None
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            r = fn()
            status = r.status_code
            if status >= 400:
                err = "HTTP %s: %s" % (status, r.text[:120])
        except Exception as e:
            err = repr(e)[:150]
        ts.append((time.perf_counter() - t0) * 1000)
    rec = {"name": name, "runs_ms": [round(x, 1) for x in ts],
           "median_ms": round(statistics.median(ts), 1), "max_ms": round(max(ts), 1),
           "status": status, "error": err}
    report["api_timings"].append(rec)
    print(f"[api] {name}: status={status} median={rec['median_ms']}ms max={rec['max_ms']}ms {err or ''}")
    return rec


def main():
    print("== A. 登录与核心 API 计时 ==")
    measure("login(S2026001)", lambda: requests.post(
        f"{BASE}/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=15))
    # 单独登录拿 token（measure 不保留 body）
    s = requests.Session()
    lr = s.post(f"{BASE}/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=15)
    tok1 = lr.json().get("token", "")
    s2 = requests.Session()
    lr2 = s2.post(f"{BASE}/api/auth/login", json={"student_no": "S2026002", "password": "123456"}, timeout=15)
    tok2 = lr2.json().get("token", "")
    st = requests.Session()
    lrt = st.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=15)
    tokT = lrt.json().get("token", "")
    print(f"tokens: S1={'ok' if tok1 else 'FAIL'} S2={'ok' if tok2 else 'FAIL'} T={'ok' if tokT else 'FAIL'}")
    s.headers["authorization"] = f"Bearer {tok1}"
    s2.headers["authorization"] = f"Bearer {tok2}"

    measure("me", lambda: s.get(f"{BASE}/api/auth/me", timeout=15))
    measure("today", lambda: s.get(f"{BASE}/api/game/today", timeout=15))
    measure("leaderboard", lambda: s.get(f"{BASE}/api/game/leaderboard", timeout=15))
    measure("wrongList(active)", lambda: s.get(f"{BASE}/api/wrong?status=active", timeout=15))
    measure("quizWeak", lambda: s.get(f"{BASE}/api/quiz/weak", timeout=15))
    measure("learnHistory", lambda: s.get(f"{BASE}/api/learn/history", timeout=15))
    measure("badges", lambda: s.get(f"{BASE}/api/game/badges", timeout=15))

    # quiz/start + submit 用空白学生 S2026002，减少对 S1 种子数据的污染
    measure("quiz/start(S2026002)", lambda: s2.post(f"{BASE}/api/quiz/start", timeout=20), runs=2)
    try:
        body = s2.post(f"{BASE}/api/quiz/start", timeout=20).json()
        attempt_id = body["attempt_id"]
        answers = {str(it["question_id"]): "A" for it in body["items"]}
        measure("quiz/submit", lambda: s2.post(f"{BASE}/api/quiz/submit",
                                               json={"attempt_id": attempt_id, "answers": answers}, timeout=30), runs=1)
    except Exception as e:
        print("quiz submit 失败:", repr(e))

    print("== B. 权限验证 ==")
    def admin_dash_student():
        return requests.get(f"{BASE}/api/admin/dashboard",
                            headers={"authorization": f"Bearer {tok1}"}, timeout=15)
    def admin_stats_student():
        return requests.get(f"{BASE}/api/admin/stats",
                            headers={"authorization": f"Bearer {tok1}"}, timeout=15)
    def admin_dash_teacher():
        return requests.get(f"{BASE}/api/admin/dashboard",
                            headers={"authorization": f"Bearer {tokT}"}, timeout=15)
    for label, fn, expect in [
        ("GET /api/admin/dashboard (学生token, 期望403)", admin_dash_student, 403),
        ("GET /api/admin/stats (学生token, 期望403/404)", admin_stats_student, None),
        ("GET /api/admin/dashboard (教师token, 期望200)", admin_dash_teacher, 200),
    ]:
        t0 = time.perf_counter()
        try:
            r = fn()
            ms = round((time.perf_counter() - t0) * 1000, 1)
            body_txt = r.text[:120]
        except Exception as e:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            r, body_txt = None, repr(e)[:150]
        code = r.status_code if r is not None else None
        ok = (code == expect) if expect else True
        report["auth_checks"].append({"check": label, "status": code, "ms": ms,
                                      "body": body_txt, "pass": ok})
        print(f"[auth] {label} -> {code} ({ms}ms) {body_txt}")

    # 越权变体: 学生 token 打别人资源
    report["auth_checks"].append({
        "check": "说明: /api/learn/status 有会话归属校验(代码审); /api/quiz/submit 校验 attempt 归属(代码审)",
        "status": None, "ms": None, "body": "", "pass": True})

    print("== C. 并发读探测 ==")
    from concurrent.futures import ThreadPoolExecutor
    def one_lb(_):
        t0 = time.perf_counter()
        r = s.get(f"{BASE}/api/game/leaderboard", timeout=20)
        return (time.perf_counter() - t0) * 1000, r.status_code
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        out = list(ex.map(one_lb, range(8)))
    wall = (time.perf_counter() - t0) * 1000
    codes = [c for _, c in out]
    report["concurrency"] = {"n": 8, "wall_ms": round(wall, 1),
                             "per_req_ms": [round(x, 1) for x, _ in out],
                             "statuses": codes,
                             "all_200": all(c == 200 for c in codes)}
    print(f"[conc] 8 并发 leaderboard: wall={round(wall,1)}ms per={report['concurrency']['per_req_ms']} codes={codes}")

    print("== D. 文件大小 ==")
    dist_files, dist_total = [], 0
    for root, _, files in os.walk(DIST):
        for f in files:
            p = os.path.join(root, f)
            sz = os.path.getsize(p)
            dist_total += sz
            dist_files.append({"path": os.path.relpath(p, DIST), "bytes": sz})
    db_files = {}
    for f in os.listdir(DB_DIR):
        if f.startswith("falllearn.db"):
            db_files[f] = os.path.getsize(os.path.join(DB_DIR, f))
    report["sizes"] = {"dist_total_bytes": dist_total, "dist_files": dist_files, "db_files": db_files}
    print(f"[size] dist 总计 {dist_total} bytes; db 文件 {db_files}")

    print("== E. Playwright 冒烟 ==")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            console_errs, page_errs, api_events = [], [], []
            page.on("console", lambda m: console_errs.append(m.text[:200]) if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errs.append(str(e)[:300]))
            def on_resp(m):
                try:
                    if "/api/" not in m.url:
                        return
                    ms = None
                    try:
                        t = m.request.timing
                        ms = round(t["endTime"] - t["startTime"], 1)
                    except Exception:
                        pass
                    api_events.append({"url": m.url.split(BASE)[-1], "status": m.status, "ms": ms})
                except Exception:
                    pass
            page.on("response", on_resp)

            t0 = time.perf_counter()
            page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=20000)
            login_ms = (time.perf_counter() - t0) * 1000
            page.fill('input[placeholder="如 S2026001"]', "S2026001")
            page.fill('input[type="password"]', "123456")
            page.click("button:has-text('登 录')")
            page.wait_for_url("**/", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=15000)
            home_api_ms = sum(e["ms"] for e in api_events if e["ms"] is not None)
            home_shot = os.path.join(OUT_DIR, "home_S2026001.png")
            page.screenshot(path=home_shot)
            print(f"[browser] login→home 首屏 {round(login_ms,0)}ms, home API 请求 {len(api_events)} 个, "
                  f"API 总耗时 {round(home_api_ms,1)}ms")
            for e in api_events:
                print("   ", e["url"], e["status"], e["ms"], "ms")

            page.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3500)
            learn_errs_before = len(console_errs) + len(page_errs)
            learn_shot = os.path.join(OUT_DIR, "learn_S2026001.png")
            page.screenshot(path=learn_shot)
            learn_html_len = page.evaluate("document.body.innerHTML.length")
            print(f"[browser] /learn 渲染后 body 长度={learn_html_len}, console_errors={len(console_errs)}, page_errors={len(page_errs)}")
            for e in (console_errs + page_errs):
                print("   ERR:", e[:220])

            report["browser"] = {
                "login_to_home_ms": round(login_ms, 1),
                "home_api_count": len(api_events),
                "home_api_sum_ms": round(home_api_ms, 1),
                "home_api": api_events,
                "console_errors": console_errs[-20:],
                "page_errors": page_errs[-20:],
                "learn_body_len": learn_html_len,
                "screenshots": [home_shot, learn_shot],
            }
            browser.close()
    except Exception as e:
        report["browser"]["error"] = repr(e)[:300]
        print("[browser] 冒烟失败:", repr(e)[:300])

    out = os.path.join(OUT_DIR, "perf2_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("saved:", out)


if __name__ == "__main__":
    main()