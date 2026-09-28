# -*- coding: utf-8 -*-
"""收尾核验：线上库只读快照（确认未污染基线）。"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
checks = {
    "students": "SELECT COUNT(*) c FROM users WHERE role='student'",
    "teachers": "SELECT COUNT(*) c FROM users WHERE role='teacher'",
    "questions": "SELECT COUNT(*) c FROM questions",
    "ai_origin_questions": "SELECT COUNT(*) c FROM questions WHERE origin='AI生成'",
    "banners": "SELECT COUNT(*) c FROM banners",
    "announcements": "SELECT COUNT(*) c FROM announcements",
    "trainings": "SELECT COUNT(*) c FROM trainings",
    "training_enrolls": "SELECT COUNT(*) c FROM training_enrolls",
    "attempts": "SELECT COUNT(*) c FROM attempts",
    "study_events": "SELECT COUNT(*) c FROM study_events",
    "synthetic_leak": "SELECT COUNT(*) c FROM users WHERE student_no LIKE 'S20261%' OR name LIKE '合成%' OR student_no LIKE 'EXPERT%'",
}
for k, sql in checks.items():
    print(f"{k:22s} = {d.execute(sql).fetchone()['c']}")
d.close()