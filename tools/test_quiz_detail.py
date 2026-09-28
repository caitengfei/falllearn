# -*- coding: utf-8 -*-
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026002", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + s["token"]}
for aid in (1, 2):
    r = requests.get(f"{B}/api/quiz/{aid}", headers=H, timeout=10)
    body = r.text
    print(f"GET /api/quiz/{aid} as S2026002:", r.status_code, body[:200])
# 顺带看 DB 里 attempts 现状
import sqlite3
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
for row in d.execute("SELECT id, student_id, kind, item_count, submitted_at, score FROM attempts ORDER BY id"):
    print("attempt:", dict(row))