# -*- coding: utf-8 -*-
import json
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
fails = []


def check(name, cond, extra=""):
    print(("  ✓ " if cond else "  ✗ ") + name, extra, flush=True)
    if not cond:
        fails.append(name)


# 自重置：干净基线
_tt = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
_rr = requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + _tt["token"]}, timeout=30)
assert _rr.ok, f"reset 失败: {_rr.text}"
print("[preset] 演示数据已重置", flush=True)

t = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
h = {"authorization": "Bearer " + t["token"]}

me = requests.get(BASE + "/api/auth/me", headers=h, timeout=10).json()
check("/me badge_count", isinstance(me.get("badge_count"), int), str(me.get("badge_count")))
check("/me practice_count", isinstance(me.get("practice_count"), int), str(me.get("practice_count")))
check("/me wrong_due", isinstance(me.get("wrong_due"), int), str(me.get("wrong_due")))
check("/me mastery 6 簇", len(me.get("mastery", {})) == 6, str(me.get("mastery")))

s = requests.get(BASE + "/api/quiz/summary", headers=h, timeout=10).json()
check("quiz/summary", s.get("wrong_active") == 3, str(s))

r = requests.post(BASE + "/api/quiz/start", json={"kind": "mock"}, headers=h, timeout=30).json()
check("quiz/start kind=mock time_limit", r.get("time_limit") == 720, f"kind={r.get('kind')} limit={r.get('time_limit')}")
check("quiz/start mock 10 题", r.get("count") == 10)
clusters = {it["cluster"] for it in r["items"]}
check("mock 无 general 稀释", "general" not in clusters or len(clusters) > 1, str(clusters))
check("题目无答案泄漏", all("answer" not in it for it in r["items"]))

r2 = requests.post(BASE + "/api/quiz/start", json={"kind": "daily"}, headers=h, timeout=30).json()
check("quiz/start kind=daily 无限时", r2.get("time_limit") == 0)

# 交卷（全答错路径 → 入错题本 + 再错 upsert）
ans = {str(it["question_id"]): "B" for it in r["items"]}
sub = requests.post(BASE + "/api/quiz/submit", json={"attempt_id": r["attempt_id"], "answers": ans}, headers=h, timeout=30).json()
check("submit 返回 per_cluster", "per_cluster" in sub, f"score={sub.get('score')}")
check("submit 正常返回", "score" in sub and "per_cluster" in sub and "max" in sub)

b = requests.get(BASE + "/api/game/badges", headers=h, timeout=10).json()
check("badges 规则文案", all(x.get("rule") for x in b), f"{len(b)} badges")
check("badges 簇徽章进度", any(x.get("progress") is not None for x in b if not x["earned"]), "")

wl = requests.get(BASE + "/api/wrong?status=active", headers=h, timeout=10).json()
check("wrong 含 first_wrong_at", all("first_wrong_at" in x for x in wl["items"]), f"{len(wl['items'])} items")

# 重答一次（第一题，答对 → streak=1，due +2d）
q = wl["items"][0]
rev = requests.post(BASE + "/api/wrong/review", json={"question_id": q["id"], "answer": q["answer"]}, headers=h, timeout=10).json()
check("wrong/review 答对", rev.get("correct") in (True, 1), f"status={rev.get('status')} streak 应=1")
wl2 = requests.get(BASE + "/api/wrong?status=active", headers=h, timeout=10).json()
same = next(x for x in wl2["items"] if x["id"] == q["id"])
import time as _t
check("答对后 due≈+2 天", 2 * 86400 - 3600 < same["due_at"] - _t.time() < 2 * 86400 + 3600, f"delta={same['due_at'] - _t.time():.0f}s")
check("答对后 active 数-1 或不变", len(wl2["items"]) <= len(wl["items"]))

# 学生打 admin 应 403
r3 = requests.get(BASE + "/api/admin/dashboard", headers=h, timeout=10)
check("学生 /api/admin/dashboard 403", r3.status_code == 403, str(r3.status_code))

print("=" * 40)
if fails:
    print("API FAIL:", fails)
    raise SystemExit(1)
print("API ALL PASS")