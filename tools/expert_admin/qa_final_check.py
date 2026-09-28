# -*- coding: utf-8 -*-
"""QA 最终基线核对（只读）。"""
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import login, req  # noqa

st, body = login("T2026")
T = body["token"]
st, kb = req("GET", "/api/admin/ai/kb", T)
print("KB 文档数:", kb.get("count"), "| EXPERT-qa:", [i["path"] for i in kb["items"] if "EXPERT-qa" in i["path"]] or "无")

d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
residue = []
for t, col in (("users", "name"), ("banners", "title"), ("announcements", "title"), ("trainings", "title")):
    for r in d.execute(f"select id from {t} where {col} like 'EXPERT-qa%'"):
        residue.append((t, r["id"]))
for r in d.execute("select id from questions where stem like 'EXPERT-qa%' or source_doc like 'EXPERT-qa%'"):
    residue.append(("questions", r["id"]))
for r in d.execute("select key from settings where value like '%EXPERT-qa%'"):
    residue.append(("settings", r["key"]))
print("EXPERT-qa 残留:", residue or "无")

print("users:", [f"{r['student_no']}/{r['name']}/{r['role']}" for r in d.execute("select student_no,name,role from users order by id")])
print("banners:", d.execute("select count(*) c from banners").fetchone()["c"],
      "| announcements:", d.execute("select count(*) c from announcements").fetchone()["c"],
      "| trainings:", d.execute("select count(*) c from trainings").fetchone()["c"],
      "| enrolls:", d.execute("select count(*) c from training_enrolls").fetchone()["c"])
print("questions:", d.execute("select count(*) c from questions").fetchone()["c"],
      "| AI生成:", d.execute("select count(*) c from questions where origin='AI生成'").fetchone()["c"],
      "| attempts:", d.execute("select count(*) c from attempts").fetchone()["c"],
      "| answers:", d.execute("select count(*) c from answers").fetchone()["c"],
      "| exams:", d.execute("select count(*) c from exams").fetchone()["c"],
      "| study_events:", d.execute("select count(*) c from study_events").fetchone()["c"],
      "| ai_grades:", d.execute("select count(*) c from ai_grades").fetchone()["c"],
      "| settings:", d.execute("select count(*) c from settings").fetchone()["c"])
d.close()
print("uploads:", sorted(os.listdir(r"E:\lilei\platform\backend\uploads")))