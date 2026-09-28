# -*- coding: utf-8 -*-
"""管理后台 · 业务管理端点（B 期）：
轮播 / 课程预告 / 考试管理 / 学生 / 账号 / 培训 / 统计。教师端全部走 require_teacher。
学生端只读消费走 /api/content/*（轮播/预告）。
"""
import csv
import io
import json
import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .auth import require_teacher, current_user

router = APIRouter(prefix="/api/admin", tags=["manage"])
content_router = APIRouter(prefix="/api/content", tags=["content"])
meta_router = APIRouter(prefix="/api/meta", tags=["meta"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ================= 轮播图 =================
class BannerIn(BaseModel):
    title: str
    tag: str = ""
    sub: str = ""
    image: str = ""
    link: str = "/"
    sort: int = 0
    enabled: int = 1


@router.get("/banners")
def banners_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    rows = d.execute("SELECT * FROM banners ORDER BY sort, id").fetchall()
    d.close()
    return {"items": [dict(r) for r in rows]}


def _check_title(title: str):
    if not (title or "").strip():
        raise HTTPException(400, "标题不能为空（纯空格也不行）")
    return title.strip()


@router.post("/banners")
def banners_create(b: BannerIn, u: dict = Depends(require_teacher)):
    title = _check_title(b.title)
    d = db.get_db()
    cur = d.execute(
        "INSERT INTO banners(title,tag,sub,image,link,sort,enabled,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (title, b.tag.strip(), b.sub.strip(), b.image, b.link.strip() or "/", b.sort, b.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid}


@router.put("/banners/{bid}")
def banners_update(bid: int, b: BannerIn, u: dict = Depends(require_teacher)):
    title = _check_title(b.title)
    d = db.get_db()
    cur = d.execute(
        "UPDATE banners SET title=?,tag=?,sub=?,image=?,link=?,sort=?,enabled=? WHERE id=?",
        (title, b.tag.strip(), b.sub.strip(), b.image, b.link.strip() or "/", b.sort, b.enabled, bid))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "轮播卡不存在（可能已被删除）")
    return {"ok": True}


@router.delete("/banners/{bid}")
def banners_delete(bid: int, u: dict = Depends(require_teacher)):
    d = db.get_db()
    cur = d.execute("DELETE FROM banners WHERE id=?", (bid,))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "轮播卡不存在（可能已被删除）")
    return {"ok": True}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...), u: dict = Depends(require_teacher)):
    """图片上传（轮播图用）：仅接受真实图片扩展名，落 backend/uploads/，返回 /uploads/xxx。"""
    data = await file.read()
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(400, "图片超过 4MB 上限")
    if not file.filename or "." not in file.filename:
        raise HTTPException(400, "无法识别的文件名，请上传 png/jpg/webp/gif 图片")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        raise HTTPException(400, f"不支持的文件类型 .{ext}（仅 png/jpg/jpeg/webp/gif）")
    name = f"banner-{int(time.time())}-{uuid.uuid4().hex[:6]}.{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return {"ok": True, "url": f"/uploads/{name}"}


# ================= 课程预告 =================
class NoticeIn(BaseModel):
    title: str
    summary: str = ""
    content: str = ""
    start_date: str = ""
    end_date: str = ""
    pinned: int = 0
    enabled: int = 1


@router.get("/announcements")
def notices_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    rows = d.execute("SELECT * FROM announcements ORDER BY pinned DESC, id DESC").fetchall()
    d.close()
    return {"items": [dict(r) for r in rows]}


@router.post("/announcements")
def notices_create(n: NoticeIn, u: dict = Depends(require_teacher)):
    title = _check_title(n.title)
    d = db.get_db()
    cur = d.execute(
        "INSERT INTO announcements(title,summary,content,start_date,end_date,pinned,enabled,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (title, n.summary.strip(), n.content.strip(), n.start_date, n.end_date, n.pinned, n.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid}


@router.put("/announcements/{nid}")
def notices_update(nid: int, n: NoticeIn, u: dict = Depends(require_teacher)):
    title = _check_title(n.title)
    d = db.get_db()
    cur = d.execute(
        "UPDATE announcements SET title=?,summary=?,content=?,start_date=?,end_date=?,pinned=?,enabled=? WHERE id=?",
        (title, n.summary.strip(), n.content.strip(), n.start_date, n.end_date, n.pinned, n.enabled, nid))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "公告不存在（可能已被删除）")
    return {"ok": True}


