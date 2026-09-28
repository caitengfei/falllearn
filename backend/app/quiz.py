# -*- coding: utf-8 -*-
"""组卷 + 判分（客观题规则判，秒判零误差）"""
import json
import random
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import current_user

router = APIRouter(prefix="/api", tags=["quiz"])

CLUSTER_CN = db.CLUSTER_NAMES


def _pick_questions(d, student_id, count, weak_clusters):
    """薄弱簇优先 60% + 未测 20% + 随机 20%；7 天去重；难度按近期正确率自适应。"""
    answered_7d = {r[0] for r in d.execute(
        "SELECT a.question_id FROM answers a JOIN attempts t ON t.id=a.attempt_id "
        "WHERE t.student_id=? AND a.answered_at > ?", (student_id, int(time.time()) - 7 * 86400))}
    tested = {r[0] for r in d.execute(
        "SELECT DISTINCT a.question_id FROM answers a JOIN attempts t ON t.id=a.attempt_id "
        "WHERE t.student_id=?", (student_id,))}

    def pool(cluster_ids=None, diff=None, exclude=None):
        sql = "SELECT id FROM questions WHERE 1=1"
        args = []
        if cluster_ids:
            sql += f" AND cluster_id IN ({','.join('?' * len(cluster_ids))})"
            args += list(cluster_ids)
        if diff is not None:
            sql += " AND difficulty=?"
            args.append(diff)
        if exclude:
            ids = list(exclude)
            sql += f" AND id NOT IN ({','.join('?' * len(ids))})"
            args += ids
        sql += " ORDER BY RANDOM() LIMIT ?"
        args.append(count)
        return [r[0] for r in d.execute(sql, args)]

    all_clusters = list(CLUSTER_CN.keys())  # 仅 6 个知识簇；general（护理通识）不入薄弱/未测池
    untested = [c for c in all_clusters if c not in tested] or list(all_clusters)
    # 难度自适应：近期 5 题正确率
    recent = d.execute(
        "SELECT a.correct FROM answers a JOIN attempts t ON t.id=a.attempt_id "
        "WHERE t.student_id=? ORDER BY a.answered_at DESC LIMIT 5", (student_id,)).fetchall()
    rate = (sum(r["correct"] for r in recent) / len(recent)) if recent else 0.5
    diff = 1
    if rate >= 0.8:
        diff = 2

    picked, used = [], set()

    def take(pool_ids, n):
        got = 0
        for qid in pool_ids:
            if qid in used:
                continue
            used.add(qid)
            picked.append(qid)
            got += 1
            if got >= n:
                break
        return got

    n_weak = max(1, int(count * 0.6))
    n_untested = max(1, int(count * 0.2))
    n_rand = count - n_weak - n_untested
    take(pool(weak_clusters, diff, answered_7d), n_weak)
    if len(picked) < n_weak:
        take(pool(weak_clusters, None, answered_7d), n_weak - len(picked))
    take(pool(untested, None, answered_7d), n_untested)
    take(pool(all_clusters, None, answered_7d), n_rand)  # 随机池只用 6 簇，避免 general 稀释
    # 兜底：6 簇凑不齐才从全库（含 general）随机补
    if len(picked) < count:
        take(pool(None, None, answered_7d), count - len(picked))
    random.shuffle(picked)
    return picked[:count]


@router.get("/quiz/weak")
def weak_info(u: dict = Depends(current_user)):
    d = db.get_db()
    rows = d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()
    lv = {r["cluster_id"]: r["level"] for r in rows}
    weak = [c for c in CLUSTER_CN if lv.get(c, 0) < 60]
    return {"weak": weak, "mastery": lv}


class StartIn(BaseModel):
    kind: str = "daily"  # daily 日常练习 | mock 12 分钟限时理论模拟考


