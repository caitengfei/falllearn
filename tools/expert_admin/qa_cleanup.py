# -*- coding: utf-8 -*-
"""QA 专家 · 收尾清理：删除全部 EXPERT-qa- 数据并验证基线恢复。
- API 删除：培训 / 公告 / 学生账号（级联）
- 孤儿 exams/exam_items（accounts_delete 不清理，属 QA-13 证据）：先取证，再直接清库（仅我创建的行）
- 删除 uploads 下我上传的文件
- 最终基线核对（与 qa_probe 相同口径）
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import login, req  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"E:\lilei\platform\backend\falllearn.db"
state = json.load(open(os.path.join(HERE, "qa_crud_state.json"), encoding="utf-8"))
st, body = login("T2026")
T = body["token"]

print("== 1. API 删除培训/公告 ==")
for tid in state["trainings_to_delete"]:
    s, b = req("DELETE", f"/api/admin/trainings/{tid}", T)
    print(f"  delete training {tid} -> {s} {b}")
for nid in state["announcements_to_delete"]:
    s, b = req("DELETE", f"/api/admin/announcements/{nid}", T)
    print(f"  delete announcement {nid} -> {s} {b}")

print("== 2. 取证：孤儿 exams（accounts_delete 不清理） ==")
d = sqlite3.connect(DB)
d.row_factory = sqlite3.Row
orphans_before = [dict(r) for r in d.execute(
    "SELECT id, title, kind, created_by FROM exams WHERE created_by IN (5,6)")]
orphans_items = d.execute(
    "SELECT COUNT(*) c FROM exam_items WHERE exam_id IN (SELECT id FROM exams WHERE created_by IN (5,6))").fetchone()[0]
print(f"  删除学生前: 孤儿 exams={orphans_before} exam_items={orphans_items}")

print("== 3. API 删除学生账号（级联清理学习痕迹） ==")
for uid in state["students_to_delete"]:
    s, b = req("DELETE", f"/api/admin/accounts/{uid}", T)
    print(f"  delete account {uid} -> {s} {b}")

orphans_after = [dict(r) for r in d.execute(
    "SELECT id, title, kind, created_by FROM exams WHERE created_by IN (5,6)")]
print(f"  删除学生后: 孤儿 exams 仍在={orphans_after} (QA-13 证据)")

print("== 4. 清理孤儿 exams/exam_items（仅我创建的 created_by IN (5,6)） ==")
d.execute("DELETE FROM exam_items WHERE exam_id IN (SELECT id FROM exams WHERE created_by IN (5,6))")
d.execute("DELETE FROM exams WHERE created_by IN (5,6)")
d.commit()
print(f"  清理后 exams={d.execute('SELECT COUNT(*) c FROM exams').fetchone()[0]} "
      f"exam_items={d.execute('SELECT COUNT(*) c FROM exam_items').fetchone()[0]}")

print("== 5. 删除 uploads 下我上传的文件 ==")
urls = list(state["uploads_to_delete"])
txt_f = os.path.join(HERE, "qa_upload_txt.txt")
if os.path.exists(txt_f):
    u = open(txt_f).read().strip()
    if u:
        urls.append(u)
up_dir = r"E:\lilei\platform\backend\uploads"
for u in urls:
    name = os.path.basename(u)
    p = os.path.join(up_dir, name)
    if os.path.exists(p):
        os.remove(p)
        print(f"  removed {name}")
left = os.listdir(up_dir) if os.path.isdir(up_dir) else []
print(f"  uploads 剩余文件: {left}")

d.close()

print("== 6. 最终基线核对 ==")
d = sqlite3.connect(DB)
d.row_factory = sqlite3.Row
users = [dict(r) for r in d.execute("select id,student_no,name,role,enabled from users order by id")]
print("  users:", [(u["student_no"], u["name"], u["role"]) for u in users])
print("  banners:", d.execute("select count(*) c from banners").fetchone()["c"],
      [r["id"] for r in d.execute("select id from banners order by id")])
print("  announcements:", d.execute("select count(*) c from announcements").fetchone()["c"])
print("  trainings:", [dict(r)["id"] for r in d.execute("select id,title from trainings")],
      "enrolls:", d.execute("select count(*) c from training_enrolls").fetchone()["c"])
print("  questions:", d.execute("select count(*) c from questions").fetchone()["c"],
      "AI生成:", d.execute("select count(*) c from questions where origin='AI生成'").fetchone()["c"])
print("  attempts:", d.execute("select count(*) c from attempts").fetchone()["c"],
      "answers:", d.execute("select count(*) c from answers").fetchone()["c"],
      "ai_grades:", d.execute("select count(*) c from ai_grades").fetchone()["c"],
      "study_events:", d.execute("select count(*) c from study_events").fetchone()["c"],
      "exams:", d.execute("select count(*) c from exams").fetchone()["c"],
      "exam_items:", d.execute("select count(*) c from exam_items").fetchone()["c"])
print("  settings:", d.execute("select count(*) c from settings").fetchone()["c"])
d.close()
import urllib.request
kb = json.load(urllib.request.urlopen(
    "http://127.0.0.1:8010/api/admin/ai/kb", timeout=30))
print("  KB 文档数:", kb.get("count"))