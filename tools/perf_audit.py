# -*- coding: utf-8 -*-
"""性能与健壮性体检（只读为主）：接口延迟分布 / 首屏指标 / 传输压缩 / 并发压测 / SQL 查询计划。

用法：
    python tools/perf_audit.py [http://127.0.0.1:8010]

说明：
  - 只做 GET 与只读 POST（登录），不写业务数据；
  - 本地/远程均可跑（默认本地 8010）。
"""
import concurrent.futures as cf
import json
import statistics
import sqlite3
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
DB = r"E:\lilei\platform\backend\falllearn.db"
fails = []


def note(name, ok, extra=""):
    print(("  \u2713 " if ok else "  \u2717 ") + name + (" " + str(extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


def timed(fn, n=5):
    ts, code = [], 0
    for _ in range(n):
        t0 = time.perf_counter()
        r = fn()
        ts.append((time.perf_counter() - t0) * 1000)
        code = r.status_code
    return code, statistics.median(ts), max(ts)


print("=== A. 登录与准备 ===", flush=True)
tj = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=20).json()
TH = {"authorization": "Bearer " + tj["token"]}
sj = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=20).json()
SH = {"authorization": "Bearer " + sj["token"]}
note("教师/学生登录", bool(tj.get("token")) and bool(sj.get("token")))

print("=== B. 接口延迟（各 5 次，取中位数/最大）===", flush=True)
API = [
    ("健康检查", "/api/health", {}),
    ("学生档案", "/api/auth/me", SH),
    ("学习报告", "/api/quiz/report", SH),
    ("错题列表", "/api/wrong", SH),
    ("知识库检索", "/api/kb/search?q=跌倒 预防", SH),
    ("AI 通道状态", "/api/learn/status", SH),
    ("题库练习", "/api/quiz/weak", SH),
    ("排行榜", "/api/game/leaderboard", SH),
    ("积分", "/api/game/points", SH),
    ("今日任务", "/api/game/today", SH),
    ("徽章", "/api/game/badges", SH),
    ("问答历史", "/api/learn/history", SH),
    ("教师总览", "/api/admin/dashboard", TH),
    ("学生列表", "/api/admin/students", TH),
    ("统计总览", "/api/admin/stats/overview", TH),
    ("错题统计", "/api/admin/stats/wrong", TH),
    ("AI 配置", "/api/admin/ai/direct", TH),
]
slow, missing = [], []
for name, path, hdr in API:
    code, p50, mx = timed(lambda p=path, h=dict(hdr): requests.get(BASE + p, headers=h, timeout=30))
    if code == 404:
        missing.append(name)
        print(f"  - {name:<12} 404（路径待核对）", flush=True)
        continue
    flag = "" if p50 < 300 else "  ← 偏慢"
    print(f"  · {name:<12} {code}  p50={p50:6.1f}ms  max={mx:6.1f}ms{flag}", flush=True)
    if p50 >= 300:
        slow.append((name, p50))
note("无 404 路径（接口名核对）", not missing, missing)
note("无 p50 ≥ 300ms 的接口", not slow, slow)

print("=== C. 传输压缩（JS/CSS/HTML）===", flush=True)
html = requests.get(BASE + "/", timeout=20).text
import re as _re
assets = _re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
js = next((a for a in assets if a.endswith(".js")), None)
css = next((a for a in assets if a.endswith(".css")), None)
for label, url in (("JS", js), ("CSS", css)):
    if not url:
        continue
    raw = requests.get(BASE + url, headers={"Accept-Encoding": "identity"}, timeout=20)
    gz = requests.get(BASE + url, headers={"Accept-Encoding": "gzip"}, timeout=20)
    ce = gz.headers.get("content-encoding", "-")
    # 注意：requests 会自动解压，gz.content 是解压后大小 → 传输体积取 content-length 头
    wire = int(gz.headers.get("content-length", 0)) or len(gz.content)
    ratio = (1 - wire / max(1, len(raw.content))) * 100
    print(f"  · {label} 原始 {len(raw.content)/1024:.1f}KB → 传输 {wire/1024:.1f}KB ({ce}) 压缩率 {ratio:.0f}%", flush=True)
    note(f"{label} 启用压缩", ce in ("gzip", "br", "zstd"), f"{ce} {ratio:.0f}%")
    note(f"{label} 压缩后小于原始", wire < len(raw.content), f"{wire} < {len(raw.content)}")
h = requests.get(BASE + "/assets/" + (js.split("/assets/")[-1] if js else ""), timeout=20).headers
note("hashed 资源长缓存", "immutable" in h.get("cache-control", ""), h.get("cache-control"))

print("=== D. 并发压测（16 并发 × 40 请求）===", flush=True)
def hammer(path, hdr, n=40, workers=16):
    def one(_):
        t0 = time.perf_counter()
        try:
            r = requests.get(BASE + path, headers=hdr, timeout=30)
            return r.status_code, (time.perf_counter() - t0) * 1000
        except Exception as e:
            return 0, (time.perf_counter() - t0) * 1000
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, range(n)))

