# -*- coding: utf-8 -*-
"""错题本：入本 / 重答 / 间隔复习（第 1/3/7 天）/ 连对 2 次掌握"""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import current_user
from .quiz import grade_objective
import json

router = APIRouter(prefix="/api/wrong", tags=["wrong"])


@router.get("")
def list_wrong(status: str = "active", u: dict = Depends(current_user)):
    d = db.get_db()
    now = int(time.time())
    rows = d.execute(
        "SELECT w.id, w.first_wrong_at, w.review_count, w.last_review_at, w.due_at, w.status, q.id qid, q.stem, q.qtype, q.options, q.answer, q.cluster_id, q.source_doc "
        "FROM wrong_records w JOIN questions q ON q.id=w.question_id "
        "WHERE w.student_id=? AND w.status=? ORDER BY (w.due_at<=?) DESC, w.due_at",
        (u["id"], status, now)).fetchall()
    items = []
    for r in rows:
        opts = json.loads(r["options"])
        items.append({
            "id": r["qid"], "stem": r["stem"], "type": r["qtype"],
            "options": opts if r["qtype"] != "判断" else ["对（A）", "错（B）"],
            "answer": r["answer"], "cluster": r["cluster_id"], "source_doc": r["source_doc"],
            "review_count": r["review_count"], "first_wrong_at": r["first_wrong_at"],
            "due_at": r["due_at"], "due": r["due_at"] <= now,
            "last_review_at": r["last_review_at"],
        })
    return {"items": items, "due_count": sum(1 for i in items if i["due"])}


class ReviewIn(BaseModel):
    question_id: int
    answer: str


@router.post("/review")
def review(body: ReviewIn, u: dict = Depends(current_user)):
    d = db.get_db()
    now = int(time.time())
    w = d.execute("SELECT * FROM wrong_records WHERE student_id=? AND question_id=?",
                  (u["id"], body.question_id)).fetchone()
    if not w:
        raise HTTPException(404, "不在错题本")
    q = d.execute("SELECT * FROM questions WHERE id=?", (body.question_id,)).fetchone()
    opts = json.loads(q["options"])
    correct, fb = grade_objective(q["qtype"], opts, q["answer"], body.answer)
    # 也记一条 answers（计入 mastery 与连对）
    att = d.execute(
        "SELECT id FROM attempts WHERE student_id=? ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    if att:
        d.execute(
            "INSERT INTO answers(attempt_id,question_id,student_answer,correct,score,feedback,graded_by,answered_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (att["id"], q["id"], body.answer, correct, 10 if correct else 0, fb, "rules-review", now))
    db.update_mastery(d, u["id"], q["cluster_id"], 1.0 if correct else 0.0)
    # 间隔复习调度（与 UI 文案一致）：首错次日到期 → 答对后第 3 天 → 连对 2 次标记掌握；答错回到次日
    if correct:
        db.add_points(d, u["id"], 10, "错题复习答对", f"q:{q['id']}")
        streak = w["correct_streak"] + 1
        if streak >= 2:
            d.execute("UPDATE wrong_records SET status='mastered', last_review_at=?, correct_streak=? WHERE id=?",
                      (now, streak, w["id"]))
            status = "mastered"
        else:
            d.execute("UPDATE wrong_records SET review_count=review_count+1, last_review_at=?, due_at=?, correct_streak=?, status='active' WHERE id=?",
                      (now, now + 2 * 86400, streak, w["id"]))
            status = "active"
    else:
        d.execute("UPDATE wrong_records SET review_count=review_count+1, last_review_at=?, due_at=?, correct_streak=0, status='active' WHERE id=?",
                  (now, now + 86400, w["id"]))
        status = "active"
    # 学时：每次复习计 1 分钟
    db.add_study(d, u["id"], "review", 1, f"q:{q['id']}")
    d.commit()
    return {"correct": correct, "feedback": fb, "status": status,
            "correct_answer": q["answer"], "source_doc": q["source_doc"]}