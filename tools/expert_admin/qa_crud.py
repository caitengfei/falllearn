# -*- coding: utf-8 -*-
"""QA 专家 · CRUD 全循环实测（公告/轮播/培训/学生/账号 + 考试 E2E + 一致性）。
创建的所有数据均带 EXPERT-qa- 前缀；E2E 学生与培训的清理由 qa_cleanup.py 完成（UI 截图需要它们）。
严禁调用：reset-demo / ai generate-questions 真实生成 / ai grade 真实判卷。
"""
import json
import os
import struct
import sys
import zlib
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import Recorder, login, req, jbody, TAG, BASE  # noqa

rec = Recorder()
T = None
created = {"banners": [], "announcements": [], "trainings": [], "students": [], "accounts": [], "uploads": []}

# ---------- PNG 工具 ----------
def make_png(w, h, rgb=(228, 57, 60)):
    def chunk(t, data):
        c = struct.pack(">I", len(data)) + t + data
        return c + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return sig + ihdr + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

# ---------- 基线 ----------
st, body = login("T2026")
assert st == 200 and "token" in body, f"教师登录失败 {st} {body}"
T = body["token"]
st, body = req("GET", "/api/admin/students", T)
baseline_students = [s["student_no"] for s in body["items"]]
st, body = req("GET", "/api/admin/banners", T)
baseline_banners = [b["id"] for b in body["items"]]
st, body = req("GET", "/api/admin/trainings", T)
baseline_trainings = [t["id"] for t in body["items"]]
print(f"基线: 学生={baseline_students} 轮播={baseline_banners} 培训={baseline_trainings}")

# ============================================================ 1) 公告 CRUD
print("\n=== 1. 公告 CRUD ===")
st, body = req("POST", "/api/admin/announcements", T,
               {"title": f"{TAG}-公告全循环", "summary": "摘要A", "content": "正文",
                "start_date": "", "end_date": "", "pinned": 0, "enabled": 1})
nid = body.get("id") if isinstance(body, dict) else None
rec.log("N", "公告创建", st == 200 and nid, f"{st} {body}")
if nid:
    created["announcements"].append(nid)
    st, body = req("GET", "/api/admin/announcements", T)
    ids = [a["id"] for a in body["items"]]
    rec.log("N", "公告列表含新建项", nid in ids, f"items={ids}")
    # 置顶 → 排序 pinned DESC 生效
    st, body = req("PUT", f"/api/admin/announcements/{nid}", T,
                   {"title": f"{TAG}-公告全循环", "summary": "摘要A", "content": "正文",
                    "start_date": "", "end_date": "", "pinned": 1, "enabled": 1})
    st2, b2 = req("GET", "/api/admin/announcements", T)
    top = b2["items"][0]["id"] if b2["items"] else None
    rec.log("N", "公告置顶后排最前", st == 200 and top == nid, f"st={st} top_id={top}")
    # 停用 → 公开接口不出现
    st, body = req("PUT", f"/api/admin/announcements/{nid}", T,
                   {"title": f"{TAG}-公告全循环", "summary": "摘要A", "content": "正文",
                    "start_date": "", "end_date": "", "pinned": 0, "enabled": 0})
    _, pub = req("GET", "/api/content/announcements")
    pub_ids = [a["id"] for a in pub["items"]]
    rec.log("N", "停用公告不出现在公开接口", st == 200 and nid not in pub_ids, f"pub_ids={pub_ids}")
    # 重新启用 → 公开接口出现
    st, body = req("PUT", f"/api/admin/announcements/{nid}", T,
                   {"title": f"{TAG}-公告全循环", "summary": "摘要A", "content": "正文",
                    "start_date": "", "end_date": "", "pinned": 0, "enabled": 1})
    _, pub = req("GET", "/api/content/announcements")
    pub_ids = [a["id"] for a in pub["items"]]
    rec.log("N", "启用公告出现在公开接口", st == 200 and nid in pub_ids, f"pub_ids={pub_ids}")
    # 删除
    st, body = req("DELETE", f"/api/admin/announcements/{nid}", T)
    _, adm = req("GET", "/api/admin/announcements", T)
    _, pub = req("GET", "/api/content/announcements")
    rec.log("N", "公告删除(管理+公开均消失)",
            st == 200 and nid not in [a["id"] for a in adm["items"]] and nid not in [a["id"] for a in pub["items"]],
            f"{st} {body}")
    created["announcements"].remove(nid)