@router.delete("/announcements/{nid}")
def notices_delete(nid: int, u: dict = Depends(require_teacher)):
    d = db.get_db()
    cur = d.execute("DELETE FROM announcements WHERE id=?", (nid,))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "公告不存在（可能已被删除）")
    return {"ok": True}


# ================= 学生端消费（轮播/预告） =================
@content_router.get("/banners")
def pub_banners():
    d = db.get_db()
    rows = d.execute("SELECT id,title,tag,sub,image,link,sort FROM banners WHERE enabled=1 ORDER BY sort, id").fetchall()
    d.close()
    return {"items": [dict(r) for r in rows]}


@content_router.get("/announcements")
def pub_notices():
    today = time.strftime("%Y-%m-%d")
    d = db.get_db()
    rows = d.execute(
        "SELECT id,title,summary,created_at FROM announcements WHERE enabled=1 "
        "AND (start_date='' OR start_date<=?) AND (end_date='' OR end_date>=?) ORDER BY pinned DESC, id DESC LIMIT 10",
        (today, today)).fetchall()
    d.close()
    return {"items": [dict(r) for r in rows]}


# 六簇元数据（id/名/色 + 实时题量）：前端卡片不再写死题数
_CLUSTERS_META = [
    ("morse", "Morse评估", "#3B82F6", "Morse 跌倒风险评估"),
    ("env", "环境防控", "#22C55E", "环境风险防控"),
    ("five", "五步处置", "#E4393C", "跌倒五步处置"),
    ("fracture", "骨折识别", "#F5A623", "骨折识别与固定"),
    ("record", "记录上报", "#8B5CF6", "记录与上报"),
    ("cpr", "CPR启动", "#0EA5E9", "CPR 与急救启动"),
]


@meta_router.get("/clusters")
def meta_clusters():
    d = db.get_db()
    counts = {r["cluster_id"]: r["c"] for r in
              d.execute("SELECT cluster_id, COUNT(*) c FROM questions WHERE cluster_id!='general' GROUP BY cluster_id")}
    d.close()
    return {"items": [
        {"id": cid, "name": short, "full": full, "color": color, "qcount": counts.get(cid, 0)}
        for cid, short, color, full in _CLUSTERS_META
    ]}


# ================= 考试管理 =================
def _attempt_row(d, r):
    return {
        "id": r["id"], "student_id": r["student_id"], "student_no": r["student_no"], "student_name": r["name"],
        "exam_title": r["exam_title"], "kind": r["kind"],
        "started_at": r["started_at"], "submitted_at": r["submitted_at"],
        "score": r["score"], "status": r["status"],
        "minutes": round(max(0, (r["submitted_at"] or 0) - (r["started_at"] or 0)) / 60, 1) if r["submitted_at"] else None,
    }


_EXAM_STATUS = {"started", "done", "aborted", "expired"}
_STATUS_CN = {"started": "进行中", "done": "已完成", "aborted": "已放弃", "expired": "已超时"}
_KIND_CN = {"daily": "日常练习", "mock": "模拟考", "teacher": "教师布置", "wrong": "错题重答"}


@router.get("/exams")
def exams_list(status: str = "", student_id: int = 0, u: dict = Depends(require_teacher)):
    """考试记录（attempts 视图）：学生 × 试卷 × 得分 × 用时。"""
    if status and status not in _EXAM_STATUS:
        raise HTTPException(400, f"状态参数无效：{status}（可选：{' / '.join(sorted(_EXAM_STATUS))}）")
    d = db.get_db()
    sql = ("SELECT a.id, a.student_id, u.student_no, u.name, e.title exam_title, e.kind, "
           "a.started_at, a.submitted_at, a.score, a.status "
           "FROM attempts a JOIN users u ON u.id=a.student_id LEFT JOIN exams e ON e.id=a.exam_id "
           "WHERE 1=1")
    args = []
    if status:
        sql += " AND a.status=?"
        args.append(status)
    if student_id:
        sql += " AND a.student_id=?"
        args.append(student_id)
    sql += " ORDER BY a.id DESC LIMIT 200"
    rows = d.execute(sql, args).fetchall()
    d.close()
    return {"items": [_attempt_row(d, r) for r in rows]}


