# -*- coding: utf-8 -*-
"""安全加固验收脚本（P1.1 修复项逐条验证）：
覆盖：请求体上限 / 输入长度 / 口令强度 / 教师横向越权 / SSRF 收敛 /
      link·image scheme / 并发交卷幂等 / 错题复习防刷 / 探测路径 404。

用法（本地，会创建并清理测试账号 S2026SEC）：
    D:\\python123\\python.exe E:\\lilei\\platform\\tools\\security_check.py
"""
import concurrent.futures
import json
import os
import sqlite3
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.environ.get("FALLLEARN_BASE", "http://127.0.0.1:8010")
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "falllearn.db")
P = {"Content-Type": "application/json"}
results = []


def check(name, ok, extra=""):
    results.append((name, ok))
    print(("\u2713 " if ok else "\u2717 ") + name, extra)


def login(no, pwd="123456"):
    r = requests.post(BASE + "/api/auth/login", json={"student_no": no, "password": pwd}, timeout=10)
    return r.json().get("token") if r.status_code == 200 else None


t = login("T2026")
H = {"authorization": "Bearer " + t, **P}

# ---------- 1. 请求体硬上限（413） ----------
big = json.dumps({"question": "A" * (7 * 1024 * 1024)}).encode()
r = requests.post(BASE + "/api/learn/ask", headers=H, data=big, timeout=30)
check("超大请求体被拒 413（7MB body）", r.status_code == 413, str(r.status_code))

# ---------- 2. 教师端输入校验 ----------
r = requests.post(BASE + "/api/admin/students", headers=H,
                  json={"name": "弱口令", "student_no": "S2026WEAK", "password": "1"}, timeout=10)
check("弱口令创建被拒 400", r.status_code == 400, r.text[:80])
r = requests.post(BASE + "/api/admin/students", headers=H,
                  json={"name": "空口令", "student_no": "S2026EMPTY", "password": ""}, timeout=10)
check("空口令创建被拒 400", r.status_code == 400, r.text[:80])
r = requests.post(BASE + "/api/admin/accounts", headers=H,
                  json={"name": "二号教师", "role": "teacher", "password": "123456"}, timeout=10)
check("后台创建教师账号被拒 403（防提权）", r.status_code == 403, r.text[:80])

# ---------- 3. link / image scheme 白名单 ----------
r = requests.post(BASE + "/api/admin/banners", headers=H,
                  json={"title": "XSS卡", "link": "javascript:alert(1)"}, timeout=10)
check("javascript: 链接被拒 400", r.status_code == 400, r.text[:60])
r = requests.post(BASE + "/api/admin/banners", headers=H,
                  json={"title": "CSS卡", "image": "data:text/html;base64,PHNjcmlwdD4="}, timeout=10)
check("data: 图片地址被拒 400", r.status_code == 400, r.text[:60])

# ---------- 4. SSRF：AI 直连 base_url 收敛 ----------
r = requests.post(BASE + "/api/admin/ai/direct", headers=H,
                  json={"base_url": "http://169.254.169.254/latest", "model": "x", "api_key": "k"}, timeout=10)
check("云元数据地址被拒 400（SSRF）", r.status_code == 400, r.text[:80])
r = requests.post(BASE + "/api/admin/ai/direct", headers=H,
                  json={"base_url": "http://100.100.100.200/latest/meta-data", "model": "x", "api_key": "k"}, timeout=10)
check("阿里云元数据地址被拒 400（SSRF）", r.status_code == 400, r.text[:80])
r = requests.post(BASE + "/api/admin/ai/direct", headers=H,
                  json={"base_url": "ftp://evil/x", "model": "x", "api_key": "k"}, timeout=10)
check("非 http(s) 地址被拒 400", r.status_code == 400, r.text[:80])

# ---------- 5. 教师横向越权（造一个遗留教师号，验证 T2026 无法操作他人） ----------
con = sqlite3.connect(DB)
con.execute("INSERT OR IGNORE INTO users(student_no,name,role,pwd_hash,enabled,created_at) "
            "VALUES('T2026X','遗留教师','teacher','x',1,?)", (int(time.time()),))
con.commit()
t2 = con.execute("SELECT id FROM users WHERE student_no='T2026X'").fetchone()[0]
con.execute("INSERT INTO trainings(title,batch,start_date,end_date,teacher_id,capacity,note,created_at) "
            "VALUES('他人培训','','','',?,10,'',?)", (t2, int(time.time())))
con.commit()
oth_training = con.execute("SELECT last_insert_rowid()").fetchone()[0]
con.close()
r = requests.put(BASE + f"/api/admin/accounts/{t2}", headers=H, json={"password": "hacked123"}, timeout=10)
check("改其他教师密码被拒 403", r.status_code == 403, r.text[:60])
r = requests.delete(BASE + f"/api/admin/accounts/{t2}", headers=H, timeout=10)
check("删其他教师账号被拒 403", r.status_code == 403, r.text[:60])
r = requests.put(BASE + f"/api/admin/trainings/{oth_training}", headers=H,
                 json={"title": "改他人培训", "capacity": 5}, timeout=10)
check("改他人培训被拒 403", r.status_code == 403, r.text[:60])
r = requests.delete(BASE + f"/api/admin/trainings/{oth_training}", headers=H, timeout=10)
check("删他人培训被拒 403", r.status_code == 403, r.text[:60])
con = sqlite3.connect(DB)
con.execute("DELETE FROM trainings WHERE id=?", (oth_training,))
con.execute("DELETE FROM users WHERE id=?", (t2,))
con.commit()
con.close()