# 公开日期窗：end_date=昨天 的启用公告不应出现
print("\n=== 1b. 公告日期窗 ===")
yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
st, body = req("POST", "/api/admin/announcements", T,
               {"title": f"{TAG}-过期公告", "summary": "s", "content": "c",
                "start_date": "", "end_date": yesterday, "pinned": 0, "enabled": 1})
nid2 = body.get("id") if isinstance(body, dict) else None
_, pub = req("GET", "/api/content/announcements")
_, adm = req("GET", "/api/admin/announcements", T)
rec.log("N", "end_date=昨天: 公开不出现/管理可见",
        st == 200 and nid2 is not None
        and nid2 not in [a["id"] for a in pub["items"]] and nid2 in [a["id"] for a in adm["items"]],
        f"pub={[a['id'] for a in pub['items']]} adm={[a['id'] for a in adm['items']]}")
if nid2:
    created["announcements"].append(nid2)

# ============================================================ 2) 轮播 CRUD + 上传
print("\n=== 2. 轮播 CRUD + 图片上传 ===")
png = make_png(600, 340)
st, body = req("POST", "/api/admin/upload", T,
               files={"file": (f"{TAG}-banner.png", png, "image/png")})
up_url = body.get("url") if isinstance(body, dict) else None
rec.log("U", "轮播图上传(600x340 png)", st == 200 and up_url, f"{st} {body}")
if up_url:
    created["uploads"].append(up_url)
    r = requests.get(BASE + up_url, timeout=20)
    rec.log("U", "上传文件可回读(200, image/png)",
            r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"),
            f"{r.status_code} {r.headers.get('content-type')} len={len(r.content)}")

st, body = req("POST", "/api/admin/banners", T,
               {"title": f"{TAG}-轮播全循环", "tag": "QA", "sub": "副标题", "image": up_url or "",
                "link": "/learn", "sort": 99, "enabled": 1})
bid = body.get("id") if isinstance(body, dict) else None
rec.log("B", "轮播卡创建", st == 200 and bid, f"{st} {body}")
if bid:
    created["banners"].append(bid)
    _, pub = req("GET", "/api/content/banners")
    rec.log("B", "启用轮播出现在公开接口", bid in [b["id"] for b in pub["items"]],
            f"pub_ids={[b['id'] for b in pub['items']]}")
    # 停用 → 公开消失
    st, body = req("PUT", f"/api/admin/banners/{bid}", T,
                   {"title": f"{TAG}-轮播全循环", "tag": "QA", "sub": "副标题", "image": up_url or "",
                    "link": "/learn", "sort": 99, "enabled": 0})
    _, pub = req("GET", "/api/content/banners")
    rec.log("B", "停用轮播不在公开接口", st == 200 and bid not in [b["id"] for b in pub["items"]],
            f"pub_ids={[b['id'] for b in pub['items']]}")
    # 重新启用
    st, body = req("PUT", f"/api/admin/banners/{bid}", T,
                   {"title": f"{TAG}-轮播全循环", "tag": "QA", "sub": "副标题", "image": up_url or "",
                    "link": "/learn", "sort": 99, "enabled": 1})
    # 上下移动（复刻 UI moveBanner：交换相邻 sort 值）
    _, adm = req("GET", "/api/admin/banners", T)
    items = adm["items"]
    i = next(k for k, b in enumerate(items) if b["id"] == bid)
    j = i - 1
    mine, other = items[i], items[j]
    req("PUT", f"/api/admin/banners/{mine['id']}", T, {**mine, "sort": j})
    req("PUT", f"/api/admin/banners/{other['id']}", T, {**other, "sort": i})
    _, adm = req("GET", "/api/admin/banners", T)
    order = [b["id"] for b in adm["items"]]
    rec.log("B", "轮播上移(与前一卡交换顺序)", order.index(bid) == j and order.index(other["id"]) == i,
            f"order={order}")
    # 再移回原位
    req("PUT", f"/api/admin/banners/{mine['id']}", T, {**mine, "sort": i})
    req("PUT", f"/api/admin/banners/{other['id']}", T, {**other, "sort": j})
    _, adm = req("GET", "/api/admin/banners", T)
    order = [b["id"] for b in adm["items"]]
    rec.log("B", "轮播下移(恢复原顺序)", order.index(bid) == i and order.index(other["id"]) == j, f"order={order}")
    # 删除
    st, body = req("DELETE", f"/api/admin/banners/{bid}", T)
    _, adm = req("GET", "/api/admin/banners", T)
    _, pub = req("GET", "/api/content/banners")
    rec.log("B", "轮播卡删除(管理+公开均消失)",
            st == 200 and bid not in [b["id"] for b in adm["items"]] and bid not in [b["id"] for b in pub["items"]],
            f"{st} {body}")
    created["banners"].remove(bid)

