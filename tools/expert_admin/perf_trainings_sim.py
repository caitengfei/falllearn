# -*- coding: utf-8 -*-
"""在 30 学生模拟库上复现 trainings_list / stats_trainings 的查询序列（计时+计数）。"""
import sqlite3, sys, time, statistics
sys.stdout.reconfigure(encoding="utf-8")
DST = r"E:\lilei\platform\tools\expert_admin\perf_sim.db"
d = sqlite3.connect(DST)
d.row_factory = sqlite3.Row

def n_queries(fn):
    c = [0]
    def tr(op):
        op = op.strip().lower()
        if op.startswith(("select", "insert", "update", "delete")):
            c[0] += 1
    d.set_trace_callback(tr)
    try: fn(d)
    finally: d.set_trace_callback(None)
    return c[0]

def training_row(d, r):
    d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE training_id=?", (r["id"],)).fetchone()
    d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE training_id=? AND status='done'", (r["id"],)).fetchone()
    d.execute("SELECT name FROM users WHERE id=?", (r["teacher_id"],)).fetchone()

def trainings_list(d):
    rows = d.execute("SELECT * FROM trainings ORDER BY id DESC").fetchall()
    for r in rows:
        training_row(d, r)
    for r in rows:
        d.execute("SELECT te.student_id, u.student_no, u.name, te.status FROM training_enrolls te "
                  "JOIN users u ON u.id=te.student_id WHERE te.training_id=? ORDER BY u.id", (r["id"],)).fetchall()

def stats_trainings(d):
    for r in d.execute("SELECT * FROM trainings ORDER BY id DESC").fetchall():
        training_row(d, r)
    for r in d.execute("SELECT id FROM users WHERE role='student' AND enabled=1").fetchall():
        d.execute("SELECT COALESCE(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END),0) done, COUNT(*) n "
                  "FROM training_enrolls WHERE student_id=?", (r["id"],)).fetchone()
        d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?", (r["id"],)).fetchone()
        d.execute("SELECT COUNT(*) c FROM attempts WHERE student_id=? AND status='done'", (r["id"],)).fetchone()
        d.execute("SELECT COUNT(*) c FROM chat_logs WHERE student_id=? AND answer!=''", (r["id"],)).fetchone()
    for r in d.execute("SELECT id FROM users WHERE role='teacher' AND enabled=1").fetchall():
        d.execute("SELECT COUNT(*) c FROM trainings WHERE teacher_id=?", (r["id"],)).fetchone()
        d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()

def exams_list(d):
    d.execute("SELECT a.id, a.student_id, u.student_no, u.name, e.title, e.kind, a.started_at, a.submitted_at, a.score, a.status "
              "FROM attempts a JOIN users u ON u.id=a.student_id LEFT JOIN exams e ON e.id=a.exam_id "
              "ORDER BY a.id DESC LIMIT 200").fetchall()

for name, fn in [("trainings_list", trainings_list), ("stats_trainings", stats_trainings), ("exams_list", exams_list)]:
    q = n_queries(fn)
    ts = []
    for _ in range(5):
        t0 = time.perf_counter(); fn(d); ts.append((time.perf_counter() - t0) * 1000)
    print(f"{name:18s} queries={q:4d} best={min(ts):.2f}ms mean={statistics.mean(ts):.2f}ms")
d.close()