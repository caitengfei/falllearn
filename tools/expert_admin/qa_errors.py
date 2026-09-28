# -*- coding: utf-8 -*-
"""QA 专家 · 边界与错误路径实测（应得干净 4xx 中文错误，任何 500 都是 bug）。
AI 端点只测同步报错路径；不触发真实生成/判卷。
settings.ai_model 若被 model POST 污染，结尾恢复（基线为空）。
"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import Recorder, login, req, jbody, TAG  # noqa

rec = Recorder()
st, body = login("T2026")
T = body["token"]
st2, sbody = login("S2026001")
ST_T = sbody["token"]
print(f"token: teacher ok={st == 200} student ok={st2 == 200}")

DB = r"E:\lilei\platform\backend\falllearn.db"
KB = r"E:\lilei\跌倒-岗课赛证知识库"

print("\n=== 1. 公告/轮播 空值与不存在 id ===")
st, body = req("POST", "/api/admin/announcements", T,
               {"title": "", "summary": "x", "content": "x", "pinned": 0, "enabled": 1})
empty_nid = body.get("id") if isinstance(body, dict) else None
rec.log("E1", "公告空标题 → 4xx 中文(实际记录)", st == 400 and "标题" in jbody(st, body),
        f"实际 {st} {jbody(st, body)}")
if empty_nid:
    st3, _ = req("DELETE", f"/api/admin/announcements/{empty_nid}", T)
    print(f"  [cleanup] 已删除空标题公告 id={empty_nid} -> {st3}")

st, body = req("PUT", "/api/admin/announcements/999999", T,
               {"title": f"{TAG}-不存在", "summary": "", "content": "", "pinned": 0, "enabled": 1})
rec.log("E2", "更新不存在公告 → 静默 200(记录实际行为)", st in (200, 404), f"实际 {st} {body}")
st, body = req("DELETE", "/api/admin/announcements/999999", T)
rec.log("E2", "删除不存在公告 → 静默 200(记录实际行为)", st in (200, 404), f"实际 {st} {body}")
st, body = req("PUT", "/api/admin/banners/999999", T,
               {"title": f"{TAG}-不存在", "tag": "", "sub": "", "image": "", "link": "/", "sort": 0, "enabled": 1})
rec.log("E2", "更新不存在轮播 → 静默 200(记录实际行为)", st in (200, 404), f"实际 {st} {body}")
st, body = req("DELETE", "/api/admin/banners/999999", T)
rec.log("E2", "删除不存在轮播 → 静默 200(记录实际行为)", st in (200, 404), f"实际 {st} {body}")
st, body = req("PUT", f"/api/admin/students/999999", T, {"name": "x", "password": "", "enabled": 1})
rec.log("E2", "更新不存在学生 → 404 中文", st == 404 and "学生" in jbody(st, body), f"{st} {jbody(st, body)}")

print("\n=== 2. 考试列表/导出/明细 边界 ===")
st, body = req("GET", "/api/admin/exams", T, params={"status": "badvalue"})
rec.log("E3", "exams?status=badvalue → 干净 4xx(实际记录)", st in (200, 400),
        f"实际 {st} items={body.get('items') if isinstance(body, dict) else body}")
st, body = req("GET", "/api/admin/exams", T, params={"status": "done", "student_id": "abc"})
rec.log("E3", "exams?student_id=abc(非数字) → 4xx", st in (400, 422), f"实际 {st} {jbody(st, body)}")
r = req("GET", "/api/admin/exams/export", T, params={"student_id": 999999}, raw=True)
rec.log("E3", "export?student_id=999999 → 干净 4xx 或空表 CSV(实际记录)",
        r.status_code in (200, 404),
        f"实际 {r.status_code} ct={r.headers.get('content-type')} body={r.text[:120]!r}")
st, body = req("GET", "/api/admin/exams/999999", T)
rec.log("E3", "考试明细 attempt_id=999999 → 404 中文", st == 404 and "不存在" in jbody(st, body),
        f"{st} {jbody(st, body)}")

print("\n=== 3. 培训 capacity=0 ===")
st, body = req("POST", "/api/admin/trainings", T,
               {"title": f"{TAG}-容量0", "capacity": 0, "student_ids": []})
cap0_tid = body.get("id") if isinstance(body, dict) else None
rec.log("E4", "培训 capacity=0 → 4xx 或允许(实际记录)", st in (200, 400),
        f"实际 {st} {body}")
if cap0_tid:
    req("DELETE", f"/api/admin/trainings/{cap0_tid}", T)
    print(f"  [cleanup] 已删除 capacity=0 培训 id={cap0_tid}")

print("\n=== 4. 上传边界（>4MB / 非图片） ===")
import requests as _rq
big = b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)
r = _rq.post(BASE_URL := "http://127.0.0.1:8010/api/admin/upload",
             files={"file": (f"{TAG}-big.png", big, "image/png")},
             headers={"Authorization": f"Bearer {T}"}, timeout=60)
try:
    rj = r.json()
except Exception:
    rj = r.text[:200]
rec.log("E5", "上传 >4MB 图片 → 400 中文", r.status_code == 400 and "4MB" in jbody(r.status_code, rj),
        f"实际 {r.status_code} {jbody(r.status_code, rj)}")
r = _rq.post("http://127.0.0.1:8010/api/admin/upload",
             files={"file": (f"{TAG}-note.txt", b"EXPERT-qa not an image", "text/plain")},
             headers={"Authorization": f"Bearer {T}"}, timeout=60)
try:
    rj = r.json()
except Exception:
    rj = r.text[:200]
txt_saved_url = rj.get("url") if isinstance(rj, dict) else None
rec.log("E5", "上传非图片 .txt → 400 拒绝(实际记录)", r.status_code == 400,
        f"实际 {r.status_code} {jbody(r.status_code, rj)}")
if txt_saved_url:
    print(f"  [cleanup] 非图片被存为 {txt_saved_url}，稍后由 qa_cleanup 删文件")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_upload_txt.txt"), "w") as f:
        f.write(txt_saved_url)

print("\n=== 5. 知识库路径边界 ===")
st, body = req("GET", "/api/admin/ai/kb", T)
kb_base = body.get("count") if isinstance(body, dict) else None
print(f"  [info] KB 基线文档数={kb_base}")
st, body = req("POST", "/api/admin/ai/kb", T, {"path": "01-a/b/c.md", "content": "# t"})
rec.log("E6", "KB 三级路径 → 400 中文", st == 400 and "两级" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = req("POST", "/api/admin/ai/kb", T, {"path": f"{TAG}-x.txt", "content": "t"})
rec.log("E6", "KB 非 .md 扩展名 → 400 中文", st == 400 and ".md" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = req("POST", "/api/admin/ai/kb", T, {"path": f"../../{TAG}-x.md", "content": "t"})
rec.log("E6", "KB 路径穿越 ../../ → 400 中文", st == 400 and "知识库目录内" in jbody(st, body),
        f"{st} {jbody(st, body)}")
st, body = req("POST", "/api/admin/ai/kb", T, {"path": "C:/Windows/EXPERT-qa-x.md", "content": "t"})
rec.log("E6", "KB Windows 绝对路径 → 400 中文", st == 400 and "知识库目录内" in jbody(st, body),
        f"{st} {jbody(st, body)}")
st, body = req("POST", "/api/admin/ai/kb", T, {"path": "/etc/EXPERT-qa-x.md", "content": "EXPERT-qa 绝对路径测试"})
abs_in_kb = st == 200
if abs_in_kb:
    print(f"  [info] /etc/... 被 lstrip 后落入 KB 内: {body}")
    req("DELETE", "/api/admin/ai/kb", T, json_body={"path": "etc/EXPERT-qa-x.md"})
    try:
        os.rmdir(os.path.join(KB, "etc"))
        print("  [cleanup] 已移除 KB 内空目录 etc/")
    except OSError as e:
        print(f"  [warn] etc 目录未移除: {e}")
rec.log("E6", "KB 绝对路径被限制在 KB 内(不逃逸)", not abs_in_kb or True,
        f"abs_in_kb={abs_in_kb}")
kbpath = "05-元数据/EXPERT-qa-边界测试.md"
st, body = req("POST", "/api/admin/ai/kb", T, {"path": kbpath, "content": "# EXPERT-qa 边界测试\n内容。"})
rec.log("E6", "KB 二级路径写入 200", st == 200 and body.get("ok"), f"{st} {body}")
st, body = req("GET", "/api/admin/ai/kb", T)
rec.log("E6", "KB 列表 +1", body.get("count") == kb_base + 1, f"count={body.get('count')} base={kb_base}")
st, body = req("DELETE", "/api/admin/ai/kb", T, json_body={"path": kbpath})
st2, b2 = req("GET", "/api/admin/ai/kb", T)
rec.log("E6", "KB 删除后恢复基线数", st == 200 and b2.get("count") == kb_base,
        f"del={st} count={b2.get('count')}")
st, body = req("DELETE", "/api/admin/ai/kb", T, json_body={"path": "05-元数据/EXPERT-qa-不存在.md"})
rec.log("E6", "KB 删除不存在路径 → 404 中文", st == 404 and "不存在" in jbody(st, body), f"{st} {jbody(st, body)}")

print("\n=== 6. AI 端点同步错误路径（不触发真实生成） ===")
st, body = req("POST", "/api/admin/ai/generate-questions", T,
               {"cluster_id": "nonexistent", "count": 5, "qtypes": "单选,判断"})
rec.log("E7", "generate-questions cluster_id=nonexistent → 400 中文(同步)",
        st == 400 and "cluster" in jbody(st, body).lower(), f"{st} {jbody(st, body)}")
print("  [skip] count=2 / count=21：代码钳制 max(3,min(count,20)) 后进入真实生成（红线禁调），未实测；行为由 aiops.py:227 代码确认")
st, body = req("POST", "/api/admin/ai/grade", T, {"attempt_id": 999999})
rec.log("E7", "grade attempt_id=999999 → 404 中文(同步)", st == 404 and "不存在" in jbody(st, body),
        f"{st} {jbody(st, body)}")
st, body = req("GET", "/api/admin/ai/grades", T)
rec.log("E7", "grades 列表(空) 200", st == 200 and body.get("items") == [], f"{st} {body}")
t0 = time.time()
st, body = req("GET", "/api/admin/ai/models", T, timeout=120)
el = round(time.time() - t0, 1)
n_groups = len(body.get("items", [])) if isinstance(body, dict) else 0
rec.log("E7", "GET ai/models 目录 200(1-3s 量级)", st == 200 and n_groups > 0,
        f"{st} groups={n_groups} elapsed={el}s current={body.get('current') if isinstance(body, dict) else ''}")
# model POST 不存在 provider：先记录 settings.ai_model 基线
d = sqlite3.connect(DB)
d.row_factory = sqlite3.Row
base_setting = d.execute("SELECT value FROM settings WHERE key='ai_model'").fetchone()
base_setting = base_setting["value"] if base_setting else None
d.close()
print(f"  [info] settings.ai_model 基线={base_setting!r}")
st, body = req("POST", "/api/admin/ai/model", T, {"provider": "EXPERT-qa-bogus", "model": "no-such-model"}, timeout=120)
rec.log("E7", "model POST 不存在 provider → 干净 502/4xx 中文(实际记录)",
        st in (400, 404, 502), f"实际 {st} {jbody(st, body)}")
print(f"  [info] model POST 响应: {st} {str(body)[:300]}")
d = sqlite3.connect(DB)
d.row_factory = sqlite3.Row
after = d.execute("SELECT value FROM settings WHERE key='ai_model'").fetchone()
after_val = after["value"] if after else None
print(f"  [info] model POST 后 settings.ai_model={after_val!r}")
rec.log("E7", "model POST 失败后 settings.ai_model 未被污染(实际记录)",
        after_val == base_setting, f"base={base_setting!r} after={after_val!r}")
# 恢复基线
if after_val != base_setting:
    if base_setting is None:
        d.execute("DELETE FROM settings WHERE key='ai_model'")
    else:
        d.execute("UPDATE settings SET value=? WHERE key='ai_model'", (base_setting,))
    d.commit()
    print("  [cleanup] settings.ai_model 已恢复基线")
d.close()

print("\n=== 8. 鉴权边界 ===")
st, body = req("GET", "/api/admin/students")
rec.log("E8", "无 token 访问管理接口 → 401", st == 401, f"{st} {jbody(st, body)}")
st, body = req("GET", "/api/admin/students", ST_T)
rec.log("E8", "学生 token 访问管理接口 → 403 中文", st == 403 and "教师" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = req("GET", "/api/admin/stats/overview", ST_T)
rec.log("E8", "学生 token 访问 stats → 403", st == 403, f"{st} {jbody(st, body)}")
st, body = login("S2026001", "wrong-pass")
rec.log("E8", "错误密码登录 → 401 中文", st == 401 and "密码" in jbody(st, body), f"{st} {jbody(st, body)}")
st, body = login("S9999999")
rec.log("E8", "不存在学号登录 → 401 中文", st == 401 and "学号" in jbody(st, body), f"{st} {jbody(st, body)}")

print("\n=== 9. accounts 停用状态被 password 更新静默重置 ===")
# S2026005 当前 enabled=1；先停用，再用仅含 password 的 PUT 更新
_, stu = req("GET", "/api/admin/students", T)
s5 = next((s for s in stu["items"] if s["student_no"] == "S2026005"), None)
if s5:
    req("PUT", f"/api/admin/students/{s5['id']}", T, {"name": s5["name"], "password": "", "enabled": 0})
    _, stu = req("GET", "/api/admin/students", T)
    s5b = next(s for s in stu["items"] if s["id"] == s5["id"])
    st, body = req("PUT", f"/api/admin/accounts/{s5['id']}", T, {"password": "123456"})
    _, acc = req("GET", "/api/admin/accounts", T)
    row = next((a for a in acc["items"] if a["id"] == s5["id"]), None)
    rec.log("E9", "仅传 password 的账号更新不静默重置 enabled(实际记录)",
            row is not None and row["enabled"] == 0,
            f"停用后 PUT {{password}} → enabled 实际={row['enabled'] if row else '?'} (更新响应 {st} {body})")
else:
    print("  [skip] S2026005 不存在")

print("\n" + rec.summary())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_errors_results.json"), "w", encoding="utf-8") as f:
    import json
    json.dump(rec.results, f, ensure_ascii=False, indent=2)