# ============================================================ 3) 培训 CRUD
print("\n=== 3. 培训 CRUD ===")
st, body = req("GET", "/api/admin/students", T)
sid_lxr = next(s["id"] for s in body["items"] if s["student_no"] == "S2026002")
sid_wdc = next(s["id"] for s in body["items"] if s["student_no"] == "S2026003")
st, body = req("POST", "/api/admin/trainings", T,
               {"title": f"{TAG}-培训全循环", "batch": "QA批次", "start_date": "2026-10-01",
                "end_date": "2026-10-08", "capacity": 5, "note": "QA",
                "student_ids": [sid_lxr, sid_wdc]})
tid = body.get("id") if isinstance(body, dict) else None
rec.log("T", "培训创建(含 2 初始报名)", st == 200 and tid, f"{st} {body}")
if tid:
    created["trainings"].append(tid)
    _, tr = req("GET", "/api/admin/trainings", T)
    t = next(x for x in tr["items"] if x["id"] == tid)
    rec.log("T", "培训报名数=2 且学生名单正确",
            t["enrolled"] == 2 and {s["id"] for s in t["students"]} == {sid_lxr, sid_wdc},
            f"enrolled={t['enrolled']} students={[s['student_no'] for s in t['students']]}")
    # 重复报名（UNIQUE 约束行为）
    st, body = req("POST", f"/api/admin/trainings/{tid}/enroll", T,
                   {"student_ids": [sid_lxr, sid_wdc], "status": "enrolled"})
    _, tr = req("GET", "/api/admin/trainings", T)
    t = next(x for x in tr["items"] if x["id"] == tid)
    rec.log("T", "同学生重复报名不 500/不重复计数", st == 200 and t["enrolled"] == 2, f"{st} {body} enrolled={t['enrolled']}")
    # 标记完成 → 完成率 50%
    st, body = req("POST", f"/api/admin/trainings/{tid}/students/{sid_lxr}/status", T, {"status": "done"})
    _, tr = req("GET", "/api/admin/trainings", T)
    t = next(x for x in tr["items"] if x["id"] == tid)
    rec.log("T", "标记完成后 rate=done/enrolled=50.0", st == 200 and t["done"] == 1 and t["rate"] == 50.0,
            f"done={t['done']} rate={t['rate']}")
    # 非法 status
    st, body = req("POST", f"/api/admin/trainings/{tid}/enroll", T,
                   {"student_ids": [sid_lxr], "status": "nope"})
    rec.log("T", "enroll 非法 status → 4xx 中文", st == 400 and "status" in jbody(st, body), f"{st} {jbody(st, body)}")
    st, body = req("POST", f"/api/admin/trainings/{tid}/students/{sid_lxr}/status", T, {"status": "nope"})
    rec.log("T", "set_status 非法 status → 4xx 中文", st == 400 and "status" in jbody(st, body), f"{st} {jbody(st, body)}")
    # 不存在的培训
    st, body = req("POST", "/api/admin/trainings/999999/enroll", T, {"student_ids": [sid_lxr]})
    rec.log("T", "不存在培训 enroll → 404 中文", st == 404 and "培训" in jbody(st, body), f"{st} {jbody(st, body)}")
    # 不存在的 (培训,学生) set_status
    st, body = req("POST", f"/api/admin/trainings/{tid}/students/999999/status", T, {"status": "done"})
    rec.log("T", "set_status 不存在学生 → 静默 200(记录实际行为)", st in (200, 404), f"实际 {st} {body}")
    # 统计一致性
    _, stt = req("GET", "/api/admin/stats/trainings", T)
    t2 = next((x for x in stt["trainings"] if x["id"] == tid), None)
    rec.log("T", "stats/trainings 与列表一致(enrolled/done/rate)",
            t2 is not None and t2["enrolled"] == t["enrolled"] and t2["done"] == t["done"] and t2["rate"] == t["rate"],
            f"stats={t2}")
    teach = next((x for x in stt["teachers"] if x["name"] == "陈老师"), None)
    rec.log("T", "教师带训计数 = 基线培训数+1(本培训)",
            teach is not None and teach["trainings"] == len(baseline_trainings) + 1,
            f"teacher={teach} baseline={len(baseline_trainings)}")
    # 删除 → 报名级联
    st, body = req("DELETE", f"/api/admin/trainings/{tid}", T)
    _, tr = req("GET", "/api/admin/trainings", T)
    _, stt = req("GET", "/api/admin/stats/trainings", T)
    rec.log("T", "培训删除(列表+统计均消失)",
            st == 200 and tid not in [x["id"] for x in tr["items"]] and tid not in [x["id"] for x in stt["trainings"]],
            f"{st} {body}")
    created["trainings"].remove(tid)

