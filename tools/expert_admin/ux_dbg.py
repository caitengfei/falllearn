# -*- coding: utf-8 -*-
import sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
rows = d.execute("SELECT id, title, summary, created_at, pinned, enabled FROM announcements ORDER BY id").fetchall()
for r in rows:
    print(dict(r), "age_s=", round(time.time() - r["created_at"], 1))
print("banners:", [dict(r) for r in d.execute("SELECT id, title, sort, enabled FROM banners ORDER BY sort, id")])