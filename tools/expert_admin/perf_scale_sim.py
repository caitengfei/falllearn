# -*- coding: utf-8 -*-
"""perf 专家 · 30 学生规模模拟（在 DB 副本上合成数据，绝不碰线上库）。
1) VACUUM INTO 快照 falllearn.db -> perf_sim.db
2) 合成 27 名学生（含 mastery/points_log/study_events/chat_logs/attempts/answers/enrolls/checkins）
3) 复现 manage.py 的查询序列计时：students_list / stats_overview / trainings_list / stats_trainings
4) 加建议索引后复测 + 复现「优化版」(GROUP BY 单查询) 计时
产物：E:\\lilei\\platform\\docs\\expert-admin\\perf_scale_sim.json
"""
import json
import os
import random
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\lilei\platform\backend\falllearn.db"  # 真实库（db.py BASE=backend/）；app/falllearn.db 为 0KB 陈旧残留
DST = r"E:\lilei\platform\tools\expert_admin\perf_sim.db"
OUT = r"E:\lilei\platform\docs\expert-admin\perf_scale_sim.json"
N_NEW = 27  # 3 种子 + 27 合成 = 30


def now():
    return int(time.time())


def snap():
    if os.path.exists(DST):
        os.remove(DST)
    for suf in ("-wal", "-shm"):
        if os.path.exists(DST + suf):
            os.remove(DST + suf)
    src = sqlite3.connect(SRC)
    src.execute("VACUUM INTO ?", (DST,))
    src.close()
    print(f"snapshot -> {DST}")


def synth():
    d = sqlite3.connect(DST)
    rnd = random.Random(20260928)
    t = now()
    base_sid = d.execute("SELECT MAX(id) FROM users WHERE role='student'").fetchone()[0]
    for k in range(1, N_NEW + 1):
        sid = base_sid + k
        d.execute("INSERT INTO users(student_no,name,role,pwd_hash,created_at,enabled) VALUES(?,?,?,?,?,1)",
                  (f"S20261{k:02d}", f"合成生{k:02d}", "student", "x", t - 86400 * 30))
        for cid in ("morse", "env", "five", "fracture", "record", "cpr"):
            d.execute("INSERT INTO mastery(student_id,cluster_id,level,n_correct,n_total,updated_at) VALUES(?,?,?,?,?,?)",
                      (sid, cid, rnd.randint(10, 95), rnd.randint(0, 20), 20, t - rnd.randint(0, 86400 * 10)))
        for _ in range(50):
            d.execute("INSERT INTO points_log(student_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                      (sid, rnd.choice([2, 5, 10]), "练习答对", "", t - rnd.randint(0, 86400 * 30)))
        for _ in range(40):
            d.execute("INSERT INTO study_events(student_id,type,minutes,ref,created_at) VALUES(?,?,?,?,?)",
                      (sid, rnd.choice(["ai_quiz", "practice", "review"]), rnd.uniform(0.5, 20), "", t - rnd.randint(0, 86400 * 30)))
        for _ in range(rnd.randint(2, 6)):
            d.execute("INSERT INTO chat_logs(student_id,dsh_session_id,question,answer,clusters_touched,created_at) VALUES(?,?,?,?,?,?)",
                      (sid, "", "q" * 8, "a" * 40, "five", t - rnd.randint(0, 86400 * 20)))
        for _ in range(rnd.randint(5, 15)):
            d.execute("INSERT OR IGNORE INTO checkins(student_id,date) VALUES(?,?)", (sid, time.strftime("%Y-%m-%d", time.localtime(t - rnd.randint(0, 14) * 86400))))
        for _ in range(rnd.randint(1, 3)):
            tid = rnd.randint(1, 2)
            d.execute("INSERT OR IGNORE INTO training_enrolls(training_id,student_id,status,enrolled_at) VALUES(?,?,?,?)",
                      (tid, sid, rnd.choice(["enrolled", "done"]), t - rnd.randint(0, 86400 * 5)))
        for _ in range(rnd.randint(3, 5)):
            st = t - rnd.randint(0, 86400 * 20)
            cur = d.execute("INSERT INTO attempts(student_id,exam_id,started_at,submitted_at,score,status) VALUES(?,?,?,?,?,?)",
                            (sid, 1, st, st + rnd.randint(300, 900), rnd.randint(40, 100), "done"))
            att = cur.lastrowid
            qids = [r[0] for r in d.execute("SELECT id FROM questions LIMIT 10")]
            for qid in qids:
                d.execute("INSERT INTO answers(attempt_id,question_id,student_answer,correct,score,feedback,graded_by,answered_at) VALUES(?,?,?,?,?,?,?,?)",
                          (att, qid, "A", rnd.randint(0, 1), 10, "", "rules", st + 600))
        for _ in range(rnd.randint(2, 6)):
            qid = rnd.randint(1, 1300)
            d.execute("INSERT OR REPLACE INTO wrong_records(student_id,question_id,first_wrong_at,review_count,correct_streak,last_review_at,due_at,status) VALUES(?,?,?,?,?,?,?,?)",
                      (sid, qid, t - 86400, 1, 0, None, t + 86400, "active"))
    d.commit()
    n = d.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    a = d.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    p = d.execute("SELECT COUNT(*) FROM points_log").fetchone()[0]
    d.close()
    print(f"synth done: students={n} answers={a} points_log={p}")


def count_queries(fn, d):
    """执行 fn(d)，统计触发的 SQL 条数（trace）。"""
    n = [0]
    def tr(op):
        op = op.strip().lower()
        if op.startswith(("select", "insert", "update", "delete", "with")):
            n[0] += 1
    d.set_trace_callback(tr)
    try:
        fn(d)
    finally:
        d.set_trace_callback(None)
    return n[0]


def student_stats_8q(d, uid):
    """复现 manage.py _student_stats：8 条查询/学生。"""
    d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (uid,)).fetchall()
    d.execute("SELECT points FROM points_cache WHERE student_id=?", (uid,)).fetchone()
    d.execute("SELECT COUNT(*) c FROM attempts WHERE student_id=? AND status='done'", (uid,)).fetchone()
    d.execute("SELECT COUNT(*) c FROM chat_logs WHERE student_id=? AND answer!=''", (uid,)).fetchone()
    d.execute("SELECT COUNT(*) c FROM wrong_records WHERE student_id=? AND status='active'", (uid,)).fetchone()
    d.execute("SELECT COUNT(*) c FROM user_badges WHERE student_id=?", (uid,)).fetchone()
    d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE student_id=?", (uid,)).fetchone()
    d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?", (uid,)).fetchone()