@router.post("/quiz/start")
def start_practice(body: StartIn = StartIn(), u: dict = Depends(current_user)):
    """开卷：daily=10 题日常练习；mock=10 题 12 分钟限时理论模拟考（同题库、前端倒计时）。"""
    kind = body.kind if body.kind in ("daily", "mock") else "daily"
    d = db.get_db()
    rows = d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()
    lv = {r["cluster_id"]: r["level"] for r in rows}
    weak = [c for c in CLUSTER_CN if lv.get(c, 0) < 60] or list(CLUSTER_CN.keys())
    qids = _pick_questions(d, u["id"], 10, weak)
    now = int(time.time())
    title = "理论模拟考·跌倒风险与急救" if kind == "mock" else f"日常练习·{now % 100000}"
    exam_id = d.execute(
        "INSERT INTO exams(title,kind,config,created_by,created_at) VALUES(?,?,?,?,?)",
        (title, kind, json.dumps({"weak": weak}), u["id"], now)).lastrowid
    for i, qid in enumerate(qids):
        d.execute("INSERT INTO exam_items(exam_id,question_id,seq,score) VALUES(?,?,?,?)",
                  (exam_id, qid, i + 1, 10))
    attempt_id = d.execute(
        "INSERT INTO attempts(student_id,exam_id,started_at,status) VALUES(?,?,?,?)",
        (u["id"], exam_id, now, "open")).lastrowid
    db.add_points(d, u["id"], 0, "开卷", f"attempt:{attempt_id}")
    d.commit()
    # 组题返回（题目内容随开卷下发）
    items = []
    for row in d.execute(
            "SELECT e.seq, q.id, q.qtype, q.stem, q.options, q.cluster_id, q.difficulty "
            "FROM exam_items e JOIN questions q ON q.id=e.question_id "
            "WHERE e.exam_id=? ORDER BY e.seq", (exam_id,)):
        opts = json.loads(row["options"]) or []
        if row["qtype"] == "判断" or not opts:
            opts = ["对（A）", "错（B）"]  # 题库判断题 options 为空数组
        items.append({
            "seq": row["seq"], "question_id": row["id"], "type": row["qtype"],
            "stem": row["stem"], "options": opts,
            "cluster": row["cluster_id"],
        })
    return {"attempt_id": attempt_id, "items": items, "count": len(items),
            "kind": kind, "time_limit": 720 if kind == "mock" else 0}


@router.get("/quiz/summary")
def quiz_summary(u: dict = Depends(current_user)):
    """练习概览：完成组数 / 最近得分 / 平均分 / 待复习错题数。"""
    d = db.get_db()
    done = d.execute("SELECT COUNT(*) c FROM attempts WHERE student_id=? AND status='done'",
                     (u["id"],)).fetchone()["c"]
    last = d.execute("SELECT score FROM attempts WHERE student_id=? AND status='done' "
                     "ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    avg = d.execute("SELECT AVG(score) a FROM attempts WHERE student_id=? AND status='done'",
                    (u["id"],)).fetchone()["a"]
    wrong_due = d.execute(
        "SELECT COUNT(*) c FROM wrong_records WHERE student_id=? AND status='active' AND due_at<=?",
        (u["id"], int(time.time()))).fetchone()["c"]
    wrong_active = d.execute("SELECT COUNT(*) c FROM wrong_records WHERE student_id=? AND status='active'",
                             (u["id"],)).fetchone()["c"]
    d.close()
    return {"practice_count": done, "last_score": last["score"] if last else None,
            "avg_score": round(avg, 1) if avg else None,
            "wrong_active": wrong_active, "wrong_due": wrong_due}


class SubmitIn(BaseModel):
    attempt_id: int
    answers: dict  # question_id(str) -> 选中字母 str（如 "A" / "ABCD"）


def grade_objective(qtype, options, answer_key, student_ans):
    """返回 (correct 0/1, feedback)"""
    sa = "".join(sorted(student_ans.strip().upper())) if qtype == "多选" else student_ans.strip().upper()
    ak = answer_key.upper()
    if qtype == "多选":
        ok = sa == ak
        fb = "" if ok else f"应选 {''.join(sorted(ak))}，漏选/多选均不得分"
    elif qtype == "判断":
        ok = sa == ak
        fb = "" if ok else f"应为 {'对（A）' if ak == 'A' else '错（B）'}"
    else:
        ok = sa == ak
        opt_letter = ak
        opt_text = options[ord(opt_letter) - ord("A")] if opt_letter in "ABCD" and options else ""
        fb = "" if ok else f"正确答案 {opt_letter}：{opt_text[:60]}"
    return int(ok), fb


