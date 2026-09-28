# -*- coding: utf-8 -*-
"""验证：学习流结束后立即 quiz/start 是否变慢（服务端阻塞）。"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

B = "http://127.0.0.1:8010"
t = requests.post(B + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
TH = {"authorization": "Bearer " + t["token"]}
r = requests.post(B + "/api/admin/reset-demo", json={}, headers=TH, timeout=30)
assert r.ok
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + s["token"]}

# 1. 基线：干净状态下 quiz/start 耗时
t0 = time.time()
r = requests.post(B + "/api/quiz/start", headers=H, timeout=60)
print(f"baseline quiz/start: {r.status_code} {(time.time()-t0)*1000:.0f}ms")

# 2. 学习流：ask → 轮询到澄清卡 → answer → 轮询到 done
t0 = time.time()
ra = requests.post(B + "/api/learn/ask", json={"question": "老年人跌倒"}, headers=H, timeout=60)
print("ask:", ra.status_code, ra.text[:120])
sid, log_id = ra.json()["session_id"], ra.json()["log_id"]
question = None
t_q = None
while time.time() - t0 < 150:
    rs = requests.get(f"{B}/api/learn/status?session_id={sid}&log_id={log_id}", headers=H, timeout=30)
    d = rs.json()
    if d.get("status") == "question":
        question = d["question"]
        t_q = time.time()
        break
    if d.get("status") == "done":
        print("direct answer (no question)")
        break
    time.sleep(3)
print(f"learn state at +{time.time()-t0:.0f}s (question keys: {list(question.keys()) if question else 'None'})", flush=True)
if question:
    t1 = time.time()
    ra2 = requests.post(B + "/api/learn/answer", json={"log_id": log_id, "option_index": 0}, headers=H, timeout=120)
    print(f"answer: {ra2.status_code} {(time.time()-t1)*1000:.0f}ms", flush=True)
    t1 = time.time()
    while time.time() - t1 < 600:
        rs = requests.get(f"{B}/api/learn/status?session_id={sid}&log_id={log_id}", headers=H, timeout=30)
        d = rs.json()
        if d.get("status") == "done":
            break
        time.sleep(3)
    print(f"learn done at +{time.time()-t1:.0f}s after answer", flush=True)

# 3. 关键测量：学习流刚结束后立即 quiz/start
t2 = time.time()
r = requests.post(B + "/api/quiz/start", headers=H, timeout=120)
print(f"POST-LEARN quiz/start: {r.status_code} 耗时 {time.time()-t2:.1f}s", flush=True)
# 4. 紧接着再测一次
t3 = time.time()
r = requests.post(B + "/api/quiz/start", headers=H, timeout=120)
print(f"followup quiz/start: {r.status_code} 耗时 {time.time()-t3:.1f}s", flush=True)