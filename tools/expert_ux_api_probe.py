# -*- coding: utf-8 -*-
"""只读 API 探测：三个学生账号的学习历史条数（判断谁还是空白）"""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"

def req(path, token=None, body=None):
    r = urllib.request.Request(BASE + path, method="POST" if body else "GET")
    r.add_header("content-type", "application/json")
    if token:
        r.add_header("authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body else None
    with urllib.request.urlopen(r, data, timeout=20) as resp:
        return json.loads(resp.read().decode())

for sno in ["S2026001", "S2026002", "S2026003"]:
    try:
        t = req("/api/auth/login", body={"student_no": sno, "password": "123456"})
        h = req("/api/learn/history", token=t["token"])
        items = h.get("items", [])
        print(sno, "learn_history_count =", len(items), flush=True)
        for x in items[:3]:
            print("   -", x.get("question", "")[:40], "at=", x.get("at"), flush=True)
        w = req("/api/wrong?status=active", token=t["token"])
        print(sno, "active_wrong =", len(w.get("items", [])), "due =", w.get("due_count"), flush=True)
        me = req("/api/auth/me", token=t["token"])
        print(sno, "mastery =", me.get("mastery"), "points =", me.get("points"), flush=True)
    except Exception as e:
        print(sno, "ERROR", str(e)[:200], flush=True)
print("DONE api-probe", flush=True)