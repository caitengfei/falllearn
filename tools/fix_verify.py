# -*- coding: utf-8 -*-
"""五专家审核修复 · 逐项验收脚本（黑盒 API + Playwright 浏览器 + DB 直查）。
用法：D:\\python123\\python.exe E:\\lilei\\platform\\tools\\fix_verify.py
约定：自造测试数据全部自清（EXPERTFIX- 前缀）。
"""
import io
import os
import re
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

BASE = "http://127.0.0.1:8010"
DB = r"E:\lilei\platform\backend\falllearn.db"
UP = r"E:\lilei\platform\backend\uploads"
KB = r"E:\lilei\跌倒-岗课赛证知识库"

PASS, FAIL = [], []


def ck(tag, ok, detail=""):
    (PASS if ok else FAIL).append(f"{tag} {detail}")
    print(("  PASS " if ok else "  FAIL ") + tag + (f"  {detail}" if detail else ""))


def login(sno, pwd="123456"):
    r = requests.post(f"{BASE}/api/auth/login", json={"student_no": sno, "password": pwd}, timeout=15)
    assert r.status_code in (200, 401, 403), r.text
    return r


def main():
    T = requests.Session()
    r = login("T2026")
    assert r.status_code == 200, "T2026 登录失败"
    T.headers["Authorization"] = "Bearer " + r.json()["token"]
    S = requests.Session()
    rs = login("S2026001")
    assert rs.status_code == 200
    S.headers["Authorization"] = "Bearer " + rs.json()["token"]

    d = sqlite3.connect(DB)

    # ---------- 1. meta/clusters（CT-4）----------
    r = T.get(f"{BASE}/api/meta/clusters", timeout=10)
    items = r.json().get("items", [])
    db_counts = {c: n for c, n in d.execute(
        "SELECT cluster_id, COUNT(*) FROM questions WHERE cluster_id!='general' GROUP BY cluster_id")}
    ok = r.status_code == 200 and len(items) == 6
    for it in items:
        if it["qcount"] != db_counts.get(it["id"], 0):
            ok = False
    ck("CT-4 meta/clusters 六簇+实时题量", ok, f"{[(x['id'], x['qcount']) for x in items]}")

    # ---------- 2. 停用账号登录拦截（QA-1）----------
    r = T.post(f"{BASE}/api/admin/accounts", json={"name": "EXPERTFIX 停用测试", "role": "student"}, timeout=10)
    fix_id = r.json()["id"]
    T.put(f"{BASE}/api/admin/accounts/{fix_id}", json={"enabled": 0}, timeout=10)
    fix_sno = d.execute("SELECT student_no FROM users WHERE id=?", (fix_id,)).fetchone()[0]
    r2 = login(fix_sno)
    ck("QA-1 停用账号登录→403", r2.status_code == 403 and "停用" in r2.json().get("detail", ""),
       f"code={r2.status_code} detail={r2.json().get('detail')}")

    # ---------- 3. 登录错误文案（CT-17）----------
    r = login("NOPE123")
    ck("CT-17 学号不存在文案", r.status_code == 401 and "账号不存在" in r.json().get("detail", ""),
       r.json().get("detail", ""))

    # ---------- 4. /me 学时（CT-13）----------
    r = S.get(f"{BASE}/api/auth/me", timeout=10)
    ck("CT-13 /me 返回 hours 字段", r.status_code == 200 and "hours" in r.json(),
       f"hours={r.json().get('hours')}")

    # ---------- 5. 标题空校验（CT-2）----------
    r = T.post(f"{BASE}/api/admin/banners", json={"title": "   ", "tag": "x"}, timeout=10)
    ck("CT-2 空白标题→400", r.status_code == 400 and "标题" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    r = T.post(f"{BASE}/api/admin/announcements", json={"title": "  "}, timeout=10)
    ck("CT-2 公告空白标题→400", r.status_code == 400, "")

    # ---------- 6. 资源不存在→404（QA-8）----------
    r = T.put(f"{BASE}/api/admin/banners/999999", json={"title": "x"}, timeout=10)
    ck("QA-8 改不存在轮播→404", r.status_code == 404, r.json().get("detail", ""))
    r = T.delete(f"{BASE}/api/admin/announcements/999999", timeout=10)
    ck("QA-8 删不存在公告→404", r.status_code == 404, "")

    # ---------- 7. 上传白名单（QA-7）----------
    r = T.post(f"{BASE}/api/admin/upload",
               files={"file": ("hack.txt", io.BytesIO(b"hello"), "text/plain")}, timeout=10)
    ck("QA-7 上传 .txt→400", r.status_code == 400 and "不支持" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    png1 = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = T.post(f"{BASE}/api/admin/upload",
               files={"file": ("fix-verify.png", io.BytesIO(png1), "image/png")}, timeout=10)
    ck("QA-7 上传 png 正常", r.status_code == 200 and r.json().get("ok"), "")
    fix_upload = r.json().get("url", "").split("/")[-1]

    # ---------- 8. AccountPatch enabled 可选（QA-9）----------
    r = T.post(f"{BASE}/api/admin/accounts", json={"name": "EXPERTFIX 补丁测试", "role": "student"}, timeout=10)
    p_id = r.json()["id"]
    p_sno = d.execute("SELECT student_no FROM users WHERE id=?", (p_id,)).fetchone()[0]
    T.put(f"{BASE}/api/admin/accounts/{p_id}", json={"enabled": 0}, timeout=10)
    r = T.put(f"{BASE}/api/admin/accounts/{p_id}", json={"password": "123456"}, timeout=10)  # 只传密码
    en = d.execute("SELECT enabled FROM users WHERE id=?", (p_id,)).fetchone()[0]
    ck("QA-9 只传密码不改 enabled", r.status_code == 200 and en == 0, f"enabled={en}")
    r = login(p_sno)
    ck("QA-9 停用状态保留（登录仍 403）", r.status_code == 403, "")

    # ---------- 9/10. 培训容量（QA-10）----------
    r = T.post(f"{BASE}/api/admin/trainings", json={"title": "EXPERTFIX 容量测试", "capacity": 0}, timeout=10)
    ck("QA-10 capacity=0→400", r.status_code == 400, r.json().get("detail", ""))
    sid2 = d.execute("SELECT id FROM users WHERE student_no='S2026002'").fetchone()[0]
    r = T.post(f"{BASE}/api/admin/trainings",
               json={"title": "EXPERTFIX 容量测试", "capacity": 1, "student_ids": [sid2]}, timeout=10)
    tr_id = r.json()["id"]
    sid3 = d.execute("SELECT id FROM users WHERE student_no='S2026003'").fetchone()[0]
    r = T.post(f"{BASE}/api/admin/trainings/{tr_id}/enroll",
               json={"student_ids": [sid3], "status": "enrolled"}, timeout=10)
    ck("QA-10 满员再报→400", r.status_code == 400 and "满" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    r = T.post(f"{BASE}/api/admin/trainings/{tr_id}/students/999999/status", json={"status": "done"}, timeout=10)
    ck("QA-12 未报名者改状态→404", r.status_code == 404, r.json().get("detail", ""))

    # ---------- 11/12. 考试 status 白名单 + CSV 中文（QA-11/CT-12）----------
    r = T.get(f"{BASE}/api/admin/exams?status=bogus", timeout=10)
    ck("QA-11 exams?status=bogus→400", r.status_code == 400 and "状态参数" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    d.execute("INSERT INTO exams(title,kind,config,created_by,created_at) VALUES(?,?,?,?,?)",
              ("EXPERTFIX 临时卷", "daily", "{}",
               d.execute("SELECT id FROM users WHERE student_no='T2026'").fetchone()[0],
               int(time.time())))
    d.commit()
    ex_id = d.execute("SELECT last_insert_rowid() id").fetchone()[0]
    d.execute("INSERT INTO attempts(student_id,exam_id,status,started_at,submitted_at,score) "
              "VALUES(?,?, 'done', ?,?, -1)",
              (d.execute("SELECT id FROM users WHERE student_no='S2026001'").fetchone()[0],
               ex_id, int(time.time()) - 600, int(time.time()) - 100))
    d.commit()
    att_id = d.execute("SELECT last_insert_rowid() id").fetchone()[0]
    r = T.get(f"{BASE}/api/admin/exams/export?status=done", timeout=10)
    txt = r.content.decode("utf-8-sig")
    ck("QA-11/CT-12 CSV 导出含中文枚举",
       r.status_code == 200 and "已完成" in txt and "日常练习" in txt and "S2026001" in txt, "")
    d.execute("DELETE FROM attempts WHERE id=?", (att_id,))
    d.execute("DELETE FROM exams WHERE id=?", (ex_id,))
    d.commit()

    # ---------- 13. KB 覆盖确认 + 路径安全（UX-14/QA-15/CT-8）----------
    r = T.post(f"{BASE}/api/admin/ai/kb",
               json={"path": "05-元数据/EXPERTFIX-覆盖测试.md", "content": "# v1\n第一版"}, timeout=10)
    ck("UX-14 新文档写入", r.status_code == 200 and r.json().get("ok"), "")
    r = T.post(f"{BASE}/api/admin/ai/kb",
               json={"path": "05-元数据/EXPERTFIX-覆盖测试.md", "content": "# v2"}, timeout=10)
    ck("UX-14 未确认覆盖→400", r.status_code == 400 and "已存在" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    r = T.post(f"{BASE}/api/admin/ai/kb",
               json={"path": "05-元数据/EXPERTFIX-覆盖测试.md", "content": "# v2", "force": True}, timeout=10)
    body = open(os.path.join(KB, "05-元数据", "EXPERTFIX-覆盖测试.md"), encoding="utf-8").read()
    ck("UX-14 force 覆盖成功", r.status_code == 200 and "# v2" in body, "")
    os.remove(os.path.join(KB, "05-元数据", "EXPERTFIX-覆盖测试.md"))
    r = T.post(f"{BASE}/api/admin/ai/kb", json={"path": "/etc/passwd", "content": "x"}, timeout=10)
    ck("QA-15 绝对路径→400", r.status_code == 400, r.json().get("detail", ""))
    r = T.post(f"{BASE}/api/admin/ai/kb", json={"path": "../../x.md", "content": "x"}, timeout=10)
    ck("QA-15 上级跳转→400", r.status_code == 400, "")

    # ---------- 14. 模型设置清空（QA-3）----------
    r = T.post(f"{BASE}/api/admin/ai/model", json={}, timeout=10)
    v = d.execute("SELECT value FROM settings WHERE key='ai_model'").fetchone()
    ck("QA-3 空 body 清空设置", r.status_code == 200 and r.json().get("cleared") and not (v and v[0]),
       f"settings={v}")

    # ---------- 15. 422 → 400 中文（QA-14）+ 404 中文（CT-16）+ GZip（PERF-8）----------
    r = T.post(f"{BASE}/api/admin/accounts", json={"role": "student"}, timeout=10)  # 缺 name
    det = r.json().get("detail", "")
    ck("QA-14 422→400 中文", r.status_code == 400 and "name" in det and "参数" in det, det)
    r = T.get(f"{BASE}/api/definitely-not-exist", timeout=10)
    ck("CT-16 API 404 中文", r.status_code == 404 and "接口不存在" in r.json().get("detail", ""),
       r.json().get("detail", ""))
    # 大 JS 资源应走 gzip（index.html 本身 400+ 字节 < 1024 阈值，不压）
    idx = requests.get(BASE + "/", timeout=15).text
    m = re.search(r'src="(/assets/index-[^"]+\.js)"', idx)
    if m:
        r = requests.get(BASE + m.group(1), headers={"Accept-Encoding": "gzip"}, timeout=15)
        ck("PERF-8 GZip 生效（大 JS 资源）", r.headers.get("Content-Encoding") == "gzip",
           f"{m.group(1)}")
    else:
        ck("PERF-8 GZip 生效（大 JS 资源）", False, "未找到入口 JS")

    # ---------- 16. 学生列表聚合正确（PERF-1）----------
    r = T.get(f"{BASE}/api/admin/students", timeout=15)
    rows = {x["student_no"]: x for x in r.json()["items"]}
    base1 = rows.get("S2026001", {})
    db_pts = d.execute("SELECT points FROM points_cache WHERE student_id=(SELECT id FROM users WHERE student_no='S2026001')").fetchone()
    ck("PERF-1 学生列表聚合值正确", r.status_code == 200 and "S2026001" in rows
       and base1.get("points") == (db_pts[0] if db_pts else 0) and "hours" in base1
       and "avg_mastery" in base1, f"S2026001 points={base1.get('points')} hours={base1.get('hours')}")

    # ---------- 17. 大屏排行/学时（PERF-2）----------
    r = T.get(f"{BASE}/api/admin/stats/overview", timeout=15)
    ov = r.json()
    db_max = d.execute("SELECT MAX(points) FROM points_cache").fetchone()[0] or 0
    ck("PERF-2 大屏接口值正确", r.status_code == 200
       and ov.get("rank_points", [{}])[0].get("value", -1) == db_max
       and isinstance(ov.get("trend"), list) and len(ov["trend"]) == 7
       and isinstance(ov.get("weak_clusters"), list), "")

    # ---------- 18. 重置范围（QA-4）----------
    r = T.post(f"{BASE}/api/admin/accounts", json={"name": "EXPERTFIX 范围测试", "role": "student"}, timeout=10)
    scope_id = r.json()["id"]
    scope_sno = d.execute("SELECT student_no FROM users WHERE id=?", (scope_id,)).fetchone()[0]
    Sc = requests.Session()
    rr = login(scope_sno)
    Sc.headers["Authorization"] = "Bearer " + rr.json()["token"]
    Sc.post(f"{BASE}/api/game/checkin", timeout=10)  # 拿积分
    p_before = Sc.get(f"{BASE}/api/auth/me", timeout=10).json()["points"]
    r = T.post(f"{BASE}/api/admin/reset-demo", timeout=30)
    rr = login(scope_sno)
    Sc2 = requests.Session()
    Sc2.headers["Authorization"] = "Bearer " + rr.json()["token"]
    p_after = Sc2.get(f"{BASE}/api/auth/me", timeout=10).json()["points"]
    base_after = S.get(f"{BASE}/api/auth/me", timeout=10).json()["points"]
    ck("QA-4 重置不伤非演示学生", r.status_code == 200 and p_after == p_before and p_before > 0,
       f"{scope_sno} points {p_before}->{p_after}")
    ck("QA-4 演示基线恢复 128 分", base_after == 128, f"S2026001 points={base_after}")

    # ---------- 19. 删除账号（QA-13 路径）+ 自清 ----------
    r = T.delete(f"{BASE}/api/admin/accounts/{p_id}", timeout=10)
    ck("QA-13 删除账号", r.status_code == 200 and r.json().get("ok"), "")
    T.delete(f"{BASE}/api/admin/accounts/{fix_id}", timeout=10)
    T.delete(f"{BASE}/api/admin/accounts/{scope_id}", timeout=10)
    T.delete(f"{BASE}/api/admin/trainings/{tr_id}", timeout=10)
    d.close()

    # ---------- 20. DB 索引（PERF-3）----------
    d2 = sqlite3.connect(DB)
    names = {r[0] for r in d2.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    need = ["idx_pointslog_time", "idx_chat_time", "idx_attempts_status", "idx_mastery_cluster",
            "idx_answers_q", "idx_enrolls_student", "idx_checkins_date", "idx_ai_grades_attempt_uq"]
    missing = [n for n in need if n not in names]
    ck("PERF-3 8 个新索引已建", not missing, f"missing={missing}" if missing else "8/8")
    d2.close()

    if fix_upload and os.path.exists(os.path.join(UP, fix_upload)):
        os.remove(os.path.join(UP, fix_upload))

    print(f"\n===== 黑盒结果：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print("  FAIL", f)

    browser_results = run_browser()
    return 0 if not FAIL and browser_results == 0 else 1


def run_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright 不可用，跳过浏览器验收")
        return 0
    fails = []

    def bck(tag, ok, detail=""):
        print(("  PASS [browser] " if ok else "  FAIL [browser] ") + tag + (f"  {detail}" if detail else ""))
        if not ok:
            fails.append(tag)

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        dialog_state = {"capture": False, "msgs": []}
        def on_dialog(dd):
            if dialog_state["capture"]:
                dialog_state["msgs"].append(dd.message)
                dd.dismiss()
            else:
                dd.accept()
        pg.on("dialog", on_dialog)

        # 登录教师
        pg.goto(f"{BASE}/login")
        pg.locator(".dh-btn", has_text="T2026").first.click()
        pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
        pg.wait_for_url("**/admin**", timeout=15000)
        pg.wait_for_timeout(800)

        # UX-1/VIS-1：全局 mask/modal 真弹层
        pg.goto(f"{BASE}/admin/content")
        pg.wait_for_timeout(1000)
        pg.locator(".card-title .more", has_text="新建预告").first.click()
        pg.wait_for_timeout(500)
        mask = pg.locator(".mask")
        modal = pg.locator(".modal")
        ok_mask = mask.count() > 0 and modal.count() > 0
        box = modal.bounding_box() if ok_mask else None
        z = pg.evaluate("() => { const m = document.querySelector('.mask'); const s = getComputedStyle(m); "
                        "return {pos: s.position, zi: s.zIndex} }") if ok_mask else {}
        centered = bool(box and box["x"] > 150 and box["y"] > 80)
        bck("UX-1/VIS-1 全局弹层 mask+modal 居中", bool(ok_mask and centered and z.get("pos") == "fixed"),
            f"mask={z} box={box}")
        pg.locator(".modal-h .more").first.click()
        pg.wait_for_timeout(300)

        # VIS-2/UX-3：开关尺寸
        sw = pg.locator(".switch").first.bounding_box()
        bck("VIS-2 switch 尺寸≈40x22", bool(sw and 35 <= sw["width"] <= 46 and 18 <= sw["height"] <= 26),
            str(sw))

        # UX-5：banner 排序按钮真实生效（点下移，验证 PUT 200）
        codes = []
        def on_put(r):
            if "/admin/banners/" in r.url and r.request.method == "PUT":
                codes.append((r.url, r.status))
        pg.on("response", on_put)
        if pg.locator(".op button[title=下移]").count() > 0:
            pg.locator(".op button[title=下移]").first.click()
            pg.wait_for_timeout(1500)
            ok_move = any(s == 200 for _, s in codes)
            bck("UX-5 banner 下移 PUT 200", ok_move, str(codes[:4]))
            if codes:
                pg.locator(".op button[title=上移]").first.click()
                pg.wait_for_timeout(1500)

        # VIS-3：390px 无横向溢出（四个重点页 + 首页）
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(400)
        for path in ("/admin/students", "/admin/content", "/admin/stats", "/admin/exams", "/admin"):
            pg.goto(f"{BASE}{path}")
            pg.wait_for_timeout(900)
            swid = pg.evaluate("document.documentElement.scrollWidth")
            bck(f"VIS-3 390px 无溢出 {path}", swid <= 392, f"scrollWidth={swid}")

        # UX-2：CSV 导出走带 token 的 fetch（200 + csv）
        pg.set_viewport_size({"width": 1440, "height": 900})
        export_res = {}
        def on_resp(r):
            if "/api/admin/exams/export" in r.url:
                export_res["status"] = r.status
                export_res["type"] = r.headers.get("content-type", "")
        pg.on("response", on_resp)
        pg.goto(f"{BASE}/admin/exams")
        pg.wait_for_timeout(1000)
        btn = pg.locator("button", has_text="导出")
        if btn.count() > 0:
            btn.first.click()
            pg.wait_for_timeout(2500)
            bck("UX-2 CSV 导出 200+csv", export_res.get("status") == 200 and "csv" in export_res.get("type", ""),
                str(export_res))
        else:
            bck("UX-2 CSV 导出按钮存在", False, "未找到导出按钮")

        # UX-6：停用/启用学生弹确认
        pg.goto(f"{BASE}/admin/students")
        pg.wait_for_timeout(1000)
        dialog_state["capture"] = True
        pg.locator(".switch").first.click()
        pg.wait_for_timeout(800)
        bck("UX-6 停用/启用弹确认", len(dialog_state["msgs"]) > 0, str(dialog_state["msgs"][:1]))
        dialog_state["capture"] = False

        # CT-13：学生端 我的 页显示学时（先清教师 token，避免 /login 重定向）
        pg.evaluate("Object.keys(localStorage).forEach(k => localStorage.removeItem(k))")
        pg.goto(f"{BASE}/login")
        pg.wait_for_timeout(800)
        pg.locator(".dh-btn", has_text="S2026001").first.click()
        pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
        pg.wait_for_selector(".stu-stats", timeout=15000)
        pg.wait_for_timeout(1000)
        pg.goto(f"{BASE}/mine")
        pg.wait_for_timeout(1200)
        html = pg.content()
        bck("CT-13 学生端我的页有学时栏", "学时" in html, "")

        # CT-4：首页知识卡显示题量（学生端首页 = /）
        pg.goto(f"{BASE}/")
        pg.wait_for_timeout(2500)
        txt = pg.evaluate("document.body.innerText")
        bck("CT-4 首页知识卡显示题量", "五步处置" in txt and "题" in txt, "")

        b.close()

    print(f"===== 浏览器结果：{len(fails)} 失败 =====")
    for f in fails:
        print("  FAIL", f)
    return len(fails)


if __name__ == "__main__":
    sys.exit(main())