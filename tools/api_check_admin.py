# -*- coding: utf-8 -*-
"""管理后台 API 冒烟（教师 T2026）：32 项检查（含教师布置闭环 6 项、流式端点鉴权、知识库 4 项）。"""
import sys, time, requests
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + t["token"]}
P = {"Content-Type": "application/json"}
results = []

def check(name, ok, extra=""):
    results.append((name, ok))
    print(("✓ " if ok else "✗ ") + name, extra)

# 1-4 轮播
r = requests.get(BASE + "/api/admin/banners", headers=H, timeout=10).json()
check("轮播列表 4 条（种子）", len(r["items"]) == 4, str(len(r["items"])))
r = requests.get(BASE + "/api/content/banners", timeout=10).json()
check("公开轮播接口", len(r["items"]) == 4)
bid = r["items"][0]["id"]
r = requests.put(BASE + f"/api/admin/banners/{bid}", headers=H, json={"title": "测试卡", "tag": "t", "sub": "s", "image": "", "link": "/", "sort": 0, "enabled": 1}, timeout=10).json()
check("轮播更新", r.get("ok"))
r = requests.put(BASE + f"/api/admin/banners/{bid}", headers=H, json={"title": "老年人跌倒 · 预防与应急处置", "tag": "世赛 × 省赛 GZ063 双对标", "sub": "岗课赛证融通 · 把技能学成肌肉记忆", "image": "", "link": "/", "sort": 0, "enabled": 1}, timeout=10).json()
check("轮播还原", r.get("ok"))

# 5-7 公告
r = requests.post(BASE + "/api/admin/announcements", headers=H, json={"title": "课程预告·秋季实训", "summary": "10 月 12 日 14:00 实训楼 203", "content": "请携带实训服与考核脚本", "start_date": "2026-09-28", "end_date": "2026-10-15", "pinned": 1, "enabled": 1}, timeout=10).json()
check("公告创建", r.get("ok") and r.get("id"))
nid = r["id"]
r = requests.get(BASE + "/api/content/announcements", timeout=10).json()
check("公开公告接口", any(x["id"] == nid for x in r["items"]))
r = requests.delete(BASE + f"/api/admin/announcements/{nid}", headers=H, timeout=10).json()
check("公告删除", r.get("ok"))

# 8-10 考试管理
r = requests.get(BASE + "/api/admin/exams?status=done", headers=H, timeout=10).json()
check("考试记录列表", "items" in r, f"{len(r.get('items', []))} 条")
if r["items"]:
    aid = r["items"][0]["id"]
    d = requests.get(BASE + f"/api/admin/exams/{aid}", headers=H, timeout=10).json()
    check("考试逐题明细", len(d["items"]) == 10 and "attempt" in d)
r = requests.get(BASE + "/api/admin/exams/export", headers=H, timeout=15)
check("考试 CSV 导出", r.status_code == 200 and "学号" in r.text[:50])

# 11-14 学生/账号
r = requests.get(BASE + "/api/admin/students", headers=H, timeout=10).json()
check("学生列表（含学时/掌握度）", len(r["items"]) == 3 and "hours" in r["items"][0], str(len(r["items"])))
r = requests.post(BASE + "/api/admin/students", headers=H, json={"name": "测试同学", "password": "123456"}, timeout=10).json()
check("学生创建（自动学号）", r.get("ok") and r.get("student_no", "").startswith("S2026"), r.get("student_no", ""))
new_no = r.get("student_no")
r = requests.put(BASE + f"/api/admin/accounts/" + str([x for x in requests.get(BASE + '/api/admin/accounts', headers=H, timeout=10).json()['items'] if x['student_no'] == new_no][0]['id']), headers=H, json={"enabled": 0, "password": ""}, timeout=10).json()
check("账号停用", r.get("ok"))
# QA-1 修复后：停用账号在登录入口即 403（不再发 token）
lr = requests.post(BASE + "/api/auth/login", json={"student_no": new_no, "password": "123456"}, timeout=10)
check("停用账号登录即 403", lr.status_code == 403 and "停用" in lr.json().get("detail", ""),
      f"{lr.status_code} {lr.json().get('detail', '')}")
# 清理测试账号（保持 3 个演示学生）
accs = requests.get(BASE + "/api/admin/accounts", headers=H, timeout=10).json()["items"]
tuid = [x for x in accs if x["student_no"] == new_no][0]["id"]
r = requests.delete(BASE + f"/api/admin/accounts/{tuid}", headers=H, timeout=10).json()
check("账号删除（清场）", r.get("ok"))

