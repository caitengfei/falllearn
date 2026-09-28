# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
print("students:")
for r in d.execute("SELECT student_no, name, role, created_at FROM users WHERE role='student' ORDER BY id"):
    print("  ", r["student_no"], r["name"], r["created_at"])
print("announcements titles:")
for r in d.execute("SELECT id, title FROM announcements ORDER BY id"):
    print("  ", r["id"], r["title"])
print("trainings titles:")
for r in d.execute("SELECT id, title, batch FROM trainings ORDER BY id"):
    print("  ", r["id"], r["title"], r["batch"])
print("attempts:")
for r in d.execute("SELECT id, student_id, exam_id, status FROM attempts ORDER BY id"):
    print("  ", dict(r))
# 任何 EXPERT-perf 痕迹？
print("EXPERT-perf anywhere in users:", d.execute("SELECT COUNT(*) c FROM users WHERE student_no LIKE '%EXPERT-perf%' OR name LIKE '%EXPERT-perf%'").fetchone()["c"])
d.close()