@router.get("/exams/export")
def exams_export(status: str = "", student_id: int = 0, u: dict = Depends(require_teacher)):
    """CSV 导出（浏览器下载）。注意：必须声明在 /exams/{attempt_id} 之前。"""
    if status and status not in _EXAM_STATUS:
        raise HTTPException(400, f"状态参数无效：{status}（可选：{' / '.join(sorted(_EXAM_STATUS))}）")
    d = db.get_db()
    sql = ("SELECT u.student_no, u.name, e.title exam_title, e.kind, a.started_at, a.submitted_at, a.score, a.status "
           "FROM attempts a JOIN users u ON u.id=a.student_id LEFT JOIN exams e ON e.id=a.exam_id WHERE 1=1")
    args = []
    if status:
        sql += " AND a.status=?"
        args.append(status)
    if student_id:
        sql += " AND a.student_id=?"
        args.append(student_id)
    sql += " ORDER BY a.id"
    rows = d.execute(sql, args).fetchall()
    d.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["学号", "姓名", "试卷", "类型", "开始时间", "交卷时间", "得分", "状态"])
    for r in rows:
        w.writerow([
            r["student_no"], r["name"], r["exam_title"], _KIND_CN.get(r["kind"], r["kind"]),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(r["started_at"] or 0)),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(r["submitted_at"] or 0)) if r["submitted_at"] else "",
            r["score"] if r["score"] is not None else "", _STATUS_CN.get(r["status"], r["status"]),
        ])
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=exams.csv"})


@router.get("/exams/{attempt_id}")
def exam_detail(attempt_id: int, u: dict = Depends(require_teacher)):
    """单次考试逐题明细。"""
    d = db.get_db()
    att = d.execute(
        "SELECT a.*, u.student_no, u.name, e.title exam_title, e.kind "
        "FROM attempts a JOIN users u ON u.id=a.student_id LEFT JOIN exams e ON e.id=a.exam_id WHERE a.id=?",
        (attempt_id,)).fetchone()
    if not att:
        raise HTTPException(404, "考试记录不存在")
    items = []
    for r in d.execute(
            "SELECT a.student_answer, a.correct, a.score, a.feedback, q.id qid, q.stem, q.qtype, q.options, q.answer, q.source_doc, q.cluster_id "
            "FROM answers a JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=? ORDER BY q.id",
            (attempt_id,)):
        opts = json.loads(r["options"]) or []
        if r["qtype"] == "判断" or not opts:
            opts = ["对（A）", "错（B）"]
        items.append({
            "question_id": r["qid"], "stem": r["stem"], "type": r["qtype"], "options": opts,
            "answer": r["answer"], "student_answer": r["student_answer"],
            "correct": r["correct"], "score": r["score"], "feedback": r["feedback"],
            "source_doc": r["source_doc"], "cluster": r["cluster_id"],
        })
    d.close()
    return {"attempt": _attempt_row(d, att), "items": items}