def students_list_current(d):
    sids = [r[0] for r in d.execute("SELECT id FROM users WHERE role='student' ORDER BY id")]
    for sid in sids:
        student_stats_8q(d, sid)


def students_list_fixed(d):
    """优化版：7 条 GROUP BY 查询覆盖全部学生。"""
    d.execute("SELECT cluster_id, level FROM mastery").fetchall()
    d.execute("SELECT student_id, points FROM points_cache").fetchall()
    d.execute("SELECT student_id, COUNT(*) FROM attempts WHERE status='done' GROUP BY student_id").fetchall()
    d.execute("SELECT student_id, COUNT(*) FROM chat_logs WHERE answer!='' GROUP BY student_id").fetchall()
    d.execute("SELECT student_id, COUNT(*) FROM wrong_records WHERE status='active' GROUP BY student_id").fetchall()
    d.execute("SELECT student_id, COUNT(*) FROM user_badges GROUP BY student_id").fetchall()
    d.execute("SELECT student_id, COUNT(*) FROM training_enrolls GROUP BY student_id").fetchall()
    d.execute("SELECT student_id, SUM(minutes) FROM study_events GROUP BY student_id").fetchall()


def stats_overview_current(d):
    """复现 manage.py stats_overview 全序列（39 + 4N 条查询）。"""
    now = int(time.time())
    today = time.strftime("%Y-%m-%d")
    d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()
    d.execute("SELECT COUNT(*) c FROM questions").fetchone()
    d.execute("SELECT COUNT(*) c FROM chat_logs WHERE answer!=''").fetchone()
    d.execute("SELECT COUNT(*) c FROM attempts WHERE status='done'").fetchone()
    d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events").fetchone()
    d.execute("SELECT COALESCE(AVG(level),0) m FROM mastery").fetchone()

    def active_days(days):
        d.execute("SELECT COUNT(DISTINCT student_id) c FROM (SELECT student_id FROM checkins WHERE date>=? "
                  "UNION SELECT student_id FROM chat_logs WHERE created_at>=? "
                  "UNION SELECT student_id FROM attempts WHERE started_at>=? "
                  "UNION SELECT student_id FROM study_events WHERE created_at>=?)",
                  (today if days == 1 else today, now - days * 86400, now - days * 86400, now - days * 86400)).fetchone()
    active_days(1)
    active_days(7)
    for i in range(6, -1, -1):
        d0, d1 = now - (i + 1) * 86400, now - i * 86400
        d.execute("SELECT COALESCE(SUM(delta),0) s FROM points_log WHERE created_at>=? AND created_at<?", (d0, d1)).fetchone()
        d.execute("SELECT COUNT(*) c FROM chat_logs WHERE created_at>=? AND created_at<? AND answer!=''", (d0, d1)).fetchone()
    for cid in ("morse", "env", "five", "fracture", "record", "cpr"):
        d.execute("SELECT COALESCE(AVG(level),0) m, COUNT(DISTINCT student_id) n FROM mastery WHERE cluster_id=?", (cid,)).fetchone()
    d.execute("SELECT qtype, COUNT(*) c FROM questions GROUP BY qtype").fetchall()

    def rank(field):
        rows = d.execute("SELECT id FROM users WHERE role='student' AND enabled=1 ORDER BY id").fetchall()
        for (r,) in rows:
            if field == "points":
                d.execute("SELECT points FROM points_cache WHERE student_id=?", (r,)).fetchone()
            elif field == "mastery":
                d.execute("SELECT COALESCE(AVG(level),0) m FROM mastery WHERE student_id=?", (r,)).fetchone()
            else:
                d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?", (r,)).fetchone()
    for f in ("points", "mastery", "hours"):
        rank(f)
    for cid in ("morse", "env", "five", "fracture", "record", "cpr"):
        d.execute("SELECT COUNT(*) n, SUM(1-a.correct) wrong FROM answers a JOIN questions q ON q.id=a.question_id "
                  "WHERE q.cluster_id=? AND a.graded_by LIKE 'rules%'", (cid,)).fetchone()
    sids = d.execute("SELECT id FROM users WHERE role='student' AND enabled=1 ORDER BY id").fetchall()
    for (r,) in sids:
        d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?", (r,)).fetchone()


