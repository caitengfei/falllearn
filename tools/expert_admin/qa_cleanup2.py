# -*- coding:utf-8 -*-
"""QA 收尾补充：删除我（EXPERT-qa）遗留的 3 条过期公告 + 1 个孤儿上传文件。"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import login, req  # noqa

st, body = login("T2026")
T = body["token"]
_, adm = req("GET", "/api/admin/announcements", T)
mine = [a["id"] for a in adm["items"] if a["title"].startswith("EXPERT-qa-")]
print("待删公告(仅 EXPERT-qa 前缀):", mine)
for nid in mine:
    s, b = req("DELETE", f"/api/admin/announcements/{nid}", T)
    print(f"  delete announcement {nid} -> {s} {b}")

# 孤儿上传文件：qa_errors 首次(崩溃)运行的 .txt-as-png 上传
p = r"E:\lilei\platform\backend\uploads\banner-1790570109-7efad3.png"
if os.path.exists(p):
    sz = os.path.getsize(p)
    os.remove(p)
    print(f"removed orphan upload {os.path.basename(p)} ({sz} bytes)")

d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
print("announcements 剩余:", [dict(r) for r in d.execute("select id,title from announcements")])
print("EXPERT-qa 残留(全表):", [dict(r) for r in d.execute(
    "select id from users where name like 'EXPERT-qa%'") +
    [dict(r) for r in d.execute("select id from banners where title like 'EXPERT-qa%'")] +
    [dict(r) for r in d.execute("select id from announcements where title like 'EXPERT-qa%'")] +
    [dict(r) for r in d.execute("select id from trainings where title like 'EXPERT-qa%'")]])
d.close()
print("uploads 目录:", sorted(os.listdir(r"E:\lilei\platform\backend\uploads")))