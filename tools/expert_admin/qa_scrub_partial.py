# -*- coding: utf-8 -*-
"""清理 qa_crud 部分运行残留（仅删除 EXPERT-qa 前缀学生账号）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import login, req  # noqa

st, body = login("T2026")
T = body["token"]
_, stu = req("GET", "/api/admin/accounts", T)
victims = [a for a in stu["items"] if a["name"].startswith("EXPERT-qa-")]
print("victims:", [(a["id"], a["student_no"], a["name"]) for a in victims])
for a in victims:
    st, b = req("DELETE", f"/api/admin/accounts/{a['id']}", T)
    print("delete", a["student_no"], st, b)
_, stu = req("GET", "/api/admin/students", T)
print("remaining students:", [s["student_no"] for s in stu["items"]])