def stats_overview_fixed(d):
    """优化版：固定 ~12 条查询（与 N 无关）。"""
    now = int(time.time())
    d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()
    d.execute("SELECT COUNT(*) c FROM questions").fetchone()
    d.execute("SELECT COUNT(*) c FROM chat_logs WHERE answer!=''").fetchone()
    d.execute("SELECT COUNT(*) c FROM attempts WHERE status='done'").fetchone()
    d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events").fetchone()
    d.execute("SELECT COALESCE(AVG(level),0) m FROM mastery").fetchone()
    d.execute("SELECT COUNT(DISTINCT student_id) c FROM (SELECT student_id FROM checkins WHERE date>=? "
              "UNION ALL SELECT student_id FROM chat_logs WHERE created_at>=? "
              "UNION ALL SELECT student_id FROM attempts WHERE started_at>=? "
              "UNION ALL SELECT student_id FROM study_events WHERE created_at>=?)",
              (time.strftime("%Y-%m-%d", time.localtime(now - 7 * 86400)),) * 4).fetchone()
    d.execute("SELECT date(created_at,'unixepoch') day, COALESCE(SUM(delta),0) s FROM points_log "
              "WHERE created_at>=? GROUP BY day", (now - 7 * 86400,)).fetchall()
    d.execute("SELECT date(created_at,'unixepoch') day, COUNT(*) c FROM chat_logs "
              "WHERE created_at>=? AND answer!='' GROUP BY day", (now - 7 * 86400,)).fetchall()
    d.execute("SELECT cluster_id, AVG(level) FROM mastery GROUP BY cluster_id").fetchall()
    d.execute("SELECT qtype, COUNT(*) c FROM questions GROUP BY qtype").fetchall()
    d.execute("SELECT u.id, COALESCE(p.points,0) v FROM users u LEFT JOIN points_cache p ON p.student_id=u.id "
              "WHERE u.role='student' AND u.enabled=1 ORDER BY v DESC LIMIT 10").fetchall()
    d.execute("SELECT u.id, COALESCE(AVG(m.level),0) v FROM users u LEFT JOIN mastery m ON m.student_id=u.id "
              "WHERE u.role='student' AND u.enabled=1 GROUP BY u.id ORDER BY v DESC LIMIT 10").fetchall()
    d.execute("SELECT u.id, COALESCE(SUM(se.minutes),0) v FROM users u LEFT JOIN study_events se ON se.student_id=u.id "
              "WHERE u.role='student' AND u.enabled=1 GROUP BY u.id ORDER BY v DESC LIMIT 10").fetchall()
    d.execute("SELECT q.cluster_id, COUNT(*) n, SUM(1-a.correct) wrong FROM answers a "
              "JOIN questions q ON q.id=a.question_id WHERE a.graded_by LIKE 'rules%' GROUP BY q.cluster_id").fetchall()
    d.execute("SELECT u.id, COALESCE(SUM(se.minutes),0) v FROM users u LEFT JOIN study_events se ON se.student_id=u.id "
              "WHERE u.role='student' AND u.enabled=1 GROUP BY u.id ORDER BY v DESC").fetchall()


