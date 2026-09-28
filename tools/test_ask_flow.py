# -*- coding: utf-8 -*-
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026003", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + s["token"]}
r = requests.post(B + "/api/learn/ask", json={"question": "Morse 量表怎么判风险等级"}, headers=H, timeout=60)
print("status:", r.status_code)
print("body:", r.text[:400])
data = r.json()
sid = data.get("session_id")
log_id = data.get("log_id")
print("session_id:", repr(sid), "log_id:", repr(log_id))
# 立即轮询 status
import time
for i in range(6):
    time.sleep(3)
    rs = requests.get(f"{B}/api/learn/status?session_id={sid}&log_id={log_id}", headers=H, timeout=30)
    print(f"poll{i}:", rs.status_code, rs.text[:200])
    if rs.ok and "done" in rs.text:
        break