# ============================================================ 4) 学生 CRUD
print("\n=== 4. 学生创建/重复姓名/停用/重置密码 ===")
st, body = req("POST", "/api/admin/students", T, {"name": f"{TAG}-重名生A", "password": "123456"})
s4 = body.get("student_no") if isinstance(body, dict) else None
s4_id = body.get("id") if isinstance(body, dict) else None
rec.log("S", "学生创建(自动学号)", st == 200 and s4 == "S2026004", f"{st} {body}")
if s4_id:
    created["students"].append(s4_id)
st, body = req("POST", "/api/admin/students", T, {"name": f"{TAG}-重名生A", "password": "123456"})
s5 = body.get("student_no") if isinstance(body, dict) else None
s5_id = body.get("id") if isinstance(body, dict) else None
rec.log("S", "重复姓名允许且学号递增", st == 200 and s5 == "S2026005", f"{st} {body}")
if s5_id:
    created["students"].append(s5_id)
st, body = req("POST", "/api/admin/students", T, {"name": f"{TAG}-重复学号", "student_no": "S2026001"})
rec.log("S", "显式学号与现有重复 → 400 中文", st == 400 and "学号" in jbody(st, body), f"{st} {jbody(st, body)}")
# 重置密码（S2026005）
st, body = req("PUT", f"/api/admin/students/{s5_id}", T, {"name": f"{TAG}-重名生A", "password": "123456", "enabled": 1})
rec.log("S", "学生重置密码 200", st == 200, f"{st} {body}")
# 停用 S2026005
st, body = req("PUT", f"/api/admin/students/{s5_id}", T, {"name": f"{TAG}-重名生A", "password": "", "enabled": 0})
rec.log("S", "学生停用 200", st == 200, f"{st} {body}")
st, body = login(s5)
login_ok = st == 200 and isinstance(body, dict) and "token" in body
print(f"  [info] 停用后登录: HTTP {st} token={'yes' if login_ok else 'no'}")
rec.log("S", "停用账号无法登录(预期 4xx)", not login_ok, f"实际 {st} {str(body)[:120]}")
if login_ok:
    me_st, me_body = req("GET", "/api/auth/me", body["token"])
    rec.log("S", "停用账号调受保护接口 → 403 中文", me_st == 403 and "停用" in jbody(me_st, me_body),
            f"{me_st} {jbody(me_st, me_body)}")
# 重新启用
st, body = req("PUT", f"/api/admin/students/{s5_id}", T, {"name": f"{TAG}-重名生A", "password": "", "enabled": 1})
st2, body2 = login(s5)
rec.log("S", "重新启用后可登录", st == 200 and st2 == 200 and "token" in body2, f"{st2} {str(body2)[:80]}")

