# -*- coding: utf-8 -*-
"""EXPERT-ux baseline check: read-only DB snapshot for reporting."""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
print("banners:")
for r in d.execute("SELECT id,title,tag,sub,link,sort,enabled FROM banners"):
    print("  ", dict(r))
print("announcements:", d.execute("SELECT COUNT(*) c FROM announcements").fetchone()["c"])
print("trainings:")
for r in d.execute("SELECT id,title,batch,capacity,teacher_id FROM trainings"):
    print("  ", dict(r))
print("enrolls:", d.execute("SELECT COUNT(*) c FROM training_enrolls").fetchone()["c"])
print("users:", [(r["student_no"], r["name"], r["role"], r["enabled"]) for r in d.execute("SELECT student_no,name,role,enabled FROM users")])
print("attempts:", d.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"])
print("questions total/AI:", d.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"],
      d.execute("SELECT COUNT(*) c FROM questions WHERE origin='AI生成'").fetchone()["c"])
print("study_events:", d.execute("SELECT COUNT(*) c FROM study_events").fetchone()["c"])
print("max user id:", d.execute("SELECT MAX(id) m FROM users").fetchone()["m"])
print("max ann id:", d.execute("SELECT MAX(id) m FROM announcements").fetchone()["m"])
print("max banner id:", d.execute("SELECT MAX(id) m FROM banners").fetchone()["m"])
print("max training id:", d.execute("SELECT MAX(id) m FROM trainings").fetchone()["m"])