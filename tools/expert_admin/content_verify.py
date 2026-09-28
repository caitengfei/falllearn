# -*- coding: utf-8 -*-
"""内容专家(content) · 补充验证：422 alert 渲染 / sort 清空 422 / 题库各簇实际题数 vs 前端硬编码"""
import json, os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = {}

# 1) JS 语义：FastAPI 422 的 detail 数组经 new Error(array).message 渲染成什么
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    pg = b.new_page()
    pg.goto("about:blank")
    OUT["js_error_array_render"] = pg.evaluate(
        "(() => { const detail=[{type:'missing',loc:['body','sort'],'msg':'Input should be a valid integer','input':null}]; return new Error(detail || 'x').message })()")
    b.close()
print("js_error_array_render =", OUT["js_error_array_render"])

# 2) UI 路径：清空排序数字 → NaN → JSON null → 422（用自建 banner，随后删除）
S = requests.Session()
TOK = S.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}).json()["token"]
H = {"authorization": f"Bearer {TOK}"}
bid = S.post(BASE + "/api/admin/banners", headers=H, json={"title": "EXPERT-content-sort测试", "link": "/", "sort": 99}).json()["id"]
r = S.put(f"{BASE}/api/admin/banners/{bid}", headers=H, json={"title": "EXPERT-content-sort测试", "tag": "", "sub": "", "image": "", "link": "/", "sort": None, "enabled": 1})
OUT["sort_null_422"] = {"status": r.status_code, "body": r.json()}
print("sort_null_422 =", OUT["sort_null_422"])
S.delete(f"{BASE}/api/admin/banners/{bid}", headers=H)

# 3) 题库各簇实际题数 vs 前端硬编码 CLUSTER_QCOUNT
DB = r"E:\lilei\platform\backend\falllearn.db"
d = sqlite3.connect(DB)
rows = dict(d.execute("SELECT cluster_id, COUNT(*) FROM questions GROUP BY cluster_id").fetchall())
total = d.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
ai_q = d.execute("SELECT cluster_id, COUNT(*) FROM questions WHERE origin='AI生成' GROUP BY cluster_id").fetchall()
d.close()
HARDCODED = {"morse": 20, "env": 58, "five": 79, "fracture": 9, "record": 35, "cpr": 2, "general": 1150}
OUT["cluster_counts_db"] = rows
OUT["cluster_counts_hardcoded"] = HARDCODED
OUT["cluster_diff"] = {k: {"db": rows.get(k, 0), "ui": HARDCODED[k], "stale": rows.get(k, 0) != HARDCODED[k]} for k in HARDCODED}
OUT["questions_total_db"] = total
OUT["ai_generated_by_cluster"] = ai_q
print(json.dumps(OUT, ensure_ascii=False, indent=1))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_verify_results.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)