@router.post("/quiz/submit")
def submit(body: SubmitIn, u: dict = Depends(current_user)):
    d = db.get_db()
    att = d.execute("SELECT * FROM attempts WHERE id=? AND student_id=?",
                    (body.attempt_id, u["id"])).fetchone()
    if not att:
        raise HTTPException(404, "练习不存在")
    if att["status"] != "open":
        raise HTTPException(400, "该练习已交卷")
    now = int(time.time())
    total = 0
    per_cluster = {}
    for row in d.execute(
            "SELECT e.seq, e.score, q.id, q.qtype, q.options, q.answer, q.cluster_id, q.source_doc "
            "FROM exam_items e JOIN questions q ON q.id=e.question_id WHERE e.exam_id=?",
            (att["exam_id"],)):
        sa = body.answers.get(str(row["id"]), "")
        correct, fb = grade_objective(row["qtype"], json.loads(row["options"]), row["answer"], sa)
        sc = row["score"] if correct else 0
        total += sc
        per_cluster[row["cluster_id"]] = per_cluster.get(row["cluster_id"], [0, 0])
        per_cluster[row["cluster_id"]][0] += correct
        per_cluster[row["cluster_id"]][1] += 1
        d.execute(
            "INSERT INTO answers(attempt_id,question_id,student_answer,correct,score,feedback,graded_by,answered_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (att["id"], row["id"], sa, correct, sc, fb, "rules", now))
        if not correct and row["cluster_id"] != "general":
            db.update_mastery(d, u["id"], row["cluster_id"], 0.0)
            db.add_points(d, u["id"], 0, "练习答错", f"q:{row['id']}")
            # 入错题本（再错同题：回到次日到期，连对计数清零）
            d.execute(
                "INSERT INTO wrong_records(student_id,question_id,first_wrong_at,review_count,correct_streak,last_review_at,due_at,status) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(student_id,question_id) DO UPDATE SET due_at=excluded.due_at, correct_streak=0, status='active'",
                (u["id"], row["id"], now, 0, 0, now, now + 86400, "active"))
        if correct:
            db.update_mastery(d, u["id"], row["cluster_id"], 1.0)
            db.add_points(d, u["id"], 5, "练习答对", f"q:{row['id']}")
            # 连对徽章
            streak = d.execute(
                "SELECT COALESCE(SUM(correct),0) c FROM (SELECT a.correct FROM answers a JOIN attempts t ON t.id=a.attempt_id "
                "WHERE t.student_id=? AND a.graded_by='rules' ORDER BY a.answered_at DESC, a.id DESC LIMIT 10)",
                (u["id"],)).fetchone()["c"]
            if streak >= 10 and d.execute(
                    "SELECT COUNT(*) FROM user_badges WHERE student_id=? AND badge_id='b_streak10'",
                    (u["id"],)).fetchone()[0] == 0:
                db.ensure_badge(d, u["id"], "b_streak10")
    d.execute("UPDATE attempts SET submitted_at=?, score=?, status='done' WHERE id=?", (now, total, att["id"]))
    # 学时：按开卷→交卷实际时长
    db.add_study(d, u["id"], "practice", (now - (att["started_at"] or now)) / 60, str(att["id"]))
    # 簇达标徽章 + 六簇全达标徽章
    db.grant_mastery_badges(d, u["id"])
    d.commit()
    # 结果详情
    detail = []
    for r in d.execute(
            "SELECT a.correct, a.feedback, a.student_answer, q.id, q.stem, q.qtype, q.options, q.answer, q.source_doc, q.cluster_id "
            "FROM answers a JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=? ORDER BY q.id",
            (att["id"],)):
        opts = json.loads(r["options"]) or []
        if r["qtype"] == "判断" or not opts:
            opts = ["对（A）", "错（B）"]
        detail.append(
            {"question_id": r["id"], "stem": r["stem"], "type": r["qtype"],
             "options": opts, "answer": r["answer"],
         "student_answer": body.answers.get(str(r["id"]), ""),
         "correct": r["correct"], "feedback": r["feedback"], "source_doc": r["source_doc"],
         "cluster": r["cluster_id"]})
    return {"score": total, "max": 100, "detail": detail,
            "per_cluster": {k: {"correct": v[0], "total": v[1]} for k, v in per_cluster.items()}}