# 15-17 培训
r = requests.post(BASE + "/api/admin/trainings", headers=H, json={"title": "跌倒应急演练班·第 1 期", "batch": "2026 秋", "start_date": "2026-10-08", "end_date": "2026-10-30", "capacity": 30, "note": "含 12 分钟模拟考考核", "student_ids": [1, 2, 3]}, timeout=10).json()
check("培训创建（含报名）", r.get("ok"), "id=" + str(r.get("id")))
tid = r["id"]
r = requests.post(BASE + f"/api/admin/trainings/{tid}/students/1/status", headers=H, json={"status": "done"}, timeout=10).json()
check("培训完成状态", r.get("ok"))
r = requests.get(BASE + "/api/admin/stats/trainings", headers=H, timeout=10).json()
tr = [x for x in r["trainings"] if x["id"] == tid][0]
# CT-12：完成率统一为整百分比（round(1/3*100)=33）
check("培训统计（3 报 1 完 33%）", tr["enrolled"] == 3 and tr["done"] == 1 and tr["rate"] == 33, f'{tr["enrolled"]}/{tr["done"]}/{tr["rate"]}')

# 18 数据大屏
r = requests.get(BASE + "/api/admin/stats/overview", headers=H, timeout=10).json()
ok = (r["cards"]["students"] >= 3 and len(r["trend"]) == 7 and len(r["clusters"]) == 6
      and r["rank_points"] and r["hours"] and "active" in r)
check("数据大屏 overview", ok, f'cards={r["cards"]}')

# 19 AI 模型目录（直连模式=直连模型；DSH 模式=实时目录）
dr = requests.get(BASE + "/api/admin/ai/direct", headers=H, timeout=10).json()
r = requests.get(BASE + "/api/admin/ai/models", headers=H, timeout=60).json()
ids = [m["id"] for g in r.get("items", []) for m in g.get("models", [])]
if dr.get("configured"):
    check("AI 模型目录（直连模式）", any("deepseek" in i for i in ids), str(ids))
else:
    check("AI 模型目录（含 deepseek/qwen）", any("deepseek" in i for i in ids) and any("qwen" in i for i in ids), str(ids))

# 20 知识库列表
r = requests.get(BASE + "/api/admin/ai/kb", headers=H, timeout=10).json()
check("知识库列表 46 文档", r["count"] >= 46, str(r["count"]))

# 21-26 教师布置闭环（教师建卷 → 学生开考/交卷 → 完成统计 → 重复开考拦截 → 删除清场）
r = requests.post(BASE + "/api/admin/assignments", headers=H, json={"title": "回归测试·五步处置专项", "clusters": ["five"], "n": 5, "minutes": 10, "due_days": 7}, timeout=10).json()
check("布置创建（教师）", r.get("ok") and r.get("n") == 5, "exam_id=" + str(r.get("exam_id")))
asg_id = r.get("exam_id")
st = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026003", "password": "123456"}, timeout=10).json()
SH = {"authorization": "Bearer " + st["token"]}
r = requests.post(BASE + "/api/quiz/start", headers=SH, json={"kind": "daily", "exam_id": asg_id}, timeout=10).json()
check("学生开考布置卷", r.get("count") == 5, "items=" + str(r.get("count")))
att_id = r.get("attempt_id")
ans = {str(it["question_id"]): "A" for it in r.get("items", [])}
r = requests.post(BASE + "/api/quiz/submit", headers=SH, json={"attempt_id": att_id, "answers": ans}, timeout=10).json()
check("布置卷交卷判分", isinstance(r.get("score"), int) and r["score"] >= 0, "score=" + str(r.get("score")))
r = requests.get(BASE + "/api/admin/assignments", headers=H, timeout=10).json()
asg = [x for x in r.get("items", []) if x["exam_id"] == asg_id]
check("布置完成统计", bool(asg) and asg[0]["done"] >= 1, "done=" + str(asg[0]["done"] if asg else "-"))
r2 = requests.post(BASE + "/api/quiz/start", headers=SH, json={"kind": "daily", "exam_id": asg_id}, timeout=10)
check("重复开考拦截", r2.status_code == 400, str(r2.status_code))
r = requests.delete(BASE + f"/api/admin/assignments/{asg_id}", headers=H, timeout=10).json()
check("布置删除（清场）", r.get("ok"))

# 27 流式端点鉴权（SSE /api/learn/stream：无 token 401，不触 AI）
r = requests.get(BASE + "/api/learn/stream?session_id=x&log_id=1", timeout=10)
check("流式端点鉴权", r.status_code == 401, str(r.status_code))

# 28-31 知识库（学生端 /api/kb：目录/检索/原文/防穿越）
r = requests.get(BASE + "/api/kb/search", headers=H, timeout=15).json()
check("知识库目录 46 份", r.get("total") == 46, str(r.get("total")))
r = requests.get(BASE + "/api/kb/search", params={"q": "Morse 量表"}, headers=H, timeout=15).json()
check("知识库检索", r.get("total", 0) >= 3, f'{r.get("total")} 条')
r = requests.get(BASE + "/api/kb/doc", params={"path": "02-课/知识点梳理.md"}, headers=H, timeout=15)
check("知识库读原文", r.status_code == 200 and len(r.json().get("content", "")) > 500)
r = requests.get(BASE + "/api/kb/doc", params={"path": "../../backend/app/main.py"}, headers=H, timeout=10)
check("知识库路径穿越拦截", r.status_code in (400, 404), str(r.status_code))

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n===== 管理后台 API: {len(results) - n_fail}/{len(results)} 通过 =====")
sys.exit(1 if n_fail else 0)