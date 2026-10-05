# -*- coding: utf-8 -*-
"""服务器只读探针 v2：国庆小测监测数据采集（纯 SELECT，绝不写库）。
由本地 tools/trial_monitor.py 经 ssh 调用；stdout 输出单个 JSON。"""
import json
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
DB = "/opt/falllearn/backend/falllearn.db"
DEMO = ("S2026001", "S2026002", "S2026003")
today = time.strftime("%Y-%m-%d")
t0 = int(time.mktime(time.strptime(today, "%Y-%m-%d")))

d = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
d.row_factory = sqlite3.Row
out = {"probe_version": 2, "collected_at": int(time.time()), "today": today}

# ---- 国庆小测 ----
ex = d.execute("SELECT id, title, kind, config, created_at FROM exams WHERE title LIKE '%国庆%' ORDER BY id DESC").fetchone()
if not ex:
    print(json.dumps({"error": "exam not found"}, ensure_ascii=False))
    sys.exit(0)
out["exam"] = {"id": ex["id"], "title": ex["title"], "kind": ex["kind"], "created_at": ex["created_at"],
               "due_at": json.loads(ex["config"] or "{}").get("due_at")}
eid = ex["id"]

items = [dict(r) for r in d.execute(
    "SELECT ei.question_id, ei.seq, ei.score, q.stem, q.cluster_id FROM exam_items ei "
    "JOIN questions q ON q.id=ei.question_id WHERE ei.exam_id=? ORDER BY ei.seq", (eid,))]
out["items"] = items
out["max_score"] = sum(int(i["score"]) for i in items)

atts = [dict(r) for r in d.execute(
    "SELECT a.id, u.student_no, a.started_at, a.submitted_at, a.score, a.status "
    "FROM attempts a JOIN users u ON u.id=a.student_id WHERE a.exam_id=? ORDER BY a.id", (eid,))]
real = [a for a in atts if a["student_no"] not in DEMO]
out["attempts"] = {"all": len(atts), "real": len(real),
                   "done": sum(1 for a in real if a["status"] == "done"),
                   "open": sum(1 for a in real if a["status"] == "open")}
out["real_attempts"] = real

done_ids = tuple(a["id"] for a in real if a["status"] == "done")
if done_ids:
    ph = ",".join("?" * len(done_ids))
    out["per_question"] = [dict(r) for r in d.execute(
        "SELECT a.question_id, COUNT(*) n, SUM(a.correct) ok FROM answers a "
        "WHERE a.attempt_id IN (%s) GROUP BY a.question_id" % ph, done_ids)]
    out["durations_min"] = sorted(round((a["submitted_at"] - a["started_at"]) / 60.0, 1) for a in real
                                  if a["status"] == "done" and a["started_at"] and a["submitted_at"])

# ---- 学生总览（不含昵称，隐私最小化） ----
out["students_real_total"] = d.execute(
    "SELECT COUNT(*) FROM users WHERE role='student' AND enabled=1 AND student_no NOT IN (?,?,?)", DEMO).fetchone()[0]
out["students_real"] = [dict(r) for r in d.execute(
    "SELECT student_no, created_at FROM users WHERE role='student' AND enabled=1 AND student_no NOT IN (?,?,?) "
    "ORDER BY id", DEMO)]

# ---- 按天完成趋势（该小测） ----
out["done_by_day"] = [dict(r) for r in d.execute(
    "SELECT date(a.submitted_at, 'unixepoch', '+8 hours') day, COUNT(*) c FROM attempts a "
    "JOIN users u ON u.id=a.student_id WHERE a.exam_id=? AND a.status='done' AND u.student_no NOT IN (?,?,?) "
    "GROUP BY day ORDER BY day", (eid,) + DEMO)]

# ---- 平台今日活跃（真实学生） ----
q = lambda s, p=(): d.execute(s, p).fetchone()[0]
NOTIN = "AND u.student_no NOT IN (?,?,?)"
out["today_activity"] = {
    "logins": q("SELECT COUNT(DISTINCT l.sno) FROM login_audit l JOIN users u ON u.id=l.user_id "
                "WHERE l.ok=1 AND l.at>=? " + NOTIN, (t0,) + DEMO),
    "checkins": q("SELECT COUNT(*) FROM checkins c JOIN users u ON u.id=c.student_id WHERE c.date=? " + NOTIN, (today,) + DEMO),
    "ai_asks": q("SELECT COUNT(*) FROM chat_logs c JOIN users u ON u.id=c.student_id WHERE c.created_at>=? " + NOTIN, (t0,) + DEMO),
    "practice_started": q("SELECT COUNT(*) FROM attempts a JOIN users u ON u.id=a.student_id "
                          "WHERE a.started_at>=? " + NOTIN, (t0,) + DEMO),
    "wrong_active": q("SELECT COUNT(*) FROM wrong_records w JOIN users u ON u.id=w.student_id "
                      "WHERE w.status='active' " + NOTIN, DEMO),
}

# ---- 累计学习数据（真实学生，应用成效口径） ----
out["cumulative"] = {
    "practice_done_all": q("SELECT COUNT(*) FROM attempts a JOIN users u ON u.id=a.student_id "
                           "WHERE a.status='done' " + NOTIN, DEMO),
    "wrong_records_total": q("SELECT COUNT(*) FROM wrong_records w JOIN users u ON u.id=w.student_id " + NOTIN, DEMO),
    "wrong_mastered": q("SELECT COUNT(*) FROM wrong_records w JOIN users u ON u.id=w.student_id "
                        "WHERE w.status='mastered' " + NOTIN, DEMO),
    "points_total": q("SELECT COALESCE(SUM(p.delta),0) FROM points_log p JOIN users u ON u.id=p.student_id " + NOTIN, DEMO),
    "chat_total": q("SELECT COUNT(*) FROM chat_logs c JOIN users u ON u.id=c.student_id " + NOTIN, DEMO),
}

d.close()
print(json.dumps(out, ensure_ascii=False))