# ================= 学生管理 / 账号管理 =================
@router.get("/students")
def students_list(u: dict = Depends(require_teacher)):
    """学生列表：8 个聚合各一条批量 GROUP BY（原逐人 8 查询 → N×8 全表扫描）。"""
    d = db.get_db()
    rows = d.execute(
        "SELECT id, student_no, name, role, enabled, created_at FROM users WHERE role='student' ORDER BY id").fetchall()
    ids = [r["id"] for r in rows]
    stats = {i: {"points": 0, "mastery": {}, "practice_count": 0, "ai_ask": 0,
                 "wrong_active": 0, "badge_count": 0, "enroll_count": 0, "hours": 0.0} for i in ids}
    if ids:
        ph = ",".join("?" * len(ids))
        for m in d.execute(f"SELECT student_id, cluster_id, level FROM mastery WHERE student_id IN ({ph})", ids):
            stats[m["student_id"]]["mastery"][m["cluster_id"]] = m["level"]
        for r in d.execute(f"SELECT student_id, points FROM points_cache WHERE student_id IN ({ph})", ids):
            stats[r["student_id"]]["points"] = r["points"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM attempts WHERE student_id IN ({ph}) AND status='done' GROUP BY student_id", ids):
            stats[r["student_id"]]["practice_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM chat_logs WHERE student_id IN ({ph}) AND answer!='' GROUP BY student_id", ids):
            stats[r["student_id"]]["ai_ask"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM wrong_records WHERE student_id IN ({ph}) AND status='active' GROUP BY student_id", ids):
            stats[r["student_id"]]["wrong_active"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM user_badges WHERE student_id IN ({ph}) GROUP BY student_id", ids):
            stats[r["student_id"]]["badge_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM training_enrolls WHERE student_id IN ({ph}) GROUP BY student_id", ids):
            stats[r["student_id"]]["enroll_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id IN ({ph}) GROUP BY student_id", ids):
            stats[r["student_id"]]["hours"] = round(r["m"] or 0, 1)
    d.close()
    items = []
    for r in rows:
        s = stats[r["id"]]
        lv = s["mastery"]
        s["avg_mastery"] = round(sum(lv.values()) / len(lv), 1) if lv else 0
        items.append({**dict(r), **s})
    return {"items": items}


class StudentIn(BaseModel):
    name: str
    student_no: str = ""
    password: str = "123456"
    enabled: int = 1


@router.post("/students")
def students_create(s: StudentIn, u: dict = Depends(require_teacher)):
    import bcrypt
    d = db.get_db()
    sno = s.student_no.strip() or ""
    if not sno:
        n = d.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()["c"]
        sno = f"S2026{n + 1:03d}"
        while d.execute("SELECT 1 FROM users WHERE student_no=?", (sno,)).fetchone():
            n += 1
            sno = f"S2026{n + 1:03d}"
    elif d.execute("SELECT 1 FROM users WHERE student_no=?", (sno,)).fetchone():
        raise HTTPException(400, "学号已存在")
    h = bcrypt.hashpw(s.password.encode(), bcrypt.gensalt(4)).decode()
    cur = d.execute(
        "INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at) VALUES(?,?,?,?,?,?)",
        (sno, s.name, "student", h, s.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid, "student_no": sno}


@router.put("/students/{uid}")
def students_update(uid: int, s: StudentIn, u: dict = Depends(require_teacher)):
    import bcrypt
    d = db.get_db()
    if not d.execute("SELECT 1 FROM users WHERE id=? AND role='student'", (uid,)).fetchone():
        raise HTTPException(404, "学生不存在")
    sets, args = [], []
    if s.name:
        sets.append("name=?"); args.append(s.name)
    if s.password:
        sets.append("pwd_hash=?"); args.append(bcrypt.hashpw(s.password.encode(), bcrypt.gensalt(4)).decode())
    sets.append("enabled=?"); args.append(s.enabled)
    args.append(uid)
    d.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", args)
    d.commit()
    d.close()
    return {"ok": True}


@router.get("/accounts")
def accounts_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    rows = d.execute("SELECT id, student_no, name, role, enabled, created_at FROM users ORDER BY role DESC, id").fetchall()
    d.close()
    return {"items": [dict(r) for r in rows]}


class AccountIn(BaseModel):
    name: str
    role: str = "student"
    student_no: str = ""
    password: str = "123456"
    enabled: int = 1


@router.post("/accounts")
def accounts_create(a: AccountIn, u: dict = Depends(require_teacher)):
    import bcrypt
    d = db.get_db()
    sno = a.student_no.strip() or ""
    prefix = "T" if a.role == "teacher" else "S"
    if not sno:
        n = d.execute("SELECT COUNT(*) c FROM users WHERE role=?", (a.role,)).fetchone()["c"]
        sno = f"{prefix}2026{n + 1:03d}"
        while d.execute("SELECT 1 FROM users WHERE student_no=?", (sno,)).fetchone():
            n += 1
            sno = f"{prefix}2026{n + 1:03d}"
    elif d.execute("SELECT 1 FROM users WHERE student_no=?", (sno,)).fetchone():
        raise HTTPException(400, "账号已存在")
    if a.role not in ("student", "teacher"):
        raise HTTPException(400, "角色仅支持 student/teacher")
    h = bcrypt.hashpw(a.password.encode(), bcrypt.gensalt(4)).decode()
    cur = d.execute(
        "INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at) VALUES(?,?,?,?,?,?)",
        (sno, a.name, a.role, h, a.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid, "student_no": sno}


@router.delete("/accounts/{uid}")
def accounts_delete(uid: int, u: dict = Depends(require_teacher)):
    """物理删除账号及其学习痕迹（不可恢复，慎用）。"""
    if uid == u["id"]:
        raise HTTPException(400, "不能删除自己的账号")
    d = db.get_db()
    if not d.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        d.close()
        raise HTTPException(404, "账号不存在")
    d.execute("DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id=?)", (uid,))
    d.execute("DELETE FROM ai_grades WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id=?)", (uid,))
    # 教师创建的考卷一并删除（否则 exams 表残留死行，FK 悬空）
    d.execute("DELETE FROM exam_items WHERE exam_id IN (SELECT id FROM exams WHERE created_by=?)", (uid,))
    d.execute("DELETE FROM exams WHERE created_by=?", (uid,))
    for t in ("mastery", "wrong_records", "chat_logs", "points_log", "checkins",
              "user_badges", "student_sessions", "attempts", "points_cache",
              "study_events", "training_enrolls"):
        d.execute(f"DELETE FROM {t} WHERE student_id=?", (uid,))
    d.execute("DELETE FROM users WHERE id=?", (uid,))
    d.commit()
    d.close()
    return {"ok": True}


class AccountPatch(BaseModel):
    # Optional：前端「重置密码」时不传 enabled（原默认值会把它悄悄重置回 1）
    enabled: int | None = None
    password: str = ""


@router.put("/accounts/{uid}")
def accounts_update(uid: int, a: AccountPatch, u: dict = Depends(require_teacher)):
    import bcrypt
    if a.enabled is None and not a.password:
        raise HTTPException(400, "没有要修改的内容（enabled 或 password 至少传一个）")
    d = db.get_db()
    if a.enabled is not None and a.enabled == 0 and uid == u["id"]:
        d.close()
        raise HTTPException(400, "不能停用自己的账号")
    if not d.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        d.close()
        raise HTTPException(404, "账号不存在")
    sets, args = [], []
    if a.enabled is not None:
        sets.append("enabled=?"); args.append(a.enabled)
    if a.password:
        sets.append("pwd_hash=?")
        args.append(bcrypt.hashpw(a.password.encode(), bcrypt.gensalt(4)).decode())
    args.append(uid)
    d.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", args)
    d.commit()
    d.close()
    return {"ok": True}


# ================= 培训管理 =================
class TrainingIn(BaseModel):
    title: str
    batch: str = ""
    start_date: str = ""
    end_date: str = ""
    capacity: int = Field(30, ge=1)  # 0/负数无意义且会让报名逻辑失去上限
    note: str = ""
    student_ids: list = []


def _training_row(d, r):
    n_enroll = d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE training_id=?", (r["id"],)).fetchone()["c"]
    n_done = d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE training_id=? AND status='done'", (r["id"],)).fetchone()["c"]
    teacher = d.execute("SELECT name FROM users WHERE id=?", (r["teacher_id"],)).fetchone()
    return {
        **dict(r),
        "teacher_name": teacher["name"] if teacher else "",
        "enrolled": n_enroll, "done": n_done,
        "rate": round(n_done * 100 / n_enroll) if n_enroll else 0,  # 整百分比（CT-12）
    }


@router.get("/trainings")
def trainings_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    rows = d.execute("SELECT * FROM trainings ORDER BY id DESC").fetchall()
    out = [_training_row(d, r) for r in rows]
    for t in out:
        t["students"] = [
            {"id": e["student_id"], "student_no": e["student_no"], "name": e["name"], "status": e["status"]}
            for e in d.execute(
                "SELECT te.student_id, u.student_no, u.name, te.status FROM training_enrolls te "
                "JOIN users u ON u.id=te.student_id WHERE te.training_id=? ORDER BY u.id", (t["id"],)).fetchall()
        ]
    d.close()
    return {"items": out}


@router.post("/trainings")
def trainings_create(t: TrainingIn, u: dict = Depends(require_teacher)):
    title = _check_title(t.title)
    d = db.get_db()
    cur = d.execute(
        "INSERT INTO trainings(title,batch,start_date,end_date,teacher_id,capacity,note,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (title, t.batch.strip(), t.start_date, t.end_date, u["id"], t.capacity, t.note.strip(), int(time.time())))
    tid = cur.lastrowid
    for sid in t.student_ids:
        d.execute(
            "INSERT OR IGNORE INTO training_enrolls(training_id,student_id,status,enrolled_at) VALUES(?,?,?,?)",
            (tid, sid, "enrolled", int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": tid}


@router.put("/trainings/{tid}")
def trainings_update(tid: int, t: TrainingIn, u: dict = Depends(require_teacher)):
    title = _check_title(t.title)
    d = db.get_db()
    cur = d.execute(
        "UPDATE trainings SET title=?,batch=?,start_date=?,end_date=?,capacity=?,note=? WHERE id=?",
        (title, t.batch.strip(), t.start_date, t.end_date, t.capacity, t.note.strip(), tid))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "培训不存在（可能已被删除）")
    return {"ok": True}


@router.post("/trainings/{tid}/enroll")
def trainings_enroll(tid: int, body: dict, u: dict = Depends(require_teacher)):
    """body: {student_ids: [...], status?: 'enrolled'|'done'}（追加或批量改状态）"""
    d = db.get_db()
    tr = d.execute("SELECT capacity FROM trainings WHERE id=?", (tid,)).fetchone()
    if not tr:
        d.close()
        raise HTTPException(404, "培训不存在")
    status = body.get("status") or "enrolled"
    if status not in ("enrolled", "done"):
        d.close()
        raise HTTPException(400, "status 仅支持 enrolled/done")
    sids = body.get("student_ids") or []
    # 容量校验：新报名（非已报名者）超出 capacity 直接拒绝
    if status == "enrolled" and sids:
        ph = ",".join("?" * len(sids))
        already = {r["student_id"] for r in d.execute(
            f"SELECT student_id FROM training_enrolls WHERE training_id=? AND student_id IN ({ph})",
            [tid] + sids)}
        n_cur = d.execute("SELECT COUNT(*) c FROM training_enrolls WHERE training_id=?", (tid,)).fetchone()["c"]
        n_new = len([s for s in sids if s not in already])
        if n_cur + n_new > tr["capacity"]:
            d.close()
            raise HTTPException(400, f"报名已满（容量 {tr['capacity']}，当前 {n_cur}，新增 {n_new}）")
    for sid in sids:
        d.execute(
            "INSERT INTO training_enrolls(training_id,student_id,status,enrolled_at) VALUES(?,?,?,?) "
            "ON CONFLICT(training_id,student_id) DO UPDATE SET status=excluded.status",
            (tid, sid, status, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True}


@router.post("/trainings/{tid}/students/{uid}/status")
def trainings_set_status(tid: int, uid: int, body: dict, u: dict = Depends(require_teacher)):
    d = db.get_db()
    status = (body or {}).get("status")
    if status not in ("enrolled", "done"):
        d.close()
        raise HTTPException(400, "status 仅支持 enrolled/done")
    cur = d.execute("UPDATE training_enrolls SET status=? WHERE training_id=? AND student_id=?", (status, tid, uid))
    d.commit()
    d.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "该学生未报名此培训")
    return {"ok": True}


@router.delete("/trainings/{tid}")
def trainings_delete(tid: int, u: dict = Depends(require_teacher)):
    d = db.get_db()
    d.execute("DELETE FROM training_enrolls WHERE training_id=?", (tid,))
    d.execute("DELETE FROM trainings WHERE id=?", (tid,))
    d.commit()
    d.close()
    return {"ok": True}


# ================= 统计（数据大屏 / 学时 / 培训情况） =================
def _day(n):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - n * 86400))


@router.get("/stats/overview")
def stats_overview(u: dict = Depends(require_teacher)):
    """数据大屏 + 概况：核心指标 / 7 日趋势 / 六簇分布 / 题型分布 / 排行榜 / 学时。"""
    d = db.get_db()
    now = int(time.time())
    today = _day(0)
    n_students = d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()["c"]
    n_questions = d.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
    n_asks = d.execute("SELECT COUNT(*) c FROM chat_logs WHERE answer!=''").fetchone()["c"]
    n_practices = d.execute("SELECT COUNT(*) c FROM attempts WHERE status='done'").fetchone()["c"]
    total_hours = d.execute("SELECT COALESCE(SUM(minutes),0) m FROM study_events").fetchone()["m"]
    avg_mastery = d.execute("SELECT COALESCE(AVG(level),0) m FROM mastery").fetchone()["m"]

    _ACTIVE_SRC = ("SELECT student_id FROM checkins WHERE date>=? "
                   "UNION SELECT student_id FROM chat_logs WHERE created_at>=? "
                   "UNION SELECT student_id FROM attempts WHERE started_at>=? "
                   "UNION SELECT student_id FROM study_events WHERE created_at>=?")

    def _active_params(days):
        return (today if days == 1 else _day(days - 1),
                now - days * 86400, now - days * 86400, now - days * 86400)

    def active_days(days):
        r = d.execute(f"SELECT COUNT(DISTINCT student_id) c FROM ({_ACTIVE_SRC})",
                      _active_params(days)).fetchone()
        return r["c"]

    def active_list(days):
        """活跃学生明细（启用学生，供指标卡下钻展示）。"""
        rows = d.execute(
            f"SELECT u.student_no, u.name FROM users u WHERE u.role='student' AND u.enabled=1 "
            f"AND u.id IN ({_ACTIVE_SRC}) ORDER BY u.student_no",
            _active_params(days)).fetchall()
        return [{"name": r["name"], "student_no": r["student_no"]} for r in rows]

    # 7 日趋势：points_log / chat_logs 各扫一次（原 14 次）
    t0 = now - 7 * 86400
    pts_by_day = [0] * 7
    for r in d.execute("SELECT created_at, delta FROM points_log WHERE created_at>=?", (t0,)):
        i = (r["created_at"] - t0) // 86400
        if 0 <= i < 7:
            pts_by_day[i] += r["delta"]
    asks_by_day = [0] * 7
    for r in d.execute("SELECT created_at FROM chat_logs WHERE created_at>=? AND answer!=''", (t0,)):
        i = (r["created_at"] - t0) // 86400
        if 0 <= i < 7:
            asks_by_day[i] += 1
    trend = [{"date": _day(i), "points": pts_by_day[i], "asks": asks_by_day[i]} for i in range(7)]

    # 六簇平均掌握度：一条 GROUP BY（原 6 次）
    clusters = [{"cluster": cid, "name": cname, "level": 0, "n": 0} for cid, cname in db.CLUSTER_NAMES.items()]
    cidx = {c["cluster"]: c for c in clusters}
    for r in d.execute("SELECT cluster_id, AVG(level) m, COUNT(DISTINCT student_id) n FROM mastery "
                       "WHERE cluster_id!='general' GROUP BY cluster_id"):
        if r["cluster_id"] in cidx:
            cidx[r["cluster_id"]]["level"] = round(r["m"] or 0, 1)
            cidx[r["cluster_id"]]["n"] = r["n"]

    # 题型分布
    qtypes = {}
    for r in d.execute("SELECT qtype, COUNT(*) c FROM questions GROUP BY qtype"):
        qtypes[r["qtype"]] = r["c"]

    # 排行榜三表各扫一次（原 3×N 次）
    students = d.execute(
        "SELECT id, student_no, name FROM users WHERE role='student' AND enabled=1 ORDER BY id").fetchall()
    pts = {r["student_id"]: r["points"] for r in d.execute("SELECT student_id, points FROM points_cache")}
    mst = {r["student_id"]: round(r["m"] or 0, 1) for r in
           d.execute("SELECT student_id, AVG(level) m FROM mastery WHERE cluster_id!='general' GROUP BY student_id")}
    hrs = {r["student_id"]: round(r["m"] or 0, 1) for r in
           d.execute("SELECT student_id, COALESCE(SUM(minutes),0) m FROM study_events GROUP BY student_id")}

    def rank(field):
        get = pts if field == "points" else (mst if field == "mastery" else hrs)
        items = [{"id": s["id"], "student_no": s["student_no"], "name": s["name"], "value": get.get(s["id"], 0)}
                 for s in students]
        items.sort(key=lambda x: -x["value"])
        for i, it in enumerate(items):
            it["rank"] = i + 1
        return items[:10]

    # 班级弱项（各簇答错率）：一条 JOIN GROUP BY（原 6 次）
    weak = []
    for r in d.execute(
            "SELECT q.cluster_id, COUNT(*) n, SUM(1-a.correct) wrong FROM answers a "
            "JOIN questions q ON q.id=a.question_id WHERE a.graded_by LIKE 'rules%' GROUP BY q.cluster_id"):
        if r["n"] and r["cluster_id"] in db.CLUSTER_NAMES:
            weak.append({"cluster": r["cluster_id"], "name": db.CLUSTER_NAMES[r["cluster_id"]],
                         "n": r["n"], "wrong": r["wrong"] or 0,
                         "rate": round((r["wrong"] or 0) * 100 / r["n"], 1)})
    weak.sort(key=lambda x: -x["rate"])

    # 学生学时表（上面 hrs 已算好）
    hours_rows = [{"student_no": s["student_no"], "name": s["name"], "hours": hrs.get(s["id"], 0)} for s in students]
    hours_rows.sort(key=lambda x: -x["hours"])

    active = {"today": active_days(1), "week": active_days(7),
              "today_list": active_list(1), "week_list": active_list(7)}
    rank_points = rank("points")
    rank_mastery = rank("mastery")
    rank_hours = rank("hours")
    d.close()
    return {
        "cards": {
            "students": n_students, "questions": n_questions, "asks": n_asks,
            "practices": n_practices, "hours": round(total_hours or 0, 1),
            "avg_mastery": round(avg_mastery or 0, 1),
        },
        "active": active,
        "trend": trend,
        "clusters": clusters,
        "qtypes": qtypes,
        "rank_points": rank_points,
        "rank_mastery": rank_mastery,
        "rank_hours": rank_hours,
        "weak_clusters": weak,
        "hours": hours_rows,
    }


@router.get("/stats/trainings")
def stats_trainings(u: dict = Depends(require_teacher)):
    """培训情况统计：各培训完成度 + 学生培训画像 + 教师带训情况。"""
    d = db.get_db()
    trainings = []
    for r in d.execute("SELECT * FROM trainings ORDER BY id DESC").fetchall():
        trainings.append(_training_row(d, r))
    # 学生培训画像：4 张表各扫一次（原 4×N 次）
    srows = d.execute("SELECT id, student_no, name FROM users WHERE role='student' AND enabled=1 ORDER BY id").fetchall()
    enroll = {}
    for r in d.execute("SELECT student_id, COUNT(*) n, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done "
                       "FROM training_enrolls GROUP BY student_id"):
        enroll[r["student_id"]] = (r["n"], r["done"] or 0)
    prac = {r["student_id"]: r["c"] for r in
            d.execute("SELECT student_id, COUNT(*) c FROM attempts WHERE status='done' GROUP BY student_id")}
    ask = {r["student_id"]: r["c"] for r in
           d.execute("SELECT student_id, COUNT(*) c FROM chat_logs WHERE answer!='' GROUP BY student_id")}
    hrs = {r["student_id"]: round(r["m"] or 0, 1) for r in
           d.execute("SELECT student_id, COALESCE(SUM(minutes),0) m FROM study_events GROUP BY student_id")}
    students = []
    for r in srows:
        n, done = enroll.get(r["id"], (0, 0))
        students.append({
            "id": r["id"], "student_no": r["student_no"], "name": r["name"],
            "enrolled": n, "done": done, "hours": hrs.get(r["id"], 0),
            "practice": prac.get(r["id"], 0), "ai_ask": ask.get(r["id"], 0),
        })
    # 教师带训（n_s 与教师无关，算一次即可）
    n_s = d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()["c"]
    tcnt = {r["teacher_id"]: r["c"] for r in d.execute("SELECT teacher_id, COUNT(*) c FROM trainings GROUP BY teacher_id")}
    teachers = []
    for r in d.execute("SELECT id, name FROM users WHERE role='teacher' AND enabled=1 ORDER BY id"):
        teachers.append({"id": r["id"], "name": r["name"], "trainings": tcnt.get(r["id"], 0), "students": n_s})
    d.close()
    return {"trainings": trainings, "students": students, "teachers": teachers}