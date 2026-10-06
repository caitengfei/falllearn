# -*- coding: utf-8 -*-
"""管理后台 · 业务管理端点（B 期）：
轮播 / 课程预告 / 考试管理 / 学生 / 账号 / 培训 / 统计。教师端全部走 require_teacher。
学生端只读消费走 /api/content/*（轮播/预告）。
"""
import csv
import io
import json
import os
import re
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


def _safe_link(v: str) -> str:
    """链接白名单：站内路径（/…）或 http(s)（阻断 javascript:/data: 等 scheme 注入）。"""
    v = (v or "").strip()
    if v and not (v.startswith("/") or v.startswith("http://") or v.startswith("https://")):
        raise HTTPException(400, "链接仅支持站内路径（/…）或 http(s) 地址")
    return v or "/"


def _safe_image(v: str) -> str:
    """轮播图地址白名单：/uploads/ 或 http(s)（阻断 data:/javascript:/CSS url() 注入）。"""
    v = (v or "").strip()
    if v and not (v.startswith("/uploads/") or v.startswith("http://") or v.startswith("https://")):
        raise HTTPException(400, "图片地址仅支持本平台上传（/uploads/…）或 http(s) 地址")
    return v


def _clean_pwd(v: str, *, strict: bool = True) -> str:
    """口令校验：新建/重置时长度 6–128（空串在 strict=False 表示“不改密码”）。"""
    v = (v or "").strip()
    if not strict and not v:
        return ""
    if not (6 <= len(v) <= 128):
        raise HTTPException(400, "密码长度需 6–128 位")
    return v


def _teacher_owned_only(d, uid: int, me: int, what: str = "账号"):
    """横向越权防护：教师只能管理学生账号 / 自己创建的培训；不能操作其他教师。
    失败时关闭连接再抛出（避免异常路径遗留 sqlite 连接）。"""
    row = d.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        d.close()
        raise HTTPException(404, f"{what}不存在")
    if row["role"] == "teacher" and uid != me:
        d.close()
        raise HTTPException(403, "不能操作其他教师账号")
    return row


