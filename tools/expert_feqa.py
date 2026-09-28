# -*- coding: utf-8 -*-
"""前端架构专家只读实测：10 个核心 API 的 P95 响应时间 + 越权校验 + 库规模。
只发 GET 与 /api/auth/login（登录不产生数据变更）。不碰 reset-demo / quiz.start / checkin / ask / review。
"""
import json
import statistics
import sqlite3
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8010"
N = 30  # 每接口迭代次数


def get(path, token=None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("authorization", "Bearer " + token)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, time.perf_counter() - t0, body
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t0, e.read()


def login(sno, pwd):
    data = json.dumps({"student_no": sno, "password": pwd}).encode()
    req = urllib.request.Request(BASE + "/api/auth/login", data=data,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def bench(path, token, tag):
    lat, codes = [], {}
    for _ in range(N):
        code, dt, _ = get(path, token)
        lat.append(dt)
        codes[code] = codes.get(code, 0) + 1
    print(f"{tag:<46} n={N} p50={pct(lat,.5)*1000:7.1f}ms p95={pct(lat,.95)*1000:7.1f}ms "
          f"max={max(lat)*1000:7.1f}ms mean={statistics.mean(lat)*1000:7.1f}ms codes={codes}")
    return lat


def main():
    print("== 登录 ==")
    st = login("S2026001", "123456")
    tok_s = st["token"]
    st2 = login("S2026002", "123456")
    tok_s2 = st2["token"]
    tt = login("T2026", "123456")
    tok_t = tt["token"]
    print("S2026001 user:", st["user"])

    print("\n== 只读 API 延迟（%d 次/接口）==" % N)
    bench("/api/health", None, "GET /api/health")
    bench("/api/auth/me", tok_s, "GET /api/auth/me (S2026001)")
    bench("/api/quiz/weak", tok_s, "GET /api/quiz/weak")
    bench("/api/wrong?status=active", tok_s, "GET /api/wrong?status=active")
    bench("/api/game/today", tok_s, "GET /api/game/today")
    bench("/api/game/points", tok_s, "GET /api/game/points")
    bench("/api/game/badges", tok_s, "GET /api/game/badges")
    bench("/api/game/leaderboard", tok_s, "GET /api/game/leaderboard")
    bench("/api/learn/history", tok_s, "GET /api/learn/history (S2026001)")
    bench("/api/learn/history", tok_s2, "GET /api/learn/history (S2026002 空白)")
    bench("/api/learn/status?session_id=probe&log_id=1", tok_s, "GET /api/learn/status (probe, 预期403)")

    print("\n== 越权校验（学生 token 打教师接口）==")
    code, dt, body = get("/api/admin/dashboard", tok_s)
    print(f"学生 S2026001 -> GET /api/admin/dashboard: {code} {dt*1000:.1f}ms body={body[:160]!r}")
    code, dt, body = get("/api/admin/dashboard", tok_t)
    print(f"教师 T2026    -> GET /api/admin/dashboard: {code} {dt*1000:.1f}ms body前120={body[:120]!r}")
    code, dt, body = get("/api/auth/me", "garbage.token.here")
    print(f"伪造 token    -> GET /api/auth/me: {code} body={body[:120]!r}")

    print("\n== 库规模（只读）==")
    con = sqlite3.connect("file:E:/lilei/platform/backend/falllearn.db?mode=ro", uri=True)
    for t in ("questions", "answers", "attempts", "wrong_records", "chat_logs", "points_log",
              "checkins", "exams", "exam_items", "users"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t:<14} {n}")
    try:
        q = con.execute("SELECT qtype, COUNT(*) FROM questions GROUP BY qtype").fetchall()
        print("题型分布:", q)
        c = con.execute("SELECT cluster_id, COUNT(*) FROM questions GROUP BY cluster_id").fetchall()
        print("簇分布:", c)
        gen = con.execute("SELECT COUNT(*) FROM questions WHERE cluster_id='general'").fetchone()[0]
        print("general 簇题量:", gen)
    except Exception as e:
        print("stats err", e)
    con.close()


if __name__ == "__main__":
    main()