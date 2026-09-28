# -*- coding: utf-8 -*-
"""内容专家(content) · 管理后台文案/信息质量黑盒 API 实测
- 只触发 4xx 错误路径（不跑真实 AI 生成/判卷、不点 reset-demo）
- 创建的数据一律带 EXPERT-content- 前缀，收尾删除并自查
"""
import io, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
import requests

BASE = "http://127.0.0.1:8010"
TAG = "EXPERT-content"
S = requests.Session()
OUT = {"errors": {}, "crud": {}, "cleanup": {}, "notes": []}

def j(r):
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:300]

def show(key, r):
    code, body = j(r)
    OUT["errors"][key] = {"status": code, "body": body}
    print(f"[{key}] {code}: {json.dumps(body, ensure_ascii=False)[:400]}")
    return code, body

# ---------- 登录 ----------
code, body = show("login_teacher", S.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "123456"}))
TOK = body["token"]
H = {"authorization": f"Bearer {TOK}"}
code, body = show("login_student", S.post(f"{BASE}/api/auth/login", json={"student_no": "S2026001", "password": "123456"}))
STOK = body["token"]
SH = {"authorization": f"Bearer {STOK}"}

# ---------- 鉴权错误文案 ----------
show("admin_no_token", S.get(f"{BASE}/api/admin/students"))
show("admin_student_token", S.get(f"{BASE}/api/admin/students", headers=SH))
show("login_bad_pwd", S.post(f"{BASE}/api/auth/login", json={"student_no": "T2026", "password": "x"}))
show("login_unknown_t", S.post(f"{BASE}/api/auth/login", json={"student_no": "T9999", "password": "123456"}))
show("learn_bad_token", S.get(f"{BASE}/api/auth/me", headers={"authorization": "Bearer garbage"}))

