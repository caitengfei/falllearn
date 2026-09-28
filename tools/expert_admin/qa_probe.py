# -*- coding: utf-8 -*-
"""QA 专家探针：只读基线快照（不修改任何数据）"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

d = sqlite3.connect(r"file:E:/lilei/platform/backend/falllearn.db?mode=ro", uri=True)
d.row_factory = sqlite3.Row


def q(sql, args=()):
    return d.execute(sql, args).fetchall()


print("users:")
for r in q("select id,student_no,name,role,enabled from users order by id"):
    print("  ", dict(r))
print("banners:", [dict(r) for r in q("select id,title,sort,enabled from banners order by sort,id")])
print("announcements:", [dict(r) for r in q("select id,title,enabled,start_date,end_date,pinned from announcements")])
print("trainings:", [dict(r) for r in q("select id,title,batch,capacity,teacher_id from trainings")])
print("training_enrolls:", [dict(r) for r in q("select training_id,student_id,status from training_enrolls")])
print("questions total:", q("select count(*) c from questions")[0][0])
print("questions AI生成:", q("select count(*) c from questions where origin='AI生成'")[0][0])
print("attempts:", q("select count(*) c from attempts")[0][0])
print("answers:", q("select count(*) c from answers")[0][0])
print("study_events:", q("select count(*) c from study_events")[0][0])
print("settings:", [dict(r) for r in q("select * from settings")])
print("ai_grades:", q("select count(*) c from ai_grades")[0][0])
print("exams:", q("select count(*) c from exams")[0][0])