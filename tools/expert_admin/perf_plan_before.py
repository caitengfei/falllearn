# -*- coding: utf-8 -*-
"""取「现有索引」下的 query plan（对照证据）。"""
import sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\lilei\platform\backend\falllearn.db"
DST = r"E:\lilei\platform\tools\expert_admin\perf_plan_before.db"
import os
if os.path.exists(DST):
    os.remove(DST)
src = sqlite3.connect(SRC)
src.execute("VACUUM INTO ?", (DST,))
src.close()
d = sqlite3.connect(DST)
d.row_factory = sqlite3.Row
print("live indexes:")
for t in ("points_log", "chat_logs", "study_events", "training_enrolls", "attempts", "mastery", "answers", "checkins", "questions", "users"):
    idx = [r[1] for r in d.execute(f"PRAGMA index_list({t})") if r[1]]
    print(f"  {t}: {idx}")
qs = [
    ("points_log_7d_trend", "SELECT COALESCE(SUM(delta),0) s FROM points_log WHERE created_at>=? AND created_at<?"),
    ("chat_logs_7d_asks", "SELECT COUNT(*) c FROM chat_logs WHERE created_at>=? AND created_at<? AND answer!=''"),
    ("enrolls_by_student", "SELECT COUNT(*) c FROM training_enrolls WHERE student_id=?"),
    ("attempts_status_done", "SELECT COUNT(*) c FROM attempts WHERE status='done'"),
    ("mastery_by_cluster", "SELECT COALESCE(AVG(level),0) m FROM mastery WHERE cluster_id=?"),
    ("weak_join_cluster", "SELECT COUNT(*) n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.cluster_id=? AND a.graded_by LIKE 'rules%'"),
    ("checkins_by_date", "SELECT student_id FROM checkins WHERE date>=?"),
    ("study_hours_student", "SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?"),
]
for name, sql in qs:
    params = (1,) * sql.count("?")
    plan = " | ".join(r[3] for r in d.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall())
    print(f"PLAN {name:24s} {plan}")
d.close()