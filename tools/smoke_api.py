# -*- coding: utf-8 -*-
"""康养智行 API 冒烟测试：登录/签到/开卷/交卷/错题/复习/榜单/教师看板"""
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"

print("health:", requests.get(B + "/api/health", timeout=5).json())
r = requests.get(B + "/", timeout=5)
print("static /:", r.status_code, "app div:", 'id="app"' in r.text)

d = requests.post(B + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
print("login:", d.get("user"))
H = {"authorization": "Bearer " + d["token"]}
print("me:", requests.get(B + "/api/auth/me", headers=H, timeout=5).json())
print("today:", requests.get(B + "/api/game/today", headers=H, timeout=5).json())
print("checkin:", requests.post(B + "/api/game/checkin", json={}, headers=H, timeout=5).json())

r = requests.post(B + "/api/quiz/start", headers=H, timeout=10).json()
print("quiz start: attempt=", r.get("attempt_id"), "items=", len(r.get("items", [])))
for it in r["items"][:3]:
    print("   item:", it["type"], it["cluster"], it["stem"][:40])

ans = {}
for it in r["items"]:
    ans[str(it["question_id"])] = "ABCD" if it["type"] == "多选" else "A"
res = requests.post(B + "/api/quiz/submit", json={"attempt_id": r["attempt_id"], "answers": ans}, headers=H, timeout=15).json()
print("submit: score=", res.get("score"), "detail=", len(res.get("detail", [])), "per_cluster=", res.get("per_cluster"))

w = requests.get(B + "/api/wrong?status=active", headers=H, timeout=5).json()
print("wrong active:", len(w.get("items", [])), "due=", w.get("due_count"))
if w["items"]:
    it = w["items"][0]
    rv = requests.post(B + "/api/wrong/review", json={"question_id": it["id"], "answer": it["answer"]}, headers=H, timeout=10).json()
    print("review:", rv)

print("points:", requests.get(B + "/api/game/points", headers=H, timeout=5).json()["total"])
lb = requests.get(B + "/api/game/leaderboard", headers=H, timeout=5).json()
print("leaderboard my rank:", lb["my_rank_points"])
print("badges:", [(b["name"], b["earned"]) for b in requests.get(B + "/api/game/badges", headers=H, timeout=5).json()])

td = requests.post(B + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
TH = {"authorization": "Bearer " + td["token"]}
dash = requests.get(B + "/api/admin/dashboard", headers=TH, timeout=10).json()
print("admin students:", len(dash["students"]), "weak:", [(x["name"], x["rate"]) for x in dash["weak_clusters"][:3]])

# 学生越权访问教师接口
try:
    r2 = requests.get(B + "/api/admin/dashboard", headers=H, timeout=5)
    print("越权测试:", r2.status_code, "(应 403)")
except Exception as e:
    print("越权测试 err:", e)
print("SMOKE DONE")