PROPOSED_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pointslog_created ON points_log(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_enrolls_student ON training_enrolls(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status)",
    "CREATE INDEX IF NOT EXISTS idx_mastery_cluster ON mastery(cluster_id)",
    "CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(date)",
]


def bench(fn, d, reps=5):
    best = 1e9
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(d)
        best = min(best, time.perf_counter() - t0)
    return round(best * 1000, 2)


def main():
    snap()
    synth()

    out = {"tag": "perf", "date": time.strftime("%Y-%m-%d %H:%M:%S"), "db_copy": DST, "scale": "30 students (27 synthetic)"}
    d = sqlite3.connect(DST)
    d.row_factory = sqlite3.Row

    n_stu = d.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()["c"]
    out["students"] = n_stu
    out["indexes_before"] = sorted({r[1] for t in ("points_log", "chat_logs", "study_events", "training_enrolls",
                                                    "attempts", "mastery", "answers", "checkins", "questions")
                                    for r in d.execute(f"PRAGMA index_list({t})") if r[1]})

    res = {}
    for name, fn in [
        ("students_list_current", students_list_current),
        ("students_list_fixed", students_list_fixed),
        ("stats_overview_current", stats_overview_current),
        ("stats_overview_fixed", stats_overview_fixed),
    ]:
        q = count_queries(fn, d)
        ms = bench(fn, d)
        res[name] = {"queries": q, "ms": ms}
        print(f"BEFORE {name:28s} queries={q:4d}  best={ms} ms")
    out["before"] = res
    d.close()

    # 加索引后
    d = sqlite3.connect(DST)
    for ix in PROPOSED_INDEXES:
        d.execute(ix)
    d.commit()
    d.row_factory = sqlite3.Row
    out["indexes_added"] = [i.split("ON")[1].strip() for i in PROPOSED_INDEXES]

    res2 = {}
    for name, fn in [
        ("students_list_current", students_list_current),
        ("students_list_fixed", students_list_fixed),
        ("stats_overview_current", stats_overview_current),
        ("stats_overview_fixed", stats_overview_fixed),
    ]:
        q = count_queries(fn, d)
        ms = bench(fn, d)
        res2[name] = {"queries": q, "ms": ms}
        print(f"AFTER  {name:28s} queries={q:4d}  best={ms} ms")
    out["after_indexes"] = res2
    d.close()

    # EXPLAIN QUERY PLAN 证据（关键缺失索引模式）
    d = sqlite3.connect(DST)
    plans = {}
    for name, sql in [
        ("points_log_7d_trend", "SELECT COALESCE(SUM(delta),0) s FROM points_log WHERE created_at>=? AND created_at<?"),
        ("chat_logs_7d_asks", "SELECT COUNT(*) c FROM chat_logs WHERE created_at>=? AND created_at<? AND answer!=''"),
        ("enrolls_by_student", "SELECT COUNT(*) c FROM training_enrolls WHERE student_id=?"),
        ("attempts_status_done", "SELECT COUNT(*) c FROM attempts WHERE status='done'"),
        ("mastery_by_cluster", "SELECT COALESCE(AVG(level),0) m FROM mastery WHERE cluster_id=?"),
        ("weak_join_cluster", "SELECT COUNT(*) n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.cluster_id=? AND a.graded_by LIKE 'rules%'"),
        ("checkins_by_date", "SELECT student_id FROM checkins WHERE date>=?"),
    ]:
        params = (1,) * sql.count("?")
        plans[name] = " | ".join(r[3] for r in d.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall())
        print(f"PLAN {name:24s} {plans[name]}")
    out["query_plans_after_indexes"] = plans
    d.close()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()