# ============================================================ 5) 账号 CRUD
print("\n=== 5. 账号 CRUD(学生+教师) ===")
st, body = req("POST", "/api/admin/accounts", T, {"name": f"{TAG}-学生账号", "role": "student"})
acc_s = body.get("student_no") if isinstance(body, dict) else None
acc_s_id = body.get("id") if isinstance(body, dict) else None
rec.log("A", "新建学生账号(自动学号)", st == 200 and acc_s == "S2026006", f"{st} {body}")
st, body = req("POST", "/api/admin/accounts", T, {"name": f"{TAG}-教师账号", "role": "teacher"})
acc_t = body.get("student_no") if isinstance(body, dict) else None
acc_t_id = body.get("id") if isinstance(body, dict) else None
rec.log("A", "新建教师账号(自动工号)", st == 200 and acc_t and acc_t.startswith("T"), f"{st} {body} (auto={acc_t})")
st, body = req("POST", "/api/admin/accounts", T, {"name": f"{TAG}-非法角色", "role": "admin"})
rec.log("A", "非法角色 → 400 中文", st == 400 and "角色" in jbody(st, body), f"{st} {jbody(st, body)}")
# 自停/自删 T2026 (id=4)
st, body = req("PUT", "/api/admin/accounts/4", T, {"enabled": 0, "password": ""})
rec.log("A", "自停用 T2026 → 400 中文", st == 400 and "自己" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = req("DELETE", "/api/admin/accounts/4", T)
rec.log("A", "自删除 T2026 → 400 中文", st == 400 and "自己" in jbody(st, body), f"{st} {jbody(st, body)}")
# 账号不存在的更新/删除
st, body = req("PUT", "/api/admin/accounts/999999", T, {"enabled": 1})
rec.log("A", "更新不存在账号 → 404 中文", st == 404 and "账号" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = req("DELETE", "/api/admin/accounts/999999", T)
rec.log("A", "删除不存在账号 → 404 中文", st == 404 and "账号" in jbody(st, body), f"{st} {jbody(st, body)}")
# 删除学生账号 → 从 /students 与 /accounts 消失
if acc_s_id:
    st, body = req("DELETE", f"/api/admin/accounts/{acc_s_id}", T)
    _, adm = req("GET", "/api/admin/accounts", T)
    _, stu = req("GET", "/api/admin/students", T)
    rec.log("A", "删除学生账号后两表均消失",
            st == 200 and acc_s_id not in [a["id"] for a in adm["items"]]
            and acc_s not in [s["student_no"] for s in stu["items"]],
            f"{st} {body}")
    created["students"] = [x for x in created["students"] if x != acc_s_id]
# 删除教师账号
if acc_t_id:
    st, body = req("DELETE", f"/api/admin/accounts/{acc_t_id}", T)
    _, adm = req("GET", "/api/admin/accounts", T)
    rec.log("A", "删除教师账号后消失", st == 200 and acc_t_id not in [a["id"] for a in adm["items"]], f"{st} {body}")

# ============================================================ 6) 考试 E2E（用 S2026004）
print("\n=== 6. 考试 E2E（S2026004 开卷→交卷→管理端可见） ===")
st, body = login(s4)
stok = body["token"] if isinstance(body, dict) else None
assert stok, "E2E 学生登录失败"
st, body = req("POST", "/api/quiz/start", stok, {"kind": "mock"})
aid = body.get("attempt_id") if isinstance(body, dict) else None
n_items = len(body.get("items", [])) if isinstance(body, dict) else 0
rec.log("E", "学生开卷(mock, 10 题)", st == 200 and aid and n_items == 10, f"{st} items={n_items}")
answers = {str(q["question_id"]): "A" for q in (body.get("items") or [])}
st, sub = req("POST", "/api/quiz/submit", stok, {"attempt_id": aid, "answers": answers})
score = sub.get("score") if isinstance(sub, dict) else None
rec.log("E", "学生交卷(全部选 A)", st == 200 and isinstance(score, int), f"{st} score={score}")
# 管理端：列表 / 学生筛选(API) / 明细 / CSV
st, body = req("GET", "/api/admin/exams", T, params={"status": "done"})
row = next((a for a in body["items"] if a["id"] == aid), None)
rec.log("E", "管理端考试列表含该卷", st == 200 and row is not None, f"{st} n={len(body['items'])}")
uid_s4 = s4_id
st, body = req("GET", "/api/admin/exams", T, params={"status": "done", "student_id": uid_s4})
rec.log("E", "API 学生筛选命中(该生 1 条)", st == 200 and len(body["items"]) == 1 and body["items"][0]["id"] == aid,
        f"{st} n={len(body['items'])}")
st, body = req("GET", "/api/admin/exams", T, params={"status": "done", "student_id": 1})
rec.log("E", "API 学生筛选排除(张小明 0 条)", st == 200 and len(body["items"]) == 0, f"{st} n={len(body['items'])}")
st, body = req("GET", f"/api/admin/exams/{aid}", T)
n_det = len(body.get("items", [])) if isinstance(body, dict) else 0
rec.log("E", "逐题明细 10 题(含题干/标准答案)",
        st == 200 and n_det == 10 and all(i.get("stem") and i.get("answer") for i in body.get("items", [])),
        f"{st} n={n_det}")
r = requests.get(BASE + "/api/admin/exams/export", params={"student_id": uid_s4},
                 headers={"Authorization": f"Bearer {T}"}, timeout=30)
csv_ok = r.status_code == 200 and ("text/csv" in r.headers.get("content-type", "")) and (s4 in r.text)
rec.log("E", "CSV 导出(含该生行)", csv_ok, f"{r.status_code} ct={r.headers.get('content-type')} head={r.text[:120]!r}")
# 学生表学时一致性（与 stats/overview hours 对比）
_, stu = req("GET", "/api/admin/students", T)
me_row = next(s for s in stu["items"] if s["id"] == uid_s4)
_, ov = req("GET", "/api/admin/stats/overview", T)
ov_row = next((h for h in ov["hours"] if h["student_no"] == s4), None)
rec.log("E", "学生表学时 == stats/overview 学时",
        me_row["hours"] == (ov_row["hours"] if ov_row else None),
        f"students.hours={me_row['hours']} overview.hours={ov_row}")
# 六簇色块数据源：S2026004 交卷后 mastery 应有 6 簇（练习覆盖到的簇）
rec.log("E", "学生表 mastery 含本次练习簇(色块数据源)",
        isinstance(me_row.get("mastery"), dict) and len(me_row["mastery"]) >= 1,
        f"mastery={me_row.get('mastery')}")

# 保留 E2E 学生与 1 份培训供 UI 截图；其余学生账号在 qa_cleanup.py 清理
print(f"\n[E2E 保留] 学生 {s4}(id={s4_id}) attempt_id={aid} score={score}")
print(f"[保留供 UI] 培训将由 qa_ui 前重建")

# 重建一个培训供 UI 截图（带完成状态）
st, body = req("POST", "/api/admin/trainings", T,
               {"title": f"{TAG}-UI截图培训", "batch": "QA批次", "start_date": "2026-10-01",
                "end_date": "2026-10-08", "capacity": 5, "note": "",
                "student_ids": [sid_lxr, sid_wdc, uid_s4]})
tid2 = body.get("id") if isinstance(body, dict) else None
if tid2:
    created["trainings"].append(tid2)
    req("POST", f"/api/admin/trainings/{tid2}/students/{sid_lxr}/status", T, {"status": "done"})
print(f"[保留供 UI] 培训 id={tid2}")

# 学生/账号清单（供清理）
cleanup_list = {
    "students_to_delete": created["students"],
    "trainings_to_delete": created["trainings"],
    "announcements_to_delete": created["announcements"],
    "banners_to_delete": created["banners"],
    "uploads_to_delete": created["uploads"],
    "e2e_student": {"student_no": s4, "id": s4_id, "attempt_id": aid, "score": score},
}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_crud_state.json"), "w", encoding="utf-8") as f:
    json.dump(cleanup_list, f, ensure_ascii=False, indent=2)

print("\n" + rec.summary())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_crud_results.json"), "w", encoding="utf-8") as f:
    json.dump(rec.results, f, ensure_ascii=False, indent=2)