for label, path, hdr in (("知识库检索", "/api/kb/search?q=跌倒", SH), ("学习报告", "/api/quiz/report", SH),
                         ("教师总览", "/api/admin/dashboard", TH)):
    res = hammer(path, hdr)
    codes = [c for c, _ in res]
    lat = sorted(t for _, t in res)
    err = sum(1 for c in codes if c != 200)
    p95 = lat[int(len(lat) * 0.95) - 1]
    print(f"  · {label:<10} 错误={err}/{len(codes)}  p50={statistics.median(lat):6.1f}ms  p95={p95:6.1f}ms  max={lat[-1]:6.1f}ms", flush=True)
    note(f"{label} 并发无错误 (<5%)", err <= len(codes) * 0.05, f"{err} 错")

print("=== E. 前端首屏（Playwright）===", flush=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    try:
        p.wait_for_url(lambda u: "/login" not in u, timeout=25000)
    except Exception:
        pass
    p.wait_for_load_state("networkidle", timeout=30000)
    m = p.evaluate("""() => {
      const n = performance.getEntriesByType('navigation')[0] || {};
      const paints = performance.getEntriesByType('paint');
      const fcp = (paints.find(x => x.name === 'first-contentful-paint') || {}).startTime || 0;
      const rs = performance.getEntriesByType('resource');
      return {
        dcl: n.domContentLoadedEventEnd || 0, load: n.loadEventEnd || 0, fcp,
        resCount: rs.length,
        transfer: rs.reduce((s, r) => s + (r.transferSize || 0), 0),
        decoded: rs.reduce((s, r) => s + (r.decodedBodySize || 0), 0),
        ttfb: n.responseStart || 0
      };
    }""")
    print(f"  · 首屏 TTFB={m['ttfb']:.0f}ms  FCP={m['fcp']:.0f}ms  DCL={m['dcl']:.0f}ms  Load={m['load']:.0f}ms", flush=True)
    print(f"  · 资源 {m['resCount']} 个，传输 {m['transfer']/1024:.1f}KB / 解压 {m['decoded']/1024:.1f}KB", flush=True)
    note("首屏 FCP < 1500ms", m["fcp"] < 1500, f"{m['fcp']:.0f}ms")
    note("首屏传输 < 500KB", m["transfer"] < 500 * 1024, f"{m['transfer']/1024:.0f}KB")
    # 二访（缓存命中）成本
    t0 = time.time()
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
    p.wait_for_load_state("networkidle", timeout=30000)
    m2 = p.evaluate("""() => performance.getEntriesByType('resource').reduce((s,r)=>s+(r.transferSize||0),0)""")
    print(f"  · 二次访问传输 {m2/1024:.1f}KB（浏览器缓存命中），耗时 {(time.time()-t0)*1000:.0f}ms", flush=True)
    note("二次访问传输 < 60KB", m2 < 60 * 1024, f"{m2/1024:.1f}KB")
    b.close()

print("=== F. SQL 查询计划（本地库）===", flush=True)
BIG = 500  # 小表（<500 行）全表扫描是 SQLite 的最优选择，不算问题
try:
    c = sqlite3.connect(DB)
    plans = {
        "得分趋势": ("SELECT a.score,e.kind,a.submitted_at,e.title FROM attempts a LEFT JOIN exams e ON e.id=a.exam_id "
                 "WHERE a.student_id=? AND a.status='done' ORDER BY a.submitted_at ASC", "attempts"),
        "学习活跃14天": ("SELECT created_at, minutes FROM study_events WHERE student_id=? AND created_at>=0", "study_events"),
        "错题知识点分布": ("SELECT q.cluster_id,w.status,COUNT(*) c FROM wrong_records w JOIN questions q ON q.id=w.question_id "
                    "WHERE w.student_id=? GROUP BY q.cluster_id,w.status", "wrong_records"),
        "正确率聚合": ("SELECT q.cluster_id,COUNT(*) n,SUM(a.correct) ok FROM answers a JOIN attempts t ON t.id=a.attempt_id "
                   "JOIN questions q ON q.id=a.question_id WHERE t.student_id=? GROUP BY q.cluster_id", "answers"),
        "错题本列表": ("SELECT w.id FROM wrong_records w JOIN questions q ON q.id=w.question_id "
                   "WHERE w.student_id=? AND w.status='active' ORDER BY w.due_at", "wrong_records"),
        "排行榜": ("SELECT u.id,u.name,COALESCE(p.points,0) pts FROM users u LEFT JOIN points_cache p ON p.student_id=u.id "
                 "WHERE u.role='student' ORDER BY pts DESC,u.id LIMIT 50", "users"),
    }
    for name, (q, table) in plans.items():
        n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        try:
            rows = c.execute("EXPLAIN QUERY PLAN " + q, (1,) if "?" in q else ()).fetchall()
            txt = " | ".join(r[-1] for r in rows)
            scan = "SCAN " in txt and "USING INDEX" not in txt
            ok = (not scan) or n < BIG
            mark = "\u2713" if ok else "\u2717"
            tail = f"（表 {n} 行，小表扫描可接受）" if scan and n < BIG else ""
            print(f"  {mark} {name}: {txt[:100]}{tail}", flush=True)
            if not ok:
                fails.append(f"SQL 全表扫描（大表）: {name}")
        except Exception as e:
            print(f"  - {name}: 跳过（{e}）", flush=True)
    c.close()
except Exception as e:
    print("  - 跳过（库不可读）:", e, flush=True)

print(f"\n===== 性能与健壮性体检: 失败 {len(fails)} 项 → {BASE} =====")
print("FAILS:", fails if fails else "无")
sys.exit(1 if fails else 0)