# ---------- 6. 并发交卷幂等 ----------
for sno in ("S2026SEC",):
    accs = requests.get(BASE + "/api/admin/accounts", headers=H, timeout=10).json()["items"]
    old = [x for x in accs if x["student_no"] == sno]
    if old:
        requests.delete(BASE + f"/api/admin/accounts/{old[0]['id']}", headers=H, timeout=10)
requests.post(BASE + "/api/admin/students", headers=H,
              json={"name": "安全测试号", "student_no": "S2026SEC", "password": "123456"}, timeout=10)
st = login("S2026SEC")
SH = {"authorization": "Bearer " + st, **P}
start = requests.post(BASE + "/api/quiz/start", headers=SH, json={"kind": "daily"}, timeout=15).json()
aid, items = start["attempt_id"], start["items"]
sid = requests.get(BASE + "/api/auth/me", headers=SH, timeout=10).json()["id"]
answers = {str(it["question_id"]): "A" for it in items}


def submit_once(_):
    try:
        return requests.post(BASE + "/api/quiz/submit", headers=SH,
                             json={"attempt_id": aid, "answers": answers}, timeout=30).status_code
    except Exception:
        return -1


with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    codes = list(ex.map(submit_once, range(6)))
check("并发交卷仅一次成功（5 次被幂等闸门拦截）",
      codes.count(200) == 1 and codes.count(400) == 5, str(sorted(codes)))
con = sqlite3.connect(DB)
n_ans = con.execute("SELECT COUNT(*) FROM answers WHERE attempt_id=?", (aid,)).fetchone()[0]
n_dup = con.execute("SELECT COUNT(*) FROM (SELECT question_id FROM answers WHERE attempt_id=? "
                    "GROUP BY question_id HAVING COUNT(*)>1)", (aid,)).fetchone()[0]
con.close()
check("作答行无重复（唯一索引生效）", n_dup == 0 and n_ans == len(answers), f"{n_ans} 行 / {len(answers)} 题")

# ---------- 7. 错题复习防刷 ----------
wl = requests.get(BASE + "/api/wrong?status=active", headers=SH, timeout=10).json()
if wl["items"]:
    it = wl["items"][0]
    qid, right = it["id"], it["answer"]
    p0 = requests.get(BASE + "/api/auth/me", headers=SH, timeout=10).json()["points"]
    r = requests.post(BASE + "/api/wrong/review", headers=SH,
                      json={"question_id": qid, "answer": right}, timeout=10).json()
    p1 = requests.get(BASE + "/api/auth/me", headers=SH, timeout=10).json()["points"]
    check("未到期复习不计分（防刷）", r.get("due") is False and p1 == p0, f"due={r.get('due')} pts {p0}->{p1}")
    con = sqlite3.connect(DB)
    con.execute("UPDATE wrong_records SET due_at=? WHERE student_id=? AND question_id=?",
                (int(time.time()) - 10, sid, qid))
    con.commit()
    con.close()
    r = requests.post(BASE + "/api/wrong/review", headers=SH,
                      json={"question_id": qid, "answer": right}, timeout=10).json()
    p2 = requests.get(BASE + "/api/auth/me", headers=SH, timeout=10).json()["points"]
    check("到期复习计分 +10", r.get("due") is True and r.get("correct") == 1 and p2 == p1 + 10,
          f"due={r.get('due')} pts {p1}->{p2}")
    con = sqlite3.connect(DB)
    con.execute("UPDATE wrong_records SET correct_streak=1, due_at=? WHERE student_id=? AND question_id=?",
                (int(time.time()) - 10, sid, qid))
    con.commit()
    con.close()
    r = requests.post(BASE + "/api/wrong/review", headers=SH,
                      json={"question_id": qid, "answer": right}, timeout=10).json()
    check("连对 2 次转已掌握", r.get("status") == "mastered", str(r.get("status")))
    r = requests.post(BASE + "/api/wrong/review", headers=SH,
                      json={"question_id": qid, "answer": right}, timeout=10)
    p3 = requests.get(BASE + "/api/auth/me", headers=SH, timeout=10).json()["points"]
    check("已掌握不再接受重答（防无限刷分）", r.status_code == 404 and p3 == p2 + 10,
          f"{r.status_code} pts={p3}")
else:
    check("错题本非空（前置：交卷全选 A 应产生错题）", False, f"{len(wl['items'])} 条")

# ---------- 8. 扫描面收敛 ----------
for pth in ("/dump.sql.lz", "/backups.rar", "/core/config/databases.yml", "/docs", "/openapi.json"):
    rr = requests.get(BASE + pth, timeout=10)
    check(f"探测路径 {pth} 返回 404（不给扫描器 200）", rr.status_code == 404, str(rr.status_code))

# ---------- 9. 前端 XSS 纵深（CSP 头存在） ----------
rr = requests.get(BASE + "/", timeout=10)
csp = rr.headers.get("Content-Security-Policy", "")
check("CSP 已下发且脚本仅同源", "script-src 'self'" in csp, csp[:60])
check("Permissions-Policy 已下发", "microphone" in rr.headers.get("Permissions-Policy", ""))

# ---------- 清场 ----------
accs = requests.get(BASE + "/api/admin/accounts", headers=H, timeout=10).json()["items"]
for x in accs:
    if x["student_no"] in ("S2026SEC", "S2026WEAK", "S2026EMPTY"):
        requests.delete(BASE + f"/api/admin/accounts/{x['id']}", headers=H, timeout=10)

ok = sum(1 for _, o in results if o)
print(f"\n===== 安全加固验收: {ok}/{len(results)} 通过 =====")
sys.exit(0 if ok == len(results) else 1)
