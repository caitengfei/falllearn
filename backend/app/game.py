# -*- coding: utf-8 -*-
"""游戏化：签到 / 积分 / 勋章 / 排行榜"""
import datetime as dt
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import db
from .auth import current_user

router = APIRouter(prefix="/api/game", tags=["game"])


def _today():
    return dt.date.today().isoformat()


@router.get("/today")
def today(u: dict = Depends(current_user)):
    d = db.get_db()
    done = d.execute("SELECT 1 FROM checkins WHERE student_id=? AND date=?",
                     (u["id"], _today())).fetchone()
    return {"checked_in": bool(done)}


class SignInIn(BaseModel):
    pass


@router.post("/checkin")
def checkin(u: dict = Depends(current_user)):
    d = db.get_db()
    date = _today()
    # INSERT OR IGNORE + rowcount 判断：并发重复签到只有一次生效（不会撞 UNIQUE 抛 500）
    cur = d.execute("INSERT OR IGNORE INTO checkins(student_id,date) VALUES(?,?)", (u["id"], date))
    if cur.rowcount == 0:
        d.close()
        return {"ok": False, "msg": "今日已签到"}
    db.add_points(d, u["id"], 5, "每日签到", date)
    d.commit()
    d.close()
    return {"ok": True, "points": 5}


@router.get("/points")
def points(u: dict = Depends(current_user)):
    d = db.get_db()
    total = d.execute("SELECT points FROM points_cache WHERE student_id=?", (u["id"],)).fetchone()
    log = d.execute("SELECT delta, reason, created_at FROM points_log WHERE student_id=? ORDER BY id DESC LIMIT 30",
                    (u["id"],)).fetchall()
    return {"total": total["points"] if total else 0,
            "log": [{"delta": r["delta"], "reason": r["reason"], "at": r["created_at"]} for r in log]}


BADGE_RULES = {
    "b_first_q": "完成首次 AI 问答",
    "b_streak10": "练习连续答对 10 题",
    "b_all60": "六簇掌握度全部 ≥ 60",
    "b_morse": "「Morse评估」掌握度 ≥ 60",
    "b_env": "「环境防控」掌握度 ≥ 60",
    "b_five": "「五步处置」掌握度 ≥ 60",
    "b_fracture": "「骨折识别」掌握度 ≥ 60",
    "b_record": "「记录上报」掌握度 ≥ 60",
    "b_cpr": "「CPR启动」掌握度 ≥ 60",
}


@router.get("/badges")
def badges(u: dict = Depends(current_user)):
    d = db.get_db()
    all_b = d.execute("SELECT * FROM badges ORDER BY id").fetchall()
    earned = {r["badge_id"]: r["earned_at"] for r in
              d.execute("SELECT * FROM user_badges WHERE student_id=?", (u["id"],)).fetchall()}
    lv = {r["cluster_id"]: r["level"] for r in
          d.execute("SELECT cluster_id, level FROM mastery WHERE student_id=?", (u["id"],)).fetchall()}
    out = []
    for b in all_b:
        item = {"id": b["id"], "name": b["name"], "icon": b["icon"],
                "earned": b["id"] in earned, "rule": BADGE_RULES.get(b["id"], "")}
        cid = b["id"][2:] if b["id"].startswith("b_") else ""
        if cid in lv and not item["earned"]:
            item["progress"] = min(100, int(lv[cid]))  # 簇徽章：当前掌握度进度
        out.append(item)
    d.close()
    return out


@router.get("/leaderboard")
def leaderboard(u: dict = Depends(current_user)):
    d = db.get_db()
    pts = d.execute(
        "SELECT u.id, u.name, u.student_no, COALESCE(p.points,0) points "
        "FROM users u LEFT JOIN points_cache p ON p.student_id=u.id "
        "WHERE u.role='student' ORDER BY points DESC, u.id LIMIT 50").fetchall()
    my_rank = next((i + 1 for i, r in enumerate(pts) if r["id"] == u["id"]), None)
    mast = d.execute(
        "SELECT u.id, u.name, COALESCE(SUM(m.level),0) total FROM users u LEFT JOIN mastery m ON m.student_id=u.id "
        "WHERE u.role='student' GROUP BY u.id, u.name ORDER BY total DESC, u.id LIMIT 50").fetchall()
    my_rank_m = next((i + 1 for i, r in enumerate(mast) if r["id"] == u["id"]), None)
    return {
        "points": [{"rank": i + 1, "name": r["name"], "points": r["points"], "me": r["id"] == u["id"]}
                   for i, r in enumerate(pts[:20])],
        "mastery": [{"rank": i + 1, "name": r["name"], "total": int(r["total"]), "me": r["id"] == u["id"]}
                    for i, r in enumerate(mast[:20])],
        "my_rank_points": my_rank, "my_rank_mastery": my_rank_m,
    }