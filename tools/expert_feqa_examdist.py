# -*- coding: utf-8 -*-
import sqlite3
con = sqlite3.connect("file:E:/lilei/platform/backend/falllearn.db?mode=ro", uri=True)
for aid in (1, 2):
    rows = con.execute(
        "SELECT q.cluster_id FROM answers a JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=?",
        (aid,)).fetchall()
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"attempt {aid} 10题簇分布:", dict(c))
con.close()