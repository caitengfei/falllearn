# -*- coding: utf-8 -*-
"""AI 出题 / 入库 / 判卷 真实链路测试（DSH qwen3.6-27b，每步 30–120s）。"""
import sys, time, json, requests
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"

t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}).json()
H = {"authorization": "Bearer " + t["token"]}
ok = 0; n = 0
def ck(name, cond, extra=""):
    global ok, n
    n += 1
    print(("✓ " if cond else "✗ ") + name + ("  " + str(extra) if extra else ""))
    ok += 1 if cond else 0

# 1) 出题
t0 = time.time()
r = requests.post(BASE + "/api/admin/ai/generate-questions", headers=H,
                  json={"cluster_id": "five", "count": 5}, timeout=330)
ck("AI 出题（五步处置 5 题）", r.status_code == 200, f"{time.time()-t0:.0f}s")
if r.status_code == 200:
    g = r.json()
    items = g.get("items", [])
    ck("  题目数 ≥3", len(items) >= 3, f"{len(items)} 题, model={g.get('model')}, elapsed={g.get('elapsed')}s")
    bad = [i for i, it in enumerate(items) if not it.get("stem") or not it.get("answer")]
    ck("  题干/答案完整", not bad, bad[:3])
    jt = [it for it in items if it.get("qtype") == "判断"]
    if jt:
        ck("  判断选项规范", jt[0].get("options") == ["对（A）", "错（B）"], jt[0].get("options"))
    # 2) 入库
    rs = requests.post(BASE + "/api/admin/ai/questions/save", headers=H, json={"items": items}, timeout=30)
    ck("  入库 questions", rs.status_code == 200, rs.json())
    if rs.status_code == 200:
        # 验证题库规模变化：overview cards.questions
        ov = requests.get(BASE + "/api/admin/stats/overview", headers=H, timeout=30).json()
        ck("  题库规模含 AI 题", ov["cards"]["questions"] >= 1353 + len(items), ov["cards"]["questions"])

# 3) 判卷
ex = requests.get(BASE + "/api/admin/exams?status=done", headers=H, timeout=30).json()
if ex["items"]:
    att = ex["items"][0]
    t0 = time.time()
    rg = requests.post(BASE + "/api/admin/ai/grade", headers=H, json={"attempt_id": att["id"]}, timeout=330)
    ck(f"AI 判卷（attempt#{att['id']} {att['student_name']}）", rg.status_code == 200, f"{time.time()-t0:.0f}s")
    if rg.status_code == 200:
        g = rg.json()
        ck("  含规则分/AI分/差异", all(k in g for k in ("rule_score", "ai_score", "diff")),
           f"rule={g.get('rule_score')} ai={g.get('ai_score')} diff={g.get('diff')} n={g.get('n')}")
        ck("  逐题明细齐全", len(g.get("detail", [])) == g.get("n"))
        gg = requests.get(BASE + "/api/admin/ai/grades?attempt_id=" + str(att["id"]), headers=H, timeout=30).json()
        ck("  ai_grades 落库", len(gg["items"]) >= 1, f"{len(gg['items'])} 条")
else:
    print("（无已交卷，跳过判卷）")

print(f"\n===== AI 链路: {ok}/{n} 通过 =====")
sys.exit(0 if ok == n else 1)