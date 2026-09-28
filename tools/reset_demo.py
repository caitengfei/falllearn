import sys, requests
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
r = requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + t["token"]}, timeout=30)
print("reset:", r.status_code, r.text[:100])
# 验证 S2026001 基线
s = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
h = {"authorization": "Bearer " + s["token"]}
me = requests.get(BASE + "/api/auth/me", headers=h, timeout=10).json()
print("S2026001 基线:", me["points"], "分 / mastery", len(me["mastery"]), "簇")
wl = requests.get(BASE + "/api/wrong?status=active", headers=h, timeout=10).json()
lh = requests.get(BASE + "/api/learn/history", headers=h, timeout=10).json()
print("错题:", len(wl["items"]), "| 学习历史:", len(lh["items"]))