# -*- coding: utf-8 -*-
"""QA 收尾复核（带 token）：KB 文档数 + 全表 EXPERT-qa 前缀残留扫描。"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import login, req, BASE  # noqa

st, body = login("T2026")
T = body["token"]

st, kb = req("GET", "/api/admin/ai/kb", T)
print("KB 文档数:", kb.get("count"))
kb_qa = [i["path"] for i in kb["items"] if "EXPERT-qa" in i["path"]]
print("KB 中 EXPERT-qa 残留:", kb_qa or "无")

d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
print("\n== EXPERT-qa 前缀残留扫描 ==")
for r in d.execute("select id,student_no,name,role from users where name like 'EXPERT-qa%'"):
    print("  users:", dict(r))
for r in d.execute("select id,title from banners where title like 'EXPERT-qa%'"):
    print("  banners:", dict(r))
for r in d.execute("select id,title,enabled from announcements where title like 'EXPERT-qa%'"):
    print("  announcements:", dict(r))
for r in d.execute("select id,title from trainings where title like 'EXPERT-qa%'"):
    print("  trainings:", dict(r))
for r in d.execute("select id,stem from questions where stem like 'EXPERT-qa%' or source_doc like 'EXPERT-qa%'"):
    print("  questions:", dict(r))
for r in d.execute("select * from settings where value like '%EXPERT-qa%'"):
    print("  settings:", dict(r))
d.execute  # no-op
print("  users 全表:", [r["student_no"] + "/" + r["name"] + "/" + r["role"] for r in d.execute("select student_no,name,role from users order by id")])
print("  settings 全表:", [dict(r) for r in d.execute("select * from settings")])
print("  announcements 全表:", [dict(r) for r in d.execute("select id,title,enabled from announcements order by id")])
print("  trainings 全表:", [dict(r) for r in d.execute("select id,title from trainings order by id")])
d.close()

import os
print("\nuploads 目录:", sorted(os.listdir(r"E:\lilei\platform\backend\uploads")))