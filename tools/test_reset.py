# -*- coding: utf-8 -*-
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
t = requests.post(B + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + t["token"]}
r = requests.post(B + "/api/admin/reset-demo", json={}, headers=H, timeout=30)
print("reset:", r.status_code, r.json())
s1 = requests.post(B + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
me1 = requests.get(B + "/api/auth/me", headers={"authorization": "Bearer " + s1["token"]}, timeout=5).json()
print("S2026001 me: points=", me1["points"], "mastery=", me1["mastery"])
s2 = requests.post(B + "/api/auth/login", json={"student_no": "S2026002", "password": "123456"}, timeout=10).json()
me2 = requests.get(B + "/api/auth/me", headers={"authorization": "Bearer " + s2["token"]}, timeout=5).json()
print("S2026002 me: points=", me2["points"], "mastery=", me2["mastery"])