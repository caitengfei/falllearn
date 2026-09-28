# -*- coding: utf-8 -*-
"""清理 E2E 造的重复「E2E 公告」，保留干净演示数据。"""
import sys, requests
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}).json()
H = {"authorization": "Bearer " + t["token"]}
items = requests.get(BASE + "/api/admin/announcements", headers=H).json()["items"]
removed = 0
for a in items:
    if a["title"].startswith("E2E 公告"):
        r = requests.delete(f"{BASE}/api/admin/announcements/{a['id']}", headers=H)
        if r.ok:
            removed += 1
            print("删除", a["title"])
print(f"===== 清理完成：删除 {removed} 条 E2E 公告，剩余 {len(items)-removed} 条 =====")