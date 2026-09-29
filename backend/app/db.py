# -*- coding: utf-8 -*-
"""SQLite 数据层：schema + 种子（题库/簇/演示账号）"""
import json
import os
import re
import sqlite3
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "falllearn.db")
SEED = os.path.join(BASE, "seed", "questions_seed.json")

CLUSTERS = [
    ("morse", "Morse评估"),
    ("env", "环境防控"),
    ("five", "五步处置"),
    ("fracture", "骨折识别"),
    ("record", "记录上报"),
    ("cpr", "CPR启动"),
]
CLUSTER_IDS = [c[0] for c in CLUSTERS]
CLUSTER_NAMES = {c[0]: c[1] for c in CLUSTERS}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, student_no TEXT UNIQUE, name TEXT, role TEXT DEFAULT 'student',
  pwd_hash TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS mastery(
  student_id INTEGER, cluster_id TEXT, level REAL DEFAULT 0,
  n_correct INTEGER DEFAULT 0, n_total INTEGER DEFAULT 0, updated_at INTEGER,
  PRIMARY KEY(student_id, cluster_id)
);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY, qtype TEXT, cluster_id TEXT, difficulty INTEGER,
  stem TEXT, options TEXT, answer TEXT, source_doc TEXT, origin TEXT
);
CREATE TABLE IF NOT EXISTS exams(
  id INTEGER PRIMARY KEY, title TEXT, kind TEXT, config TEXT, created_by INTEGER, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS exam_items(
  exam_id INTEGER, question_id INTEGER, seq INTEGER, score INTEGER,
  PRIMARY KEY(exam_id, seq)
);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY, student_id INTEGER, exam_id INTEGER,
  started_at INTEGER, submitted_at INTEGER, score INTEGER DEFAULT -1, status TEXT DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS answers(
  id INTEGER PRIMARY KEY, attempt_id INTEGER, question_id INTEGER,
  student_answer TEXT, correct INTEGER, score INTEGER, feedback TEXT,
  graded_by TEXT DEFAULT 'rules', answered_at INTEGER
);
CREATE TABLE IF NOT EXISTS wrong_records(
  id INTEGER PRIMARY KEY, student_id INTEGER, question_id INTEGER,
  first_wrong_at INTEGER, review_count INTEGER DEFAULT 0,
  correct_streak INTEGER DEFAULT 0,
  last_review_at INTEGER, due_at INTEGER, status TEXT DEFAULT 'active',
  UNIQUE(student_id, question_id)
);
CREATE TABLE IF NOT EXISTS chat_logs(
  id INTEGER PRIMARY KEY, student_id INTEGER, dsh_session_id TEXT,
  question TEXT, answer TEXT, clusters_touched TEXT, created_at INTEGER,
  dsh_base_seq INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS checkins(
  student_id INTEGER, date TEXT, PRIMARY KEY(student_id, date)
);
CREATE TABLE IF NOT EXISTS points_log(
  id INTEGER PRIMARY KEY, student_id INTEGER, delta INTEGER, reason TEXT,
  ref TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS badges(
  id TEXT PRIMARY KEY, name TEXT, icon TEXT
);
CREATE TABLE IF NOT EXISTS user_badges(
  student_id INTEGER, badge_id TEXT, earned_at INTEGER, PRIMARY KEY(student_id, badge_id)
);
CREATE TABLE IF NOT EXISTS student_sessions(
  student_id INTEGER PRIMARY KEY, dsh_session_id TEXT, dsh_preset TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS points_cache(
  student_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0
);
-- ---------- 管理后台（B 期） ----------
CREATE TABLE IF NOT EXISTS banners(
  id INTEGER PRIMARY KEY, title TEXT, tag TEXT, sub TEXT, image TEXT, link TEXT,
  sort INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS announcements(
  id INTEGER PRIMARY KEY, title TEXT, summary TEXT, content TEXT,
  start_date TEXT, end_date TEXT, pinned INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS study_events(
  id INTEGER PRIMARY KEY, student_id INTEGER, type TEXT,
  minutes REAL, ref TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS trainings(
  id INTEGER PRIMARY KEY, title TEXT, batch TEXT, start_date TEXT, end_date TEXT,
  teacher_id INTEGER, capacity INTEGER, note TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS training_enrolls(
  id INTEGER PRIMARY KEY, training_id INTEGER, student_id INTEGER,
  status TEXT DEFAULT 'enrolled', enrolled_at INTEGER,
  UNIQUE(training_id, student_id)
);
CREATE TABLE IF NOT EXISTS ai_grades(
  id INTEGER PRIMARY KEY, attempt_id INTEGER, model TEXT,
  ai_score REAL, detail TEXT, diff INTEGER, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT
);
"""

CLUSTER_KEY_MAP = {
    "Morse评估": "morse", "环境防控": "env", "五步处置": "five",
    "骨折识别": "fracture", "记录上报": "record", "CPR启动": "cpr", "通用": "general",
}


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _migrate(db):
    """旧库平滑升级：补列 + 错题本唯一约束（先去重）+ 热列索引。"""
    cols = {r[1] for r in db.execute("PRAGMA table_info(wrong_records)")}
    if "correct_streak" not in cols:
        db.execute("ALTER TABLE wrong_records ADD COLUMN correct_streak INTEGER DEFAULT 0")
    cols2 = {r[1] for r in db.execute("PRAGMA table_info(chat_logs)")}
    if "dsh_base_seq" not in cols2:
        db.execute("ALTER TABLE chat_logs ADD COLUMN dsh_base_seq INTEGER DEFAULT 0")
    cols3 = {r[1] for r in db.execute("PRAGMA table_info(users)")}
    if "enabled" not in cols3:
        db.execute("ALTER TABLE users ADD COLUMN enabled INTEGER DEFAULT 1")
    cols4 = {r[1] for r in db.execute("PRAGMA table_info(banners)")}
    if "tag" not in cols4:
        db.execute("ALTER TABLE banners ADD COLUMN tag TEXT DEFAULT ''")
        db.execute("ALTER TABLE banners ADD COLUMN sub TEXT DEFAULT ''")
    for idx in (
        "CREATE INDEX IF NOT EXISTS idx_questions_cluster ON questions(cluster_id)",
        "CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id)",
        # 学习报告「得分趋势」按 student_id+status 过滤并按 submitted_at 排序：复合索引免临时排序
        "CREATE INDEX IF NOT EXISTS idx_attempts_student_status ON attempts(student_id, status, submitted_at)",
        "CREATE INDEX IF NOT EXISTS idx_answers_attempt ON answers(attempt_id)",
        "CREATE INDEX IF NOT EXISTS idx_wrong_student ON wrong_records(student_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_chat_student ON chat_logs(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_pointslog_student ON points_log(student_id, reason)",
        "CREATE INDEX IF NOT EXISTS idx_study_student ON study_events(student_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_enrolls_training ON training_enrolls(training_id)",
        # 性能专家补 7 个热列索引（消除 7 类全表扫描：7 日趋势/排行榜/判卷幂等等）
        "CREATE INDEX IF NOT EXISTS idx_pointslog_time ON points_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_time ON chat_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status)",
        "CREATE INDEX IF NOT EXISTS idx_mastery_cluster ON mastery(cluster_id)",
        "CREATE INDEX IF NOT EXISTS idx_answers_q ON answers(question_id)",
        "CREATE INDEX IF NOT EXISTS idx_enrolls_student ON training_enrolls(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(date)",
        "CREATE INDEX IF NOT EXISTS idx_ai_grades_attempt ON ai_grades(attempt_id)",
    ):
        db.execute(idx)
    # ai_grades 幂等：同一 attempt 只保留一条 AI 判卷
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_grades_attempt_uq ON ai_grades(attempt_id)")
    except sqlite3.IntegrityError:
        pass
    # 种子轮播首卡 link='/' 是死跳转（CT-3）：迁移为 /learn
    try:
        db.execute("UPDATE banners SET link='/learn' WHERE link IN ('', '/')")
    except sqlite3.Error:
        pass
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_wrong_sq ON wrong_records(student_id, question_id)")
    except sqlite3.IntegrityError:
        # 已有重复：保留每组最新一条
        db.execute(
            "DELETE FROM wrong_records WHERE id NOT IN "
            "(SELECT id FROM wrong_records WHERE student_id IS NOT NULL "
            "GROUP BY student_id, question_id HAVING id = MAX(id))")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_wrong_sq ON wrong_records(student_id, question_id)")
    # 并发防护①：同一张卷同一题只允许一条作答（并发重复交卷会插入重复行 → 统计翻倍）
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_aq_uq ON answers(attempt_id, question_id)")
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM answers WHERE id NOT IN "
                   "(SELECT MIN(id) FROM answers GROUP BY attempt_id, question_id)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_aq_uq ON answers(attempt_id, question_id)")
    # 并发防护②：同一学生同一张卷最多一张未交卷（并发开卷会造出两张 open 卷 → 双份得分）
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_open_uq "
                   "ON attempts(student_id, exam_id) WHERE status='open'")
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM answers WHERE attempt_id IN ("
                   "SELECT id FROM attempts WHERE status='open' AND id NOT IN ("
                   "SELECT MAX(id) FROM attempts WHERE status='open' GROUP BY student_id, exam_id))")
        db.execute("DELETE FROM attempts WHERE status='open' AND id NOT IN ("
                   "SELECT MAX(id) FROM attempts WHERE status='open' GROUP BY student_id, exam_id)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_open_uq "
                   "ON attempts(student_id, exam_id) WHERE status='open'")
    db.commit()


def init_db(seed=True):
    db = get_db()
    db.executescript(SCHEMA)
    _migrate(db)
    for cid, cname in CLUSTERS:
        db.execute("INSERT OR IGNORE INTO badges(id,name,icon) VALUES(?,?,?)",
                   ("b_" + cid, f"掌握「{cname}」", "🎖"))
    for bid, bname in [("b_first_q", "首答之章"), ("b_streak10", "连对十题"), ("b_all60", "六簇达标")]:
        db.execute("INSERT OR IGNORE INTO badges(id,name,icon) VALUES(?,?,?)", (bid, bname, "🏅"))
    if seed:
        _seed_bank(db)
        _seed_users(db)
        _seed_assignment(db)
    _seed_banners(db)
    # 兜底：老库/任何来源的 banner 死链接（'' 或 '/'）→ /learn（CT-3）
    try:
        db.execute("UPDATE banners SET link='/learn' WHERE link IN ('', '/')")
    except sqlite3.Error:
        pass
    db.commit()
    db.close()


def _seed_banners(db):
    """首启时把首页 4 张静态轮播卡落库（管理后台可替换/新增）。"""
    if db.execute("SELECT COUNT(*) c FROM banners").fetchone()["c"] > 0:
        return
    now = int(time.time())
    rows = [
        ("老年人跌倒 · 预防与应急处置", "世赛 × 省赛 GZ063 双对标", "岗课赛证融通 · 把技能学成肌肉记忆", "/learn", "", 0),
        ("12 分钟理论模拟考", "限时 12 分钟 · 10 题 100 分", "对标竞赛情景模块 · 倒计时自动交卷", "/practice?menu=mock", "", 1),
        ("比赛资料 · 官方规程与评分标准", "46 份真实文档", "世赛/全国赛/省赛规程与正式赛题 · M8 评分 · 三证国标与题库", "/competition", "", 2),
        ("错题本 · 次日到期 → 第 3 天", "间隔复习 · 连对 2 次掌握", "每道错题自动入本 · 重答 / 讲解双模式", "/wrong", "", 3),
    ]
    for title, tag, sub, link, img, sort in rows:
        db.execute(
            "INSERT INTO banners(title,tag,sub,image,link,sort,enabled,created_at) VALUES(?,?,?,?,?,?,1,?)",
            (title, tag, sub, img, link, sort, now))


def _seed_bank(db):
    n = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if n > 0:
        return n
    if not os.path.exists(SEED):
        raise SystemExit(f"缺题库种子: {SEED}（先跑 tools/parse_bank.py）")
    rows = json.load(open(SEED, encoding="utf-8"))
    now = int(time.time())
    for q in rows:
        db.execute(
            "INSERT INTO questions(qtype,cluster_id,difficulty,stem,options,answer,source_doc,origin) VALUES(?,?,?,?,?,?,?,?)",
            (q["type"], CLUSTER_KEY_MAP.get(q["cluster"], "general"), q["difficulty"],
             q["stem"], json.dumps(q["options"], ensure_ascii=False), q["answer"],
             q["source_doc"], q["origin"]),
        )
    print(f"[seed] 题库 {db.execute('SELECT COUNT(*) FROM questions').fetchone()[0]} 题")
    return db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]


import bcrypt as _bcrypt


def _hash(p):
    return _bcrypt.hashpw(p.encode(), _bcrypt.gensalt(10)).decode()


def _seed_users(db):
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return
    now = int(time.time())
    demo = [
        ("S2026001", "张小明", "student", "123456"),
        ("S2026002", "李小红", "student", "123456"),
        ("S2026003", "王大锤", "student", "123456"),
        ("T2026", "陈老师", "teacher", "123456"),
    ]
    for sno, name, role, pwd in demo:
        db.execute(
            "INSERT INTO users(student_no,name,role,pwd_hash,created_at) VALUES(?,?,?,?,?)",
            (sno, name, role, _hash(pwd), now),
        )
    seed_demo_data(db)
    print("[seed] 演示账号 S2026001-3 / T2026 密码 123456")


def _seed_assignment(db):
    """种子一条教师布置（幂等）：演示「教师布置 → 学生完成」闭环，评委可直接开考体验。"""
    if db.execute("SELECT 1 FROM exams WHERE kind='teacher' LIMIT 1").fetchone():
        return
    t = db.execute("SELECT id FROM users WHERE student_no='T2026'").fetchone()
    if not t:
        return
    now = int(time.time())
    qids = [r["id"] for r in db.execute(
        "SELECT id FROM questions WHERE cluster_id='five' ORDER BY RANDOM() LIMIT 5")]
    if len(qids) < 5:
        qids += [r["id"] for r in db.execute(
            "SELECT id FROM questions ORDER BY RANDOM() LIMIT ?", [5 - len(qids)])]
    cfg = {"clusters": ["five"], "n": len(qids), "minutes": 10, "due_at": now + 14 * 86400}
    eid = db.execute(
        "INSERT INTO exams(title,kind,config,created_by,created_at) VALUES(?,?,?,?,?)",
        ("教师布置·五步处置专项（5 题）", "teacher", json.dumps(cfg, ensure_ascii=False), t["id"], now)).lastrowid
    for i, qid in enumerate(qids):
        db.execute("INSERT INTO exam_items(exam_id,question_id,seq,score) VALUES(?,?,?,?)", (eid, qid, i + 1, 10))
    print("[seed] 演示教师布置 1 条（五步处置 5 题 · 10 分钟 · 14 天有效）")


def seed_demo_data(db):
    """给 S2026001 预置学习痕迹基线（可重入：先清后插）。"""
    sid = db.execute("SELECT id FROM users WHERE student_no='S2026001'").fetchone()
    if not sid:
        return
    sid = sid[0]
    now = int(time.time())
    for t in ("mastery", "wrong_records", "chat_logs", "points_log", "checkins", "user_badges"):
        db.execute(f"DELETE FROM {t} WHERE student_id=?", (sid,))  # nosec B608（人工确认：参数化/白名单常量拼接）
    levels = {"morse": 62, "env": 71, "five": 41, "fracture": 38, "record": 55, "cpr": 29}
    for cid, lv in levels.items():
        db.execute(
            "INSERT INTO mastery(student_id,cluster_id,level,n_correct,n_total,updated_at) VALUES(?,?,?,?,?,?)",
            (sid, cid, lv, int(lv / 10), 20, now),
        )
    db.execute("INSERT OR REPLACE INTO points_cache(student_id,points) VALUES(?,128)", (sid,))
    for delta, reason in [(5, "每日签到"), (5, "每日签到"), (2, "AI 问答"), (5, "练习答对"), (10, "错题复习答对"), (101, "课程开通奖励")]:
        db.execute("INSERT INTO points_log(student_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
                   (sid, delta, reason, "", now - 86400 * 3))
    # 预置 3 道错题（取五步处置簇真题）
    qs = db.execute("SELECT id FROM questions WHERE cluster_id='five' LIMIT 3").fetchall()
    for q in qs:
        db.execute("INSERT OR IGNORE INTO wrong_records(student_id,question_id,first_wrong_at,review_count,correct_streak,last_review_at,due_at,status) VALUES(?,?,?,?,?,?,?,?)",
                   (sid, q["id"], now - 86400, 0, 0, None, now + 86400, "active"))
    sample_answer = (
        "【岗】养老护理员国家职业技能标准（2019 年版）将『风险应对』列为五级/四级核心技能：能识别老年人跌倒风险因素，"
        "按 MZ/T 185—2021 完成风险评估与环境排查，发现跌倒后立即报告并规范处置。"
        "（来源：养老护理员国家职业技能标准-风险应对.md（01-岗/…））\n"
        "【课】课程标准项目二『跌倒的防护与急救』四个任务：Morse 量表评估 → 环境隐患五查 → 应急处置五步法（评估意识与伤情 → "
        "不急于搬动 → 呼叫支援 → 按预案处置 → 记录上报）→ 疑似骨折就地制动；实训任务单按情景 A/B 考核。\n"
        "【赛】山东省技能兴鲁大赛养老护理员赛项：跌倒应急处置为独立情景模块，风险识别为给分项，"
        "『未制动即搬动』属重扣分点；12 分钟模块内处置顺序与记录上报为评分主线。\n"
        "【证】养老护理员（三级）实操考核『跌倒预防与应急处理』：M8 分型处理 15 分，"
        "『不要急于扶起、分情况处理』为核心理念；理论考 Morse 分层切点（<25 低危 / 25–44 中危 / ≥45 高危）。"
    )
    db.execute(
        "INSERT INTO chat_logs(student_id,dsh_session_id,question,answer,clusters_touched,created_at) VALUES(?,?,?,?,?,?)",
        (sid, "", "老年人跌倒", sample_answer, "five,fracture", now - 86400 * 2),
    )


# ---------- 通用小工具 ----------
def get_setting(db, key, default=None):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(db, key, value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))


def add_study(db, student_id, type_, minutes, ref=""):
    """学时事件：AI 问答按实际耗时、练习按交卷时长、复习按次计 1 分钟。"""
    minutes = max(0.0, min(float(minutes) or 0, 240.0))
    if minutes < 0.05:
        return
    db.execute(
        "INSERT INTO study_events(student_id,type,minutes,ref,created_at) VALUES(?,?,?,?,?)",
        (student_id, type_, round(minutes, 1), ref, int(time.time())))


def student_hours(db, student_id):
    r = db.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=?",
                   (student_id,)).fetchone()
    return round(r["m"] or 0, 1)


def add_points(db, student_id, delta, reason, ref=""):
    db.execute("INSERT OR IGNORE INTO points_cache(student_id,points) VALUES(?,0)", (student_id,))
    db.execute("UPDATE points_cache SET points = points + ? WHERE student_id=?", (delta, student_id))
    db.execute("INSERT INTO points_log(student_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)",
               (student_id, delta, reason, ref, int(time.time())))


def update_mastery(db, student_id, cluster_id, score_rate, n=1):
    """score_rate 0-1；指数滑动 0.7/0.3；提问触达传 rate=None 只 +2 封顶。"""
    if cluster_id not in CLUSTER_IDS or cluster_id == "general":
        return
    row = db.execute("SELECT level,n_correct,n_total FROM mastery WHERE student_id=? AND cluster_id=?",
                     (student_id, cluster_id)).fetchone()
    now = int(time.time())
    if row is None:
        lv = 0.0
        nc, nt = 0, 0
    else:
        lv, nc, nt = row["level"], row["n_correct"], row["n_total"]
    if score_rate is None:
        lv = min(100.0, lv + 2.0)
    else:
        lv = 0.7 * lv + 0.3 * (score_rate * 100)
        nc += int(score_rate >= 0.5)
        nt += n
    db.execute(
        "INSERT INTO mastery(student_id,cluster_id,level,n_correct,n_total,updated_at) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(student_id,cluster_id) DO UPDATE SET level=excluded.level, n_correct=excluded.n_correct, n_total=excluded.n_total, updated_at=excluded.updated_at",
        (student_id, cluster_id, round(lv, 1), nc, nt, now),
    )


def clusters_touched(question_text):
    """从提问文本粗判触达簇（24h 去重由调用方处理）"""
    t = question_text.lower()
    hit = []
    for cid, cname in CLUSTERS:
        kws = {
            "morse": ["morse", "量表", "评估", "风险分"],
            "env": ["地面", "环境", "照明", "扶手", "防滑", "预防"],
            "five": ["跌倒后", "倒地", "急救", "处置", "意识", "搬运", "急救处理"],
            "fracture": ["骨折", "髋部", "股骨颈"],
            "record": ["记录", "上报", "不良事件"],
            "cpr": ["cpr", "心肺复苏", "按压"],
        }[cid]
        if any(k in t for k in kws):
            hit.append(cid)
    return hit or ["five"]


def ensure_badge(db, student_id, badge_id):
    cur = db.execute("INSERT OR IGNORE INTO user_badges(student_id,badge_id,earned_at) VALUES(?,?,?)",
                     (student_id, badge_id, int(time.time())))
    return cur.rowcount > 0


def grant_mastery_badges(db, student_id):
    """掌握度 ≥60 的簇点亮对应勋章；六簇全 ≥60 点亮 b_all60。"""
    rows = db.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (student_id,)).fetchall()
    lv = {r["cluster_id"]: r["level"] for r in rows}
    for cid, _ in CLUSTERS:
        if lv.get(cid, 0) >= 60:
            ensure_badge(db, student_id, "b_" + cid)
    if all(lv.get(cid, 0) >= 60 for cid, _ in CLUSTERS):
        ensure_badge(db, student_id, "b_all60")