@router.post("/banners")
def banners_create(b: BannerIn, u: dict = Depends(require_teacher)):
    title = _check_title(b.title)
    d = db.get_db()
    cur = d.execute(
        "INSERT INTO banners(title,tag,sub,image,link,sort,enabled,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (title, b.tag.strip(), b.sub.strip(), _safe_image(b.image), _safe_link(b.link), b.sort, b.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid}


@router.put("/banners/{bid}")
def banners_update(bid: int, b: BannerIn, u: dict = Depends(require_teacher)):
    title = _check_title(b.title)
    d = db.get_db()
    cur = d.execute(
        "UPDATE banners SET title=?,tag=?,sub=?,image=?,link=?,sort=?,enabled=? WHERE id=?",
        (title, b.tag.strip(), b.sub.strip(), _safe_image(b.image), _safe_link(b.link), b.sort, b.enabled, bid))
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
    # 分块读 + 累计判长：不在内存里接住超大文件（上限 4MB）
    chunks, size = [], 0
    while True:
        chunk = await file.read(256 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > 4 * 1024 * 1024:
            raise HTTPException(400, "图片超过 4MB 上限")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not file.filename or "." not in file.filename:
        raise HTTPException(400, "无法识别的文件名，请上传 png/jpg/webp/gif 图片")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        raise HTTPException(400, f"不支持的文件类型 .{ext}（仅 png/jpg/jpeg/webp/gif）")
    # 内容魔数校验（防伪装扩展名上传非图片内容）
    head = data[:12]
    if ext == "png" and not head.startswith(b"\x89PNG"):
        raise HTTPException(400, "文件内容与扩展名不符（非有效 PNG）")
    if ext in ("jpg", "jpeg") and not head.startswith(b"\xff\xd8"):
        raise HTTPException(400, "文件内容与扩展名不符（非有效 JPEG）")
    if ext == "webp" and not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
        raise HTTPException(400, "文件内容与扩展名不符（非有效 WebP）")
    if ext == "gif" and not (head.startswith(b"GIF87a") or head.startswith(b"GIF89a")):
        raise HTTPException(400, "文件内容与扩展名不符（非有效 GIF）")
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


# ================= 教师布置（闭环：教师建卷 → 学生开考/交卷 → 教师看完成与得分） =================
class AssignIn(BaseModel):
    title: str = ""
    clusters: list = []
    n: int = 10
    minutes: int = 10
    due_days: int = 7


def _pick_for_assignment(d, clusters, n):
    """布置选题：所选知识簇内随机；不足时从全库兜底补齐。"""
    cids = [c for c in clusters if c in db.CLUSTER_NAMES] or list(db.CLUSTER_NAMES.keys())
    ph = ",".join("?" * len(cids))
    ids = [r[0] for r in d.execute(
        f"SELECT id FROM questions WHERE cluster_id IN ({ph}) ORDER BY RANDOM() LIMIT ?",  # nosec B608（人工确认：仅 ? 占位符拼接）
        cids + [n])]
    if len(ids) < n:
        if ids:
            ph2 = ",".join("?" * len(ids))
            extra = [r[0] for r in d.execute(
                f"SELECT id FROM questions WHERE id NOT IN ({ph2}) ORDER BY RANDOM() LIMIT ?",  # nosec B608（人工确认：仅 ? 占位符拼接）
                ids + [n - len(ids)])]
        else:
            extra = [r[0] for r in d.execute("SELECT id FROM questions ORDER BY RANDOM() LIMIT ?", [n])]
        ids += extra
    return ids[:n]


@router.post("/assignments")
def assignments_create(b: AssignIn, u: dict = Depends(require_teacher)):
    """教师布置练习：选知识簇 + 题量 + 时限 + 截止时间；全体学生在「练习考试·教师布置」可见。"""
    n = max(5, min(20, int(b.n or 10)))
    minutes = max(0, min(120, int(b.minutes or 0)))
    due_days = max(1, min(90, int(b.due_days or 7)))
    clusters = [c for c in (b.clusters or []) if c in db.CLUSTER_NAMES]
    d = db.get_db()
    qids = _pick_for_assignment(d, clusters, n)
    if len(qids) < 5:
        d.close()
        raise HTTPException(400, "题库不足，无法组卷")
    now = int(time.time())
    title = (b.title or "").strip()
    if not title:
        name = "·".join(db.CLUSTER_NAMES[c] for c in clusters[:2]) if clusters else "综合练习"
        title = f"教师布置·{name}（{len(qids)} 题）"
    cfg = {"clusters": clusters, "n": len(qids), "minutes": minutes, "due_at": now + due_days * 86400}
    exam_id = d.execute(
        "INSERT INTO exams(title,kind,config,created_by,created_at) VALUES(?,?,?,?,?)",
        (title, "teacher", json.dumps(cfg, ensure_ascii=False), u["id"], now)).lastrowid
    for i, qid in enumerate(qids):
        d.execute("INSERT INTO exam_items(exam_id,question_id,seq,score) VALUES(?,?,?,?)",
                  (exam_id, qid, i + 1, 10))
    d.commit()
    d.close()
    return {"ok": True, "exam_id": exam_id, "title": title, "n": len(qids),
            "minutes": minutes, "due_at": cfg["due_at"]}


@router.get("/assignments")
def assignments_list(u: dict = Depends(require_teacher)):
    """布置列表（完成统计 + 成绩统计：平均分/满分人数/得分分布/各簇正确率/自动定位最弱簇，总体与分班双口径）。"""
    d = db.get_db()
    total_students = d.execute("SELECT COUNT(*) c FROM users WHERE role='student' AND enabled=1").fetchone()["c"]
    out = []
    for ex in d.execute("SELECT * FROM exams WHERE kind='teacher' ORDER BY created_at DESC, id DESC"):
        cfg = json.loads(ex["config"] or "{}")
        done_rows = d.execute(
            "SELECT a.score, u.class_name FROM attempts a JOIN users u ON u.id=a.student_id "
            "WHERE a.exam_id=? AND a.status='done'", (ex["id"],)).fetchall()
        scores = [r["score"] for r in done_rows if r["score"] is not None]
        max_score = d.execute(
            "SELECT COALESCE(SUM(score),0) m FROM exam_items WHERE exam_id=?", (ex["id"],)).fetchone()["m"] or 1
        dist = {}
        for s in scores:
            dist[s] = dist.get(s, 0) + 1

        # 各簇正确率：总体 + 分班（各一条 GROUP BY）
        cl_all, cl_by_cls = {}, {}
        for r in d.execute(
                "SELECT q.cluster_id cid, COUNT(*) n, SUM(a.correct) ok FROM answers a "
                "JOIN attempts t ON t.id=a.attempt_id JOIN questions q ON q.id=a.question_id "
                "WHERE t.exam_id=? AND t.status='done' GROUP BY q.cluster_id", (ex["id"],)):
            cl_all[r["cid"]] = (r["n"], r["ok"] or 0)
        for r in d.execute(
                "SELECT u.class_name cls, q.cluster_id cid, COUNT(*) n, SUM(a.correct) ok FROM answers a "
                "JOIN attempts t ON t.id=a.attempt_id JOIN users u ON u.id=t.student_id "
                "JOIN questions q ON q.id=a.question_id "
                "WHERE t.exam_id=? AND t.status='done' GROUP BY u.class_name, q.cluster_id", (ex["id"],)):
            cl_by_cls.setdefault(r["cls"] or "", {})[r["cid"]] = (r["n"], r["ok"] or 0)

        def _clusters_stat(cm):
            rows = [{"cluster": cid, "name": db.CLUSTER_NAMES.get(cid, cid), "n": n, "ok": ok,
                     "rate": round(ok * 100 / n, 1)} for cid, (n, ok) in cm.items() if n]
            rows.sort(key=lambda x: x["rate"])
            return rows

        def _weakest(rows):
            return ({"cluster": rows[0]["cluster"], "name": rows[0]["name"],
                     "rate": rows[0]["rate"], "n": rows[0]["n"]} if rows else None)

        all_c = _clusters_stat(cl_all)
        item = {
            "exam_id": ex["id"], "title": ex["title"], "clusters": cfg.get("clusters", []),
            "n": cfg.get("n", 0), "minutes": cfg.get("minutes", 0), "due_at": cfg.get("due_at", 0),
            "created_at": ex["created_at"],
            "done": len(done_rows), "total_students": total_students,
            "rate": round(len(done_rows) * 100 / total_students) if total_students else 0,
            "max_score": max_score,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "full_count": sum(1 for s in scores if s == max_score),
            "score_dist": {str(k): v for k, v in sorted(dist.items(), reverse=True)},
            "clusters_stat": all_c,
            "weakest": _weakest(all_c),
            "per_class": [],
        }
        # 分班口径（未分班单独成组，排最后）
        cls_groups = {}
        for r in done_rows:
            cls_groups.setdefault(r["class_name"] or "", []).append(r["score"])
        for cname, cs in sorted(cls_groups.items(), key=lambda kv: (kv[0] == "", kv[0])):
            crow = _clusters_stat(cl_by_cls.get(cname, {}))
            item["per_class"].append({
                "class": cname or "未分班",
                "done": len(cs),
                "avg_score": round(sum(cs) / len(cs), 1) if cs else None,
                "full_count": sum(1 for s in cs if s == max_score),
                "weakest": _weakest(crow),
            })
        out.append(item)
    d.close()
    return {"items": out}


@router.delete("/assignments/{exam_id}")
def assignments_delete(exam_id: int, u: dict = Depends(require_teacher)):
    """删除布置（级联删题目、作答记录与 AI 判卷）。"""
    d = db.get_db()
    ex = d.execute("SELECT id FROM exams WHERE id=? AND kind='teacher'", (exam_id,)).fetchone()
    if not ex:
        d.close()
        raise HTTPException(404, "布置不存在或不是教师布置类型")
    d.execute("DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id=?)", (exam_id,))
    d.execute("DELETE FROM ai_grades WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id=?)", (exam_id,))
    d.execute("DELETE FROM attempts WHERE exam_id=?", (exam_id,))
    d.execute("DELETE FROM exam_items WHERE exam_id=?", (exam_id,))
    d.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    d.commit()
    d.close()
    return {"ok": True}


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
def students_list(u: dict = Depends(require_teacher), cls: str = ""):
    """学生列表：8 个聚合各一条批量 GROUP BY（原逐人 8 查询 → N×8 全表扫描）。

    cls 过滤：不传=全部；'__none__'=未分班（class_name 为空）；其他值=精确匹配班级名。"""
    d = db.get_db()
    wcls = ""
    params: list = []
    if cls == "__none__":
        wcls = " AND (class_name='' OR class_name IS NULL)"
    elif cls:
        wcls = " AND class_name=?"
        params.append(cls)
    rows = d.execute(
        "SELECT id, student_no, name, role, enabled, created_at, class_name FROM users "
        "WHERE role='student'" + wcls + " ORDER BY id", params).fetchall()
    ids = [r["id"] for r in rows]
    stats = {i: {"points": 0, "mastery": {}, "practice_count": 0, "ai_ask": 0,
                 "wrong_active": 0, "badge_count": 0, "enroll_count": 0, "hours": 0.0} for i in ids}
    if ids:
        ph = ",".join("?" * len(ids))
        for m in d.execute(f"SELECT student_id, cluster_id, level FROM mastery WHERE student_id IN ({ph})", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[m["student_id"]]["mastery"][m["cluster_id"]] = m["level"]
        for r in d.execute(f"SELECT student_id, points FROM points_cache WHERE student_id IN ({ph})", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["points"] = r["points"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM attempts WHERE student_id IN ({ph}) AND status='done' GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["practice_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM chat_logs WHERE student_id IN ({ph}) AND answer!='' GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["ai_ask"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM wrong_records WHERE student_id IN ({ph}) AND status='active' GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["wrong_active"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM user_badges WHERE student_id IN ({ph}) GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["badge_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COUNT(*) c FROM training_enrolls WHERE student_id IN ({ph}) GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["enroll_count"] = r["c"]
        for r in d.execute(f"SELECT student_id, COALESCE(SUM(minutes),0) m FROM study_events WHERE student_id IN ({ph}) GROUP BY student_id", ids):  # nosec B608（人工确认：参数化/白名单常量拼接）
            stats[r["student_id"]]["hours"] = round(r["m"] or 0, 1)
    classes = [r[0] for r in d.execute(
        "SELECT DISTINCT class_name FROM users WHERE role='student' AND class_name!='' ORDER BY class_name")]
    d.close()
    items = []
    for r in rows:
        s = stats[r["id"]]
        lv = s["mastery"]
        s["avg_mastery"] = round(sum(lv.values()) / len(lv), 1) if lv else 0
        items.append({**dict(r), **s})
    return {"items": items, "classes": classes}


class StudentIn(BaseModel):
    name: str
    student_no: str = ""
    password: str = "123456"
    enabled: int = 1
    class_name: str = ""


@router.post("/students/class")
def students_set_class(b: dict, u: dict = Depends(require_teacher)):
    """批量设置学生班级（教师按名单补分班/调整班级）。"""
    ids = [int(i) for i in (b.get("ids") or [])]
    cls = (b.get("class_name") or "").strip()[:30]
    if not ids:
        raise HTTPException(400, "未选择学生")
    d = db.get_db()
    ph = ",".join("?" * len(ids))
    cur = d.execute(f"UPDATE users SET class_name=? WHERE id IN ({ph}) AND role='student'",  # nosec B608
                    [cls] + ids)
    d.commit()
    d.close()
    return {"ok": True, "updated": cur.rowcount}


@router.post("/students/class-roster")
def students_class_roster(b: dict, u: dict = Depends(require_teacher)):
    """按名单批量分班：粘贴学号串（换行/逗号/空格混合分隔均可）→ 一次性归入指定班级。

    class_name 留空 = 移为未分班。返回更新数与未找到的学号（前 50 个）。"""
    import re
    nos = [t.strip() for t in re.split(r"[\s,，;；、]+", b.get("text") or "") if t.strip()]
    if not nos:
        raise HTTPException(400, "请粘贴学号（换行、逗号、空格均可分隔）")
    nos = list(dict.fromkeys(nos))
    cn = (b.get("class_name") or "").strip()[:30]
    d = db.get_db()
    valid = [r[0] for r in d.execute(
        "SELECT DISTINCT student_no FROM users WHERE role='student' AND student_no IN (" +
        ",".join("?" * len(nos)) + ")", nos)]
    if valid:
        d.execute("UPDATE users SET class_name=? WHERE role='student' AND student_no IN (" +
                  ",".join("?" * len(valid)) + ")", [cn] + valid)
        d.commit()
    missing = [n for n in nos if n not in set(valid)]
    d.close()
    return {"updated": len(valid), "not_found": missing[:50], "class_name": cn or "未分班"}


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
    h = bcrypt.hashpw(_clean_pwd(s.password).encode(), bcrypt.gensalt(10)).decode()
    cur = d.execute(
        "INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at,class_name) VALUES(?,?,?,?,?,?,?)",
        (sno, s.name, "student", h, s.enabled, int(time.time()), (s.class_name or "").strip()[:30]))
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
        sets.append("pwd_hash=?"); args.append(bcrypt.hashpw(_clean_pwd(s.password, strict=False).encode(), bcrypt.gensalt(10)).decode())
    sets.append("enabled=?"); args.append(s.enabled)
    args.append(uid)
    d.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", args)  # nosec B608（人工确认：参数化/白名单常量拼接）
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
    if a.role == "teacher":
        # 横向越权防护：教师账号只能由部署方（数据库/CLI）创建，管理后台不允许再造教师号
        raise HTTPException(403, "管理后台仅可创建学生账号")
    h = bcrypt.hashpw(_clean_pwd(a.password).encode(), bcrypt.gensalt(10)).decode()
    cur = d.execute(
        "INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at) VALUES(?,?,?,?,?,?)",
        (sno, a.name, a.role, h, a.enabled, int(time.time())))
    d.commit()
    d.close()
    return {"ok": True, "id": cur.lastrowid, "student_no": sno}


class AccountBatchIn(BaseModel):
    count: int = 10
    prefix: str = "S20261"       # 学号前缀，后接两位序号（如 S20261 01..30）
    password: str = "123456"
    name_tpl: str = "同学{seq}"  # 姓名模板，{seq}=序号（真实试用前请替换为真实姓名模板）


@router.post("/accounts/batch")
def accounts_batch(b: AccountBatchIn, u: dict = Depends(require_teacher)):
    """批量创建学生账号（真实试用 / 教学批量发号）。已存在的学号跳过不报错。"""
    import bcrypt
    if not 1 <= b.count <= 100:
        raise HTTPException(400, "单次批量 1–100 个")
    if not re.match(r"^[A-Za-z0-9]{2,12}$", b.prefix):
        raise HTTPException(400, "前缀仅支持字母/数字（2–12 位）")
    h = bcrypt.hashpw(_clean_pwd(b.password).encode(), bcrypt.gensalt(10)).decode()
    d = db.get_db()
    made, skipped = [], []
    for i in range(1, b.count + 1):
        sno = f"{b.prefix}{i:02d}"
        if d.execute("SELECT 1 FROM users WHERE student_no=?", (sno,)).fetchone():
            skipped.append(sno)
            continue
        name = b.name_tpl.replace("{seq}", str(i))
        d.execute("INSERT INTO users(student_no,name,role,pwd_hash,enabled,created_at) VALUES(?,?,?,?,1,?)",
                  (sno, name, "student", h, int(time.time())))
        made.append(sno)
    d.commit()
    d.close()
    return {"ok": True, "created": len(made), "skipped": skipped, "items": made}


@router.delete("/accounts/{uid}")
def accounts_delete(uid: int, u: dict = Depends(require_teacher)):
    """物理删除账号及其学习痕迹（不可恢复，慎用）。"""
    if uid == u["id"]:
        raise HTTPException(400, "不能删除自己的账号")
    d = db.get_db()
    _teacher_owned_only(d, uid, u["id"])  # 不存在 → 404；其他教师 → 403（横向越权防护）
    d.execute("DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id=?)", (uid,))
    d.execute("DELETE FROM ai_grades WHERE attempt_id IN (SELECT id FROM attempts WHERE student_id=?)", (uid,))
    # 教师创建的考卷一并删除（否则 exams 表残留死行，FK 悬空）
    d.execute("DELETE FROM exam_items WHERE exam_id IN (SELECT id FROM exams WHERE created_by=?)", (uid,))
    d.execute("DELETE FROM exams WHERE created_by=?", (uid,))
    for t in ("mastery", "wrong_records", "chat_logs", "points_log", "checkins",
              "user_badges", "student_sessions", "attempts", "points_cache",
              "study_events", "training_enrolls"):
        d.execute(f"DELETE FROM {t} WHERE student_id=?", (uid,))  # nosec B608（人工确认：参数化/白名单常量拼接）
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
    _teacher_owned_only(d, uid, u["id"])  # 不存在 → 404；其他教师 → 403（横向越权防护）
    sets, args = [], []
    if a.enabled is not None:
        sets.append("enabled=?"); args.append(a.enabled)
    if a.password:
        sets.append("pwd_hash=?")
        args.append(bcrypt.hashpw(_clean_pwd(a.password, strict=False).encode(), bcrypt.gensalt(10)).decode())
    args.append(uid)
    d.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", args)  # nosec B608（人工确认：参数化/白名单常量拼接）
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


def _own_training(d, tid: int, me: int):
    """培训归属校验：只有创建者能改（防教师互相改动/删除他人培训）。失败时关闭连接。"""
    row = d.execute("SELECT teacher_id FROM trainings WHERE id=?", (tid,)).fetchone()
    if not row:
        d.close()
        raise HTTPException(404, "培训不存在")
    if row["teacher_id"] != me:
        d.close()
        raise HTTPException(403, "只能管理自己创建的培训")
    return row


@router.put("/trainings/{tid}")
def trainings_update(tid: int, t: TrainingIn, u: dict = Depends(require_teacher)):
    title = _check_title(t.title)
    d = db.get_db()
    _own_training(d, tid, u["id"])
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
    _own_training(d, tid, u["id"])
    tr = d.execute("SELECT capacity FROM trainings WHERE id=?", (tid,)).fetchone()
    status = body.get("status") or "enrolled"
    if status not in ("enrolled", "done"):
        d.close()
        raise HTTPException(400, "status 仅支持 enrolled/done")
    sids = body.get("student_ids") or []
    # 容量校验：新报名（非已报名者）超出 capacity 直接拒绝
    if status == "enrolled" and sids:
        ph = ",".join("?" * len(sids))
        already = {r["student_id"] for r in d.execute(
            f"SELECT student_id FROM training_enrolls WHERE training_id=? AND student_id IN ({ph})",  # nosec B608（人工确认：参数化/白名单常量拼接）
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
    _own_training(d, tid, u["id"])
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
    _own_training(d, tid, u["id"])
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
        r = d.execute(f"SELECT COUNT(DISTINCT student_id) c FROM ({_ACTIVE_SRC})",  # nosec B608（人工确认：参数化/白名单常量拼接）
                      _active_params(days)).fetchone()
        return r["c"]

    def active_list(days):
        """活跃学生明细（启用学生，供指标卡下钻展示）。"""
        rows = d.execute(
            f"SELECT u.student_no, u.name FROM users u WHERE u.role='student' AND u.enabled=1 "  # nosec B608（人工确认：参数化/白名单常量拼接）
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
            wr = round((r["wrong"] or 0) * 100 / r["n"], 1)
            weak.append({"cluster": r["cluster_id"], "name": db.CLUSTER_NAMES[r["cluster_id"]],
                         "n": r["n"], "wrong": r["wrong"] or 0, "rate": wr,
                         "correct": round(100 - wr, 1)})
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


@router.get("/asks/recent")
def asks_recent(limit: int = 20, u: dict = Depends(require_teacher)):
    """最近 AI 问答明细（数据总览「AI 问答总量」卡下钻用）。

    只读：问题原文截断 + 答案摘录 + 触达簇；教师端展示昵称与学号。"""
    d = db.get_db()
    limit = max(1, min(int(limit), 50))
    rows = d.execute(
        "SELECT c.question, c.answer, c.clusters_touched, c.created_at, u.student_no, u.name "
        "FROM chat_logs c JOIN users u ON u.id=c.student_id "
        "WHERE c.answer!='' ORDER BY c.created_at DESC, c.id DESC LIMIT ?", (limit,)).fetchall()
    d.close()
    return {"items": [
        {"student_no": r["student_no"], "name": r["name"], "created_at": r["created_at"],
         "question": (r["question"] or "")[:120],
         "answer_excerpt": (r["answer"] or "")[:100],
         "clusters": r["clusters_touched"] or ""}
        for r in rows]}


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


@router.get("/stats/wrong")
def stats_wrong(u: dict = Depends(require_teacher), cls: str = ""):
    """班级错题分析：高频错题 TOP10（多少名学生在错题本）+ 各知识点正确率 + 错题分布。

    cls 按班级过滤：不传=全部学生；'__none__'=未分班；其他值=精确班级名。"""
    d = db.get_db()
    wcls = ""
    cls_params: list = []
    if cls == "__none__":
        wcls = " AND (class_name='' OR class_name IS NULL)"
    elif cls:
        wcls = " AND class_name=?"
        cls_params.append(cls)
    sids = [r[0] for r in d.execute(
        "SELECT id FROM users WHERE role='student' AND enabled=1" + wcls + " ORDER BY id", cls_params)]
    classes = [r[0] for r in d.execute(
        "SELECT DISTINCT class_name FROM users WHERE role='student' AND class_name!='' ORDER BY class_name")]
    top_wrong, correct_rate, wrong_by_cluster = [], [], []
    if sids:
        ph = ",".join("?" * len(sids))
        rows = d.execute(
            f"SELECT q.id, q.stem, q.cluster_id, COUNT(DISTINCT w.student_id) c FROM wrong_records w "  # nosec B608（人工确认：{ph} 由 ? 占位符拼接，值全部参数化绑定）
            f"JOIN questions q ON q.id=w.question_id WHERE w.status='active' AND w.student_id IN ({ph}) "
            f"GROUP BY w.question_id ORDER BY c DESC, MIN(w.first_wrong_at) DESC LIMIT 10", sids).fetchall()
        top_wrong = [{"qid": r["id"], "stem": r["stem"], "cluster": r["cluster_id"], "students_wrong": r["c"]}
                     for r in rows]
        ar = d.execute(
            f"SELECT q.cluster_id, COUNT(*) n, SUM(a.correct) ok FROM answers a "  # nosec B608（人工确认：{ph} 由 ? 占位符拼接，值全部参数化绑定）
            f"JOIN attempts t ON t.id=a.attempt_id JOIN questions q ON q.id=a.question_id "
            f"WHERE t.student_id IN ({ph}) GROUP BY q.cluster_id ORDER BY n DESC", sids).fetchall()
        correct_rate = [{"cluster": r["cluster_id"], "n": r["n"],
                         "rate": round((r["ok"] or 0) * 100 / r["n"], 1) if r["n"] else None} for r in ar]
        wc = d.execute(
            f"SELECT q.cluster_id, w.status, COUNT(*) c FROM wrong_records w "  # nosec B608（人工确认：{ph} 由 ? 占位符拼接，值全部参数化绑定）
            f"JOIN questions q ON q.id=w.question_id WHERE w.student_id IN ({ph}) "
            f"GROUP BY q.cluster_id, w.status", sids).fetchall()
        per = {}
        for r in wc:
            p = per.setdefault(r["cluster_id"], {"active": 0, "mastered": 0})
            p[r["status"]] = p.get(r["status"], 0) + r["c"]
        wrong_by_cluster = [{"cluster": cid, "active": p.get("active", 0), "mastered": p.get("mastered", 0)}
                            for cid, p in per.items()]
        wrong_by_cluster.sort(key=lambda x: -(x["active"] + x["mastered"]))
    # 分班对比：各班 人数 / 活跃错题 / 已掌握 / 总体正确率 / 最弱簇（自动定位）
    per_class = []
    cls_cnt = {}
    for r in d.execute("SELECT COALESCE(NULLIF(class_name,''),'__none__') c, COUNT(*) c2 "
                       "FROM users WHERE role='student' AND enabled=1 GROUP BY 1"):
        cls_cnt[r["c"]] = r["c2"]
    if cls_cnt:
        wstat = {}
        for r in d.execute(
                "SELECT COALESCE(NULLIF(u.class_name,''),'__none__') cls, w.status, COUNT(*) c2 "
                "FROM wrong_records w JOIN users u ON u.id=w.student_id "
                "WHERE u.role='student' AND u.enabled=1 GROUP BY 1,2"):
            wstat.setdefault(r["cls"], {}).setdefault(r["status"], 0)
            wstat[r["cls"]][r["status"]] += r["c2"]
        ar2 = {}
        for r in d.execute(
                "SELECT COALESCE(NULLIF(u.class_name,''),'__none__') c, q.cluster_id cid, COUNT(*) n, SUM(a.correct) ok "
                "FROM answers a JOIN attempts t ON t.id=a.attempt_id JOIN users u ON u.id=t.student_id "
                "JOIN questions q ON q.id=a.question_id "
                "WHERE u.role='student' AND u.enabled=1 GROUP BY 1,2"):
            ar2.setdefault(r["c"], {})[r["cid"]] = (r["n"], r["ok"] or 0)
        for cname, nstu in sorted(cls_cnt.items(), key=lambda kv: (kv[0] != "__none__", kv[0])):
            ws = wstat.get(cname, {})
            cm = ar2.get(cname, {})
            tot_n = sum(n for n, _ in cm.values())
            tot_ok = sum(ok for _, ok in cm.values())
            rows = sorted([{"cluster": cid, "name": db.CLUSTER_NAMES.get(cid, cid),
                            "rate": round(ok * 100 / n, 1)} for cid, (n, ok) in cm.items() if n],
                          key=lambda x: x["rate"])
            per_class.append({
                "class": "未分班" if cname == "__none__" else cname,
                "students": nstu,
                "active": ws.get("active", 0),
                "mastered": ws.get("mastered", 0),
                "rate": round(tot_ok * 100 / tot_n, 1) if tot_n else None,
                "weakest": ({"cluster": rows[0]["cluster"], "name": rows[0]["name"], "rate": rows[0]["rate"]}
                            if rows else None),
            })
    d.close()
    return {"top_wrong": top_wrong, "correct_rate": correct_rate,
            "wrong_by_cluster": wrong_by_cluster, "classes": classes, "per_class": per_class}


# ---------- 邀请码（学生自助批量加入 · 替代逐个建号） ----------
class InviteIn(BaseModel):
    note: str = ""          # 备注（如「2026 级养老 1 班」）
    max_uses: int = 60      # 人数上限
    days: int = 30          # 有效期（天）
    class_name: str = ""    # 班级名：学生注册时自动归入该班


@router.post("/invites")
def invites_create(b: InviteIn, u: dict = Depends(require_teacher)):
    """生成邀请码：学生凭「邀请码 + 昵称 + 自设密码」自助注册，教师无需逐个建号。"""
    import secrets
    if not 1 <= b.max_uses <= 500:
        raise HTTPException(400, "人数上限 1–500")
    if not 1 <= b.days <= 365:
        raise HTTPException(400, "有效期 1–365 天")
    note = (b.note or "").strip()[:40]
    cls = (b.class_name or "").strip()[:30]
    d = db.get_db()
    now = int(time.time())
    # 去掉易混字符（0/O、1/I/L）的 6 位码：FD-XXXXXX
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    code = ""
    for _ in range(8):
        code = "FD-" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not d.execute("SELECT 1 FROM invite_codes WHERE code=?", (code,)).fetchone():
            break
    exp = now + b.days * 86400
    d.execute("INSERT INTO invite_codes(code,note,class_name,created_by,max_uses,used_count,expires_at,enabled,created_at) "
              "VALUES(?,?,?,?,0,?,1,?,?)", (code, note, cls, u["id"], b.max_uses, exp, now))
    d.commit()
    d.close()
    return {"ok": True, "code": code, "note": note, "class_name": cls, "max_uses": b.max_uses,
            "expires_at": exp, "path": f"/register?code={code}"}


@router.get("/invites")
def invites_list(u: dict = Depends(require_teacher)):
    d = db.get_db()
    rows = d.execute("SELECT * FROM invite_codes ORDER BY id DESC LIMIT 50").fetchall()
    d.close()
    now = int(time.time())
    items = []
    for r in rows:
        items.append({
            "id": r["id"], "code": r["code"], "note": r["note"],
            "class_name": r["class_name"] if "class_name" in r.keys() else "",
            "created_by": r["created_by"],
            "max_uses": r["max_uses"], "used_count": r["used_count"],
            "expires_at": r["expires_at"], "enabled": bool(r["enabled"]),
            "expired": int(r["expires_at"]) < now,
            "full": int(r["used_count"]) >= int(r["max_uses"]),
            "mine": int(r["created_by"] or 0) == int(u["id"]),
            "path": f"/register?code={r['code']}",
        })
    return {"items": items}


class InvitePatch(BaseModel):
    enabled: int


@router.put("/invites/{iid}")
def invites_update(iid: int, b: InvitePatch, u: dict = Depends(require_teacher)):
    d = db.get_db()
    row = d.execute("SELECT * FROM invite_codes WHERE id=?", (iid,)).fetchone()
    if not row:
        d.close()
        raise HTTPException(404, "邀请码不存在")
    if int(row["created_by"] or 0) != int(u["id"]):
        d.close()
        raise HTTPException(403, "只能操作自己生成的邀请码")  # 横向越权防护
    d.execute("UPDATE invite_codes SET enabled=? WHERE id=?", (1 if b.enabled else 0, iid))
    d.commit()
    d.close()
    return {"ok": True}


@router.delete("/invites/{iid}")
def invites_delete(iid: int, u: dict = Depends(require_teacher)):
    d = db.get_db()
    row = d.execute("SELECT * FROM invite_codes WHERE id=?", (iid,)).fetchone()
    if not row:
        d.close()
        raise HTTPException(404, "邀请码不存在")
    if int(row["created_by"] or 0) != int(u["id"]):
        d.close()
        raise HTTPException(403, "只能删除自己生成的邀请码")
    d.execute("DELETE FROM invite_codes WHERE id=?", (iid,))
    d.commit()
    d.close()
    return {"ok": True}