# ---------- 422 校验错误（前端 alert 会直接弹这些 detail） ----------
show("notice_422_empty", S.post(f"{BASE}/api/admin/announcements", headers=H, json={}))
show("banner_422_empty", S.post(f"{BASE}/api/admin/banners", headers=H, json={}))
show("student_422_empty", S.post(f"{BASE}/api/admin/students", headers=H, json={}))
show("training_422_empty", S.post(f"{BASE}/api/admin/trainings", headers=H, json={}))
show("kbwrite_422", S.post(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": ""}))

# ---------- 业务 4xx 文案 ----------
show("notice_whitespace_title", S.post(f"{BASE}/api/admin/announcements", headers=H, json={"title": "   ", "summary": "x"}))
# 上一条若 200 → 空白标题入库了（记录 id 供清理）
n = S.get(f"{BASE}/api/admin/announcements", headers=H).json()
ws_ids = [x["id"] for x in n["items"] if x["title"].strip() == ""]
OUT["crud"]["whitespace_notice_ids"] = ws_ids

show("student_dup_sno", S.post(f"{BASE}/api/admin/students", headers=H, json={"name": f"{TAG}-重号", "student_no": "S2026001"}))
show("account_dup_sno", S.post(f"{BASE}/api/admin/accounts", headers=H, json={"name": f"{TAG}-重号T", "student_no": "T2026"}))
show("account_bad_role", S.post(f"{BASE}/api/admin/accounts", headers=H, json={"name": f"{TAG}-坏角色", "student_no": "EXPC999", "role": "admin"}))
# 自停 / 自删
code, body = j(S.get(f"{BASE}/api/auth/me", headers=H))
me = body
show("account_self_disable", S.put(f"{BASE}/api/admin/accounts/{me['id']}", headers=H, json={"enabled": 0}))
show("account_self_delete", S.delete(f"{BASE}/api/admin/accounts/{me['id']}", headers=H))
show("exam_detail_404", S.get(f"{BASE}/api/admin/exams/999999", headers=H))
show("training_404", S.get(f"{BASE}/api/admin/trainings/999999", headers=H))

# ---------- 上传 ----------
# 1) 超 4MB
big = io.BytesIO(os.urandom(4 * 1024 * 1024 + 1024))
big.name = "big.png"
show("upload_too_big", S.post(f"{BASE}/api/admin/upload", headers=H, files={"file": big}))
# 2) 非图片扩展名（API 静默改 .png）
txt = io.BytesIO(b"hello not an image")
txt.name = f"{TAG}-test.txt"
code, body = show("upload_txt", S.post(f"{BASE}/api/admin/upload", headers=H, files={"file": txt}))
if code == 200:
    OUT["crud"]["txt_upload_url"] = body.get("url")
# 3) 正常小图（随后清理文件）
png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
png.name = f"{TAG}-ok.png"
code, body = show("upload_ok_png", S.post(f"{BASE}/api/admin/upload", headers=H, files={"file": png}))
if code == 200:
    OUT["crud"]["png_upload_url"] = body.get("url")

# ---------- KB 路径安全 / 覆盖语义 ----------
show("kb_traversal", S.post(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": "../../backend/app/main.py", "content": "x"}))
show("kb_too_deep", S.post(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": "05-元数据/a/b/c.md", "content": "x"}))
kb1 = f"{TAG}-kb-覆盖测试.md"
show("kb_write_new", S.post(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": kb1, "content": "# 第一版"}))
show("kb_write_same_path", S.post(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": kb1, "content": "# 第二版（覆盖）"}))
show("kb_delete_missing", S.delete(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": f"{TAG}-不存在.md"}))

# ---------- AI 端点：仅同步报错路径（禁止真实生成） ----------
show("ai_gen_bad_cluster", S.post(f"{BASE}/api/admin/ai/generate-questions", headers=H, json={"cluster_id": "bad", "count": 10}))
show("ai_grade_missing", S.post(f"{BASE}/api/admin/ai/grade", headers=H, json={"attempt_id": 999999}))
code, body = show("ai_models_get", S.get(f"{BASE}/api/admin/ai/models", headers=H, timeout=120))
if code == 200:
    OUT["crud"]["ai_model_current"] = body.get("current")
    OUT["crud"]["ai_model_groups"] = [g.get("id") for g in body.get("items", [])]
show("ai_grades_list", S.get(f"{BASE}/api/admin/ai/grades", headers=H))

# ---------- CSV 导出（表头/编码/枚举值文案） ----------
r = S.get(f"{BASE}/api/admin/exams/export", headers=H)
csv_head = r.content[:200]
OUT["crud"]["csv_status"] = r.status_code
OUT["crud"]["csv_bom"] = r.content[:3] == b"\xef\xbb\xbf"
OUT["crud"]["csv_head_text"] = csv_head.decode("utf-8-sig", "replace")[:200]
print(f"[csv] {r.status_code} bom={OUT['crud']['csv_bom']} head={OUT['crud']['csv_head_text']!r}")

# ---------- 学生端公开内容接口 ----------
show("pub_banners", S.get(f"{BASE}/api/content/banners"))
show("pub_notices", S.get(f"{BASE}/api/content/announcements"))
code, body = show("student_me", S.get(f"{BASE}/api/auth/me", headers=SH))
OUT["crud"]["s2026001_mastery"] = body.get("mastery")

# ---------- CRUD 生命周期（带前缀，随后清理） ----------
# 1) 课程预告
code, body = show("crud_notice_create", S.post(f"{BASE}/api/admin/announcements", headers=H, json={
    "title": f"{TAG}-课程预告", "summary": "EXPERT 测试摘要", "content": "EXPERT 正文",
    "start_date": "2026-09-01", "end_date": "2026-12-31", "pinned": 1, "enabled": 1}))
nid = body.get("id")
show("crud_notice_pub_visible", S.get(f"{BASE}/api/content/announcements"))
show("crud_notice_update", S.put(f"{BASE}/api/admin/announcements/{nid}", headers=H, json={
    "title": f"{TAG}-课程预告", "summary": "EXPERT 摘要2", "content": "", "start_date": "", "end_date": "", "pinned": 0, "enabled": 0}))
show("crud_notice_pub_after_disable", S.get(f"{BASE}/api/content/announcements"))
# 2) 轮播卡（link=/practice 观察学生端 CTA 映射）
code, body = show("crud_banner_create", S.post(f"{BASE}/api/admin/banners", headers=H, json={
    "title": f"{TAG}-轮播卡", "tag": "EXPERT", "sub": "测试副标题", "image": "", "link": "/practice", "sort": 99, "enabled": 1}))
bid = body.get("id")
show("crud_banner_pub", S.get(f"{BASE}/api/content/banners"))
# 3) 学生账号
code, body = show("crud_student_create", S.post(f"{BASE}/api/admin/students", headers=H, json={"name": f"{TAG}-新同学"}))
new_sno = body.get("student_no")
new_id = body.get("id")
OUT["crud"]["new_student"] = {"sno": new_sno, "id": new_id}
code, body = show("crud_new_student_login", S.post(f"{BASE}/api/auth/login", json={"student_no": new_sno, "password": "123456"}))
# 4) 培训（只勾自己创建的学生，避免污染演示学生报名数据）
code, body = show("crud_training_create", S.post(f"{BASE}/api/admin/trainings", headers=H, json={
    "title": f"{TAG}-培训", "batch": "EXPERT", "start_date": "2026-10-01", "end_date": "2026-10-07",
    "capacity": 5, "note": "EXPERT 测试", "student_ids": [new_id]}))
tid = body.get("id")
show("crud_training_setstatus", S.post(f"{BASE}/api/admin/trainings/{tid}/students/{new_id}/status", headers=H, json={"status": "done"}))
show("crud_training_list", S.get(f"{BASE}/api/admin/trainings", headers=H))
show("crud_stats_trainings", S.get(f"{BASE}/api/admin/stats/trainings", headers=H))

# ---------- 清理 ----------
def cleanup_del(key, r):
    code, body = show("clean_" + key, r)
    OUT["cleanup"][key] = code == 200
for i in ws_ids:
    cleanup_del(f"notice_ws_{i}", S.delete(f"{BASE}/api/admin/announcements/{i}", headers=H))
if nid: cleanup_del("notice", S.delete(f"{BASE}/api/admin/announcements/{nid}", headers=H))
if bid: cleanup_del("banner", S.delete(f"{BASE}/api/admin/banners/{bid}", headers=H))
if tid: cleanup_del("training", S.delete(f"{BASE}/api/admin/trainings/{tid}", headers=H))
if new_id: cleanup_del("student_account", S.delete(f"{BASE}/api/admin/accounts/{new_id}", headers=H))
show("clean_kb_own", S.delete(f"{BASE}/api/admin/ai/kb", headers=H, json={"path": kb1}))
for k in ("txt_upload_url", "png_upload_url"):
    url = OUT["crud"].get(k)
    if url:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend", "uploads", os.path.basename(url))
        if os.path.isfile(p):
            os.remove(p)
            OUT["cleanup"]["uploaded_file_" + k] = True
        else:
            OUT["cleanup"]["uploaded_file_" + k] = f"not found: {p}"

# ---------- 收尾自查 ----------
checks = {}
def contains_tag(items):
    return [x for x in items if TAG in json.dumps(x, ensure_ascii=False)]
n = S.get(f"{BASE}/api/admin/announcements", headers=H).json()
b = S.get(f"{BASE}/api/admin/banners", headers=H).json()
t = S.get(f"{BASE}/api/admin/trainings", headers=H).json()
a = S.get(f"{BASE}/api/admin/accounts", headers=H).json()
kb = S.get(f"{BASE}/api/admin/ai/kb", headers=H).json()
checks["announcements"] = [x["title"] for x in contains_tag(n["items"])]
checks["banners"] = [x["title"] for x in contains_tag(b["items"])]
checks["trainings"] = [x["title"] for x in contains_tag(t["items"])]
checks["accounts"] = [x["student_no"] for x in contains_tag(a["items"])]
checks["kb"] = [x["path"] for x in kb["items"] if TAG in x["path"]]
OUT["self_check"] = checks
print("\n=== SELF CHECK ===")
print(json.dumps(checks, ensure_ascii=False, indent=1))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_api_results.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("saved content_api_results.json")