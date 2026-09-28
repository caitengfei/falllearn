# -*- coding: utf-8 -*-
"""perf 专家 · 管理后台 API 计时（只读，3 次均值，串行）。
端点：/api/admin/stats/overview · /students · /exams · /banners · /trainings
      · /api/admin/ai/kb · /api/admin/ai/models(10min 缓存) · /api/content/banners
产物：E:\\lilei\\platform\\docs\\expert-admin\\perf_api_timing.json
"""
import json
import os
import statistics
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
N = 3

OUT = r"E:\lilei\platform\docs\expert-admin\perf_api_timing.json"

ENDPOINTS = [
    ("admin.stats_overview", "GET", "/api/admin/stats/overview", True),
    ("admin.students", "GET", "/api/admin/students", True),
    ("admin.exams", "GET", "/api/admin/exams", True),
    ("admin.banners", "GET", "/api/admin/banners", True),
    ("admin.trainings", "GET", "/api/admin/trainings", True),
    ("admin.ai_kb", "GET", "/api/admin/ai/kb", True),
    ("admin.ai_models", "GET", "/api/admin/ai/models", True),   # 10min 进程内缓存
    ("content.banners", "GET", "/api/content/banners", False),  # 公开
]


def main():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=15)
    r.raise_for_status()
    tok = r.json()["token"]
    print(f"login T2026 ok, token len={len(tok)}")
    s.headers["authorization"] = f"Bearer {tok}"

    results = []
    for tag, method, path, authed in ENDPOINTS:
        times, status, body_bytes, detail = [], 0, 0, ""
        for i in range(N):
            t0 = time.perf_counter()
            try:
                rr = s.request(method, f"{BASE}{path}", timeout=120)
                dt = (time.perf_counter() - t0) * 1000
                times.append(round(dt, 1))
                status = rr.status_code
                body_bytes = len(rr.content)
                if i == 0:
                    detail = rr.text[:300].replace("\n", " ")
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                times.append(round(dt, 1))
                status = -1
                detail = f"EXC {e}"
            time.sleep(0.2)  # 串行隔离
        results.append({
            "tag": tag, "path": path, "runs_ms": times,
            "mean_ms": round(statistics.mean(times), 1),
            "min_ms": min(times), "max_ms": max(times),
            "status": status, "body_bytes": body_bytes, "first_body_head": detail,
        })
        print(f"{tag:22s} {path:32s} runs={times} mean={statistics.mean(times):.1f}ms status={status} bytes={body_bytes}")

    # 参考：登录（bcrypt）单次
    t0 = time.perf_counter()
    rr = requests.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=15)
    login_ms = round((time.perf_counter() - t0) * 1000, 1)
    print(f"{'auth.login(ref)':22s} runs=[{login_ms}] status={rr.status_code}")

    payload = {
        "tag": "perf", "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "串行 3 次均值；ai_models 若首跑慢=进程内 10min 缓存冷（含 DSH session.models RPC），后续命中缓存",
        "login_ms": login_ms, "endpoints": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()