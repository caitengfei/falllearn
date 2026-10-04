# -*- coding: utf-8 -*-
"""组卷 + 判分（客观题规则判，秒判零误差）"""
import datetime
import json
import logging
import random
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import current_user

router = APIRouter(prefix="/api", tags=["quiz"])

CLUSTER_CN = db.CLUSTER_NAMES


def _pick_questions(d, student_id, count, weak_clusters, only_cluster=None):
    """薄弱簇优先 60% + 未测 20% + 随机 20%；7 天去重；难度按近期正确率自适应。
    only_cluster 指定时：题目全部取自该簇（簇专项练习）。"""
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

    if only_cluster:                      # 簇专项：全部取该簇；难度自适应 + 7 天去重，题量不足时放宽去重
        take(pool([only_cluster], diff, answered_7d), count)
        if len(picked) < count:
            take(pool([only_cluster], None, answered_7d), count - len(picked))
        if len(picked) < count:
            take(pool([only_cluster], None), count - len(picked))
        random.shuffle(picked)
        return picked[:count]

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
    kind: str = "daily"  # daily 综合练习(20题) | mock 12分钟模拟考(10题) | cluster 簇专项(20题)
    exam_id: int = 0  # >0：按教师布置卷开卷（忽略 kind）
    cluster: str = ""  # kind=cluster 时的知识点簇（morse/env/five/fracture/record/cpr）


def _exam_items_payload(d, exam_id):
    """组题返回（题目内容随开卷下发）。"""
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
    return items


