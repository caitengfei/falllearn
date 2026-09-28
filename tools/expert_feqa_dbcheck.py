# -*- coding: utf-8 -*-
import sqlite3
con = sqlite3.connect("file:E:/lilei/platform/backend/falllearn.db?mode=ro", uri=True)
rows = con.execute("SELECT id, student_id, substr(question,1,30), length(answer), substr(answer,1,50), created_at FROM chat_logs").fetchall()
for r in rows:
    print(r)
print(con.execute("SELECT id, student_no, name, role FROM users").fetchall())
print("attempts:", con.execute("SELECT id, student_id, status, score FROM attempts").fetchall())
con.close()