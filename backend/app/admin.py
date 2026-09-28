# -*- coding: utf-8 -*-
"""教师看板：学生列表 / 班级弱项 / 演示账号重置"""
import bcrypt
import time

from fastapi import APIRouter, Depends

from . import db
from .auth import require_teacher

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(u: dict = Depends(require_teacher)):
    d = db.get_db()
    students = []
    for r in d.execute("SELECT id, student_no, name FROM users WHERE role='student' ORDER BY id"):
        lv = {m["cluster_id"]: m["level"] for m in d.execute(
            "SELECT cluster_id, level FROM mastery WHERE student_id=?", (r["id"],)).fetchall()}
        pts = d.execute("SELECT points FROM points_cache WHERE student_id=?", (r["id"],)).fetchone()
        last = d.execute(
            "SELECT a.score, a.submitted_at FROM attempts a WHERE a.student_id=? AND a.status='done' "
            "ORDER BY a.id DESC LIMIT 1", (r["id"],)).fetchone()
        n_wrong = d.execute("SELECT COUNT(*) c FROM wrong_records WHERE student_id=? AND status='active'",
                            (r["id"],)).fetchone()["c"]
        students.append({
            "id": r["id"], "student_no": r["student_no"], "name": r["name"],
            "mastery": lv, "points": pts["points"] if pts else 0,
            "last_score": last["score"] if last else None,
            "last_at": last["submitted_at"] if last else None,
            "active_wrong": n_wrong,
        })
    # 班级弱项：各簇错误率（来自 rules 判分的 answers）
    weak = []
    for cid, cname in db.CLUSTER_NAMES.items():
        row = d.execute(
            "SELECT COUNT(*) n, SUM(1-a.correct) wrong FROM answers a JOIN questions q ON q.id=a.question_id "
            "WHERE q.cluster_id=? AND a.graded_by LIKE 'rules%'", (cid,)).fetchone()
        if row["n"]:
            weak.append({"cluster": cid, "name": cname, "n": row["n"], "wrong": row["wrong"] or 0,
                         "rate": round((row["wrong"] or 0) * 100 / row["n"], 1)})
    weak.sort(key=lambda x: -x["rate"])
    return {"students": students, "weak_clusters": weak}


DEMO_STUDENTS = ("S2026001", "S2026002", "S2026003")


@router.post("/reset-demo")
def reset_demo(u: dict = Depends(require_teacher)):
    """重置演示账号（仅 S2026001-3 + T2026 密码）+ 清空这 3 人的学习痕迹（大赛演示用）。

    范围严格限定：不碰其他学生/教师的数据，考卷只删演示学生创建的。
    """
    d = db.get_db()
    for sno in (*DEMO_STUDENTS, "T2026"):
        h = bcrypt.hashpw(b"123456", bcrypt.gensalt(4)).decode()
        d.execute("UPDATE users SET pwd_hash=? WHERE student_no=?", (h, sno))
    ph = ",".join("?" * len(DEMO_STUDENTS))
    SIDS = f"SELECT id FROM users WHERE student_no IN ({ph})"
    # answers 无 student_id 列，先经 attempts 级联删
    d.execute(f"DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id IN ({SIDS}))",
              DEMO_STUDENTS)
    d.execute(f"DELETE FROM ai_grades WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id IN ({SIDS}))",
              DEMO_STUDENTS)
    for t in ("mastery", "wrong_records", "chat_logs", "points_log", "checkins",
              "user_badges", "student_sessions", "attempts", "points_cache", "study_events"):
        d.execute(f"DELETE FROM {t} WHERE student_id IN ({SIDS})", DEMO_STUDENTS)
    d.execute(f"DELETE FROM training_enrolls WHERE student_id IN ({SIDS})", DEMO_STUDENTS)
    # 考卷只删演示学生创建的（教师/其他学生的卷不受影响）
    d.execute(f"DELETE FROM exam_items WHERE exam_id IN (SELECT id FROM exams WHERE created_by IN ({SIDS}))",
              DEMO_STUDENTS)
    d.execute(f"DELETE FROM exams WHERE created_by IN ({SIDS})", DEMO_STUDENTS)
    # 重新预置 S2026001 演示基线（掌握度/积分/错题/对话）
    db.seed_demo_data(d)
    d.commit()
    d.close()
    return {"ok": True}