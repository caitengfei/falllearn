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
        "SELECT w.id, w.first_wrong_at, w.review_count, w.last_review_at, w.due_at, w.status, "
        "q.id qid, q.stem, q.qtype, q.options, q.answer, q.cluster_id, q.source_doc, q.explanation "
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
            "explanation": r["explanation"] or "",
            "review_count": r["review_count"], "first_wrong_at": r["first_wrong_at"],
            "due_at": r["due_at"], "due": r["due_at"] <= now,
            "last_review_at": r["last_review_at"],
        })
    return {"items": items, "due_count": sum(1 for i in items if i["due"])}


class ReviewIn(BaseModel):
    question_id: int
    answer: str


REVIEW_DAILY_MINUTES = 30  # 复习学时每日封顶（防脚本刷学时刷分）


def _today_start(now: int) -> int:
    lt = time.localtime(now)
    return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))


@router.post("/review")
def review(body: ReviewIn, u: dict = Depends(current_user)):
    d = db.get_db()
    now = int(time.time())
    # 只认「待复习（active）」记录：已掌握不再接受重答——否则同一题可无限答对刷积分/刷学时
    w = d.execute("SELECT * FROM wrong_records WHERE student_id=? AND question_id=? AND status='active'",
                  (u["id"], body.question_id)).fetchone()
    if not w:
        d.close()
        raise HTTPException(404, "该题不在待复习列表（可能已掌握）")
    q = d.execute("SELECT * FROM questions WHERE id=?", (body.question_id,)).fetchone()
    opts = json.loads(q["options"])
    correct, fb = grade_objective(q["qtype"], opts, q["answer"], body.answer)
    # 到期判定：只有「已到期」的复习才计入掌握度/积分/学时；未到期只是提前练习，不给奖励
    due = bool(w["due_at"] and w["due_at"] <= now)
    if not due:
        d.close()
        return {"correct": correct, "feedback": fb, "status": "active", "due": False,
                "message": "尚未到期（提前练习不计分）；到期后重答才算有效复习",
                "correct_answer": q["answer"], "source_doc": q["source_doc"]}
    # 不再往 answers 表插行：复习历史不是考试作答，避免污染已交卷试卷与班级正确率统计
    db.update_mastery(d, u["id"], q["cluster_id"], 1.0 if correct else 0.0)
    # 间隔复习调度（与 UI 文案一致）：首错次日到期 → 答对后第 3 天 → 连对 2 次标记掌握；答错回到次日
    if correct:
        db.add_points(d, u["id"], 10, "错题复习答对", f"q:{q['id']}")
        # 间隔复习（按教师确认口径）：首错次日到期 → 答对后第 3 天 → 连对 2 次标记掌握；答错回到次日
        streak = w["correct_streak"] + 1
        if streak >= 2:
            d.execute("UPDATE wrong_records SET status='mastered', last_review_at=?, review_count=review_count+1, correct_streak=? WHERE id=?",
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
    # 学时：每次有效复习计 1 分钟，每日封顶（防无限刷）
    used = d.execute(
        "SELECT COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id=? AND type='review' AND created_at>=?",
        (u["id"], _today_start(now))).fetchone()["m"]
    if used < REVIEW_DAILY_MINUTES:
        db.add_study(d, u["id"], "review", 1, f"q:{q['id']}")
    d.commit()
    d.close()
    return {"correct": correct, "feedback": fb, "status": status, "due": True,
            "correct_answer": q["answer"], "source_doc": q["source_doc"]}