@router.post("/quiz/start")
def start_practice(body: StartIn = StartIn(), u: dict = Depends(current_user)):
    """开卷：daily=10 题日常练习；mock=10 题 12 分钟限时理论模拟考（同题库、前端倒计时）；
    exam_id>0=教师布置卷（固定题目，截止/已完成校验，可断点续考）。"""
    d = db.get_db()
    now = int(time.time())
    if body.exam_id:
        ex = d.execute("SELECT * FROM exams WHERE id=? AND kind='teacher'", (body.exam_id,)).fetchone()
        if not ex:
            d.close()
            raise HTTPException(404, "布置不存在或已删除")
        cfg = json.loads(ex["config"] or "{}")
        if cfg.get("due_at") and now > cfg["due_at"]:
            d.close()
            raise HTTPException(400, "该布置已截止，无法开考")
        done = d.execute(
            "SELECT score FROM attempts WHERE student_id=? AND exam_id=? AND status='done' "
            "ORDER BY id DESC LIMIT 1", (u["id"], ex["id"])).fetchone()
        if done:
            d.close()
            raise HTTPException(400, f"已完成该布置（得分 {done['score']}），可在「教师布置」查看成绩")
        open_att = d.execute(
            "SELECT id FROM attempts WHERE student_id=? AND exam_id=? AND status='open'",
            (u["id"], ex["id"])).fetchone()
        if open_att:
            attempt_id = open_att["id"]  # 断点续考：沿用未交卷记录
        else:
            try:
                attempt_id = d.execute(
                    "INSERT INTO attempts(student_id,exam_id,started_at,status) VALUES(?,?,?,?)",
                    (u["id"], ex["id"], now, "open")).lastrowid
                db.add_points(d, u["id"], 0, "开卷", f"attempt:{attempt_id}")
                d.commit()
            except sqlite3.IntegrityError:
                # 并发开卷：唯一索引拦截第二张未交卷，改用已存在的那张（断点续考）
                d.rollback()
                open_att = d.execute(
                    "SELECT id FROM attempts WHERE student_id=? AND exam_id=? AND status='open'",
                    (u["id"], ex["id"])).fetchone()
                if not open_att:
                    d.close()
                    raise HTTPException(409, "开卷冲突，请重试")
                attempt_id = open_att["id"]
        items = _exam_items_payload(d, ex["id"])
        d.close()
        return {"attempt_id": attempt_id, "items": items, "count": len(items),
                "kind": "teacher", "time_limit": cfg.get("minutes", 0) * 60, "title": ex["title"]}
    kind = body.kind if body.kind in ("daily", "mock", "cluster") else "daily"
    rows = d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()
    lv = {r["cluster_id"]: r["level"] for r in rows}
    weak = [c for c in CLUSTER_CN if lv.get(c, 0) < 60] or list(CLUSTER_CN.keys())
    if kind == "cluster" and body.cluster in CLUSTER_CN:
        qids = _pick_questions(d, u["id"], 20, [body.cluster], only_cluster=body.cluster)
        title = f"专项练习·{CLUSTER_CN[body.cluster]}"
    elif kind == "mock":
        qids = _pick_questions(d, u["id"], 10, weak)
        title = "理论模拟考·跌倒风险与急救"
    else:
        qids = _pick_questions(d, u["id"], 20, weak)
        title = "综合练习 · 按薄弱点组卷"
    exam_id = d.execute(
        "INSERT INTO exams(title,kind,config,created_by,created_at) VALUES(?,?,?,?,?)",
        (title, kind, json.dumps({"weak": weak}), u["id"], now)).lastrowid
    n_q = max(1, len(qids))
    per_score = 10 if n_q <= 10 else max(1, 100 // n_q)   # 统一百分制（整数分）
    scores = [per_score] * len(qids)
    if scores:
        scores[-1] = max(1, 100 - per_score * (len(qids) - 1))   # 末题补差：满分恰为 100
    for i, qid in enumerate(qids):
        d.execute("INSERT INTO exam_items(exam_id,question_id,seq,score) VALUES(?,?,?,?)",
                  (exam_id, qid, i + 1, scores[i]))
    attempt_id = d.execute(
        "INSERT INTO attempts(student_id,exam_id,started_at,status) VALUES(?,?,?,?)",
        (u["id"], exam_id, now, "open")).lastrowid
    db.add_points(d, u["id"], 0, "开卷", f"attempt:{attempt_id}")
    d.commit()
    items = _exam_items_payload(d, exam_id)
    d.close()
    return {"attempt_id": attempt_id, "items": items, "count": len(items),
            "kind": kind, "title": title, "time_limit": 720 if kind == "mock" else 0}


@router.get("/quiz/assignments")
def my_assignments(u: dict = Depends(current_user)):
    """学生端「教师布置」列表（含本人完成状态：todo/open/done/overdue）。"""
    d = db.get_db()
    now = int(time.time())
    out = []
    for ex in d.execute("SELECT * FROM exams WHERE kind='teacher' ORDER BY created_at DESC, id DESC"):
        cfg = json.loads(ex["config"] or "{}")
        att = d.execute("SELECT id, score, status FROM attempts WHERE student_id=? AND exam_id=? "
                        "ORDER BY id DESC LIMIT 1", (u["id"], ex["id"])).fetchone()
        status, score, attempt_id = "todo", None, None
        if att:
            if att["status"] == "done":
                status, score, attempt_id = "done", att["score"], att["id"]
            elif att["status"] == "open":
                status, attempt_id = "open", att["id"]
        if status == "todo" and cfg.get("due_at") and now > cfg["due_at"]:
            status = "overdue"
        out.append({"exam_id": ex["id"], "title": ex["title"], "clusters": cfg.get("clusters", []),
                    "n": cfg.get("n", 0), "minutes": cfg.get("minutes", 0), "due_at": cfg.get("due_at", 0),
                    "status": status, "score": score, "attempt_id": attempt_id})
    d.close()
    return {"items": out}


@router.get("/quiz/result/{attempt_id}")
def my_result(attempt_id: int, u: dict = Depends(current_user)):
    """本人已交卷结果回顾（「教师布置·查看成绩」复用）。"""
    d = db.get_db()
    att = d.execute("SELECT * FROM attempts WHERE id=? AND student_id=? AND status='done'",
                    (attempt_id, u["id"])).fetchone()
    if not att:
        d.close()
        raise HTTPException(404, "该练习不存在或未交卷")
    res = _attempt_result_payload(d, att)
    d.close()
    return res


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


def _report_data(me_id: int) -> dict:
    """学习报告数据（/quiz/report 与 /quiz/report/ai 共用）。"""
    d = db.get_db()
    me = me_id
    now = int(time.time())
    # 1) 得分趋势（全部已交卷，按时间升序）
    rows = d.execute(
        "SELECT a.score, e.kind, a.submitted_at, e.title FROM attempts a LEFT JOIN exams e ON e.id=a.exam_id "
        "WHERE a.student_id=? AND a.status='done' ORDER BY a.submitted_at ASC", (me,)).fetchall()
    score_trend = [{"at": r["submitted_at"], "score": r["score"], "kind": r["kind"], "title": r["title"] or ""}
                   for r in rows]
    # 2) 近 14 天学习活跃（日历日分组，分钟）
    ev = d.execute("SELECT created_at, minutes FROM study_events WHERE student_id=? AND created_at>=?",
                   (me, now - 14 * 86400)).fetchall()
    today = datetime.date.fromtimestamp(now)
    acc = {}
    for r in ev:
        ds = datetime.date.fromtimestamp(r["created_at"]).isoformat()
        acc[ds] = acc.get(ds, 0) + (r["minutes"] or 0)
    activity = [{"day": (today - datetime.timedelta(days=i)).isoformat()[5:].replace("-", "/"),
                 "minutes": round(acc.get((today - datetime.timedelta(days=i)).isoformat(), 0), 1)}
                for i in range(13, -1, -1)]
    # 3) 错题按知识点分布 + 复习进度（active/mastered）
    wc = d.execute(
        "SELECT q.cluster_id, w.status, COUNT(*) c FROM wrong_records w JOIN questions q ON q.id=w.question_id "
        "WHERE w.student_id=? GROUP BY q.cluster_id, w.status", (me,)).fetchall()
    per = {}
    for r in wc:
        p = per.setdefault(r["cluster_id"], {"active": 0, "mastered": 0})
        p[r["status"]] = p.get(r["status"], 0) + r["c"]
    mlevel = {r["cluster_id"]: r["level"] for r in d.execute(
        "SELECT cluster_id, level FROM mastery WHERE student_id=?", (me,))}
    wrong_by_cluster = [{"cluster": cid,
                         "active": p.get("active", 0), "mastered": p.get("mastered", 0),
                         "total": p.get("active", 0) + p.get("mastered", 0),
                         "mastery": round(mlevel.get(cid) or 0)}
                        for cid, p in per.items()]
    wrong_by_cluster.sort(key=lambda x: -x["total"])
    # 4) 各知识点正确率（answers × attempts × questions）
    ar = d.execute(
        "SELECT q.cluster_id, COUNT(*) n, SUM(a.correct) ok FROM answers a "
        "JOIN attempts t ON t.id=a.attempt_id JOIN questions q ON q.id=a.question_id "
        "WHERE t.student_id=? GROUP BY q.cluster_id", (me,)).fetchall()
    correct_rate = [{"cluster": r["cluster_id"], "n": r["n"],
                     "rate": round(r["ok"] * 100 / r["n"], 1) if r["n"] else None} for r in ar]
    d.close()
    return {
        "score_trend": score_trend,
        "activity": activity,
        "total_hours_14d": round(sum(x["minutes"] for x in activity) / 60, 1),
        "wrong_by_cluster": wrong_by_cluster,
        "correct_rate": correct_rate,
        "practice_count": len(score_trend),
        "avg_score": round(sum(t["score"] for t in score_trend) / len(score_trend), 1) if score_trend else None,
        "wrong_active": sum(x["active"] for x in wrong_by_cluster),
        "wrong_mastered": sum(x["mastered"] for x in wrong_by_cluster),
    }


@router.get("/quiz/report")
def quiz_report(u: dict = Depends(current_user)):
    """学习报告：得分趋势 / 14 天活跃 / 错题知识点分布 / 正确率。"""
    return _report_data(u["id"])


@router.post("/quiz/report/ai")
async def quiz_report_ai(u: dict = Depends(current_user)):
    """AI 学习分析：报告数据 → 轻量 LLM 调用 → 诊断+建议（独立于四栏 persona）。"""
    from . import llm_direct
    cfg = llm_direct.get_cfg()
    if not cfg:
        raise HTTPException(400, "AI 直连通道未配置")
    rep = _report_data(u["id"])
    compact = {
        "学生": u.get("name", "同学"),
        "完成练习次数": rep["practice_count"],
        "平均分": rep["avg_score"],
        "得分趋势": [t["score"] for t in rep["score_trend"]][-10:],
        "近14天总学时": rep["total_hours_14d"],
        "错题分布": [{"知识点": CLUSTER_CN.get(x["cluster"], x["cluster"]),
                     "待巩固": x["active"], "已掌握": x["mastered"], "掌握度%": x["mastery"]}
                    for x in rep["wrong_by_cluster"]],
        "各知识点正确率": [{"知识点": CLUSTER_CN.get(x["cluster"], x["cluster"]),
                          "正确率%": x["rate"], "作答数": x["n"]} for x in rep["correct_rate"]],
    }
    sysp = ("你是康养智行的学业导师。根据学生近两周学习报告数据（JSON），用简体中文输出一段简洁的「AI 学习分析」，"
            "不超过 160 字：先一句总体表现（结合平均分与趋势走向），再点出最薄弱的 1-2 个知识点（结合正确率与错题分布），"
            "最后给一条具体可执行的建议。语气鼓励但诚实。不要 emoji、不要 markdown、不要分点编号。")
    try:
        text = await llm_direct.complete(
            cfg, [{"role": "system", "content": sysp},
                  {"role": "user", "content": json.dumps(compact, ensure_ascii=False)}],
            max_tokens=300, timeout=60)
    except Exception as e:
        logging.getLogger("falllearn").warning("ai_report_failed err=%s", str(e)[:300])  # 细节仅进服务端日志
        raise HTTPException(502, "AI 分析暂时不可用，请稍后重试")
    return {"analysis": text.strip()}


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
    # 输入收敛：作答键数与单值长度设上限（防超大 body / 脏数据入库）
    if len(body.answers) > 200 or any(not isinstance(v, str) or len(v) > 20 for v in body.answers.values()):
        raise HTTPException(400, "作答数据异常")
    d = db.get_db()
    att = d.execute("SELECT * FROM attempts WHERE id=? AND student_id=?",
                    (body.attempt_id, u["id"])).fetchone()
    if not att:
        d.close()
        raise HTTPException(404, "练习不存在")
    now = int(time.time())
    # 幂等闸门：以「open → done」条件更新抢占交卷权（并发重复提交只有一次能成功，防重复加分/重复作答行）
    claimed = d.execute(
        "UPDATE attempts SET status='done', submitted_at=?, score=-1 WHERE id=? AND student_id=? AND status='open'",
        (now, att["id"], u["id"]))
    if claimed.rowcount == 0:
        d.close()
        raise HTTPException(400, "该练习已交卷")
    d.commit()
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
    d.execute("UPDATE attempts SET score=? WHERE id=?", (total, att["id"]))
    # 学时：按开卷→交卷实际时长
    db.add_study(d, u["id"], "practice", (now - (att["started_at"] or now)) / 60, str(att["id"]))
    # 簇达标徽章 + 六簇全达标徽章
    db.grant_mastery_badges(d, u["id"])
    d.commit()
    att = d.execute("SELECT * FROM attempts WHERE id=?", (att["id"],)).fetchone()  # 取更新后的行（score 已落库，勿用开卷时的旧行）
    return _attempt_result_payload(d, att)


def _attempt_result_payload(d, att):
    """交卷结果 / 历史回顾共用：总分 + 各簇 + 逐题明细。"""
    total = att["score"]
    per_cluster = {}
    detail = []
    for r in d.execute(
            "SELECT a.correct, a.feedback, a.student_answer, q.id, q.stem, q.qtype, q.options, q.answer, q.source_doc, q.cluster_id "
            "FROM answers a JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=? ORDER BY q.id",
            (att["id"],)):
        pc = per_cluster.setdefault(r["cluster_id"], [0, 0])
        pc[0] += r["correct"]
        pc[1] += 1
        opts = json.loads(r["options"]) or []
        if r["qtype"] == "判断" or not opts:
            opts = ["对（A）", "错（B）"]
        detail.append(
            {"question_id": r["id"], "stem": r["stem"], "type": r["qtype"],
             "options": opts, "answer": r["answer"],
             "student_answer": r["student_answer"] or "",
             "correct": r["correct"], "feedback": r["feedback"], "source_doc": r["source_doc"],
             "cluster": r["cluster_id"]})
    minutes = 0
    ex = d.execute("SELECT config FROM exams WHERE id=?", (att["exam_id"],)).fetchone()
    if ex:
        try:
            minutes = int(json.loads(ex["config"] or "{}").get("minutes", 0) or 0)
        except (ValueError, TypeError):
            minutes = 0
    return {"score": total, "max": 100, "detail": detail, "minutes": minutes,
            "per_cluster": {k: {"correct": v[0], "total": v[1]} for k, v in per_cluster.items()}}
