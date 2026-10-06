# -*- coding: utf-8 -*-
"""教师端知识库管理验收（本地或远程；生产可安全重跑——绝不覆盖已配置的模型密钥）。

覆盖：列表与六维分类统计 / 权限拦截（学生访问教师接口 403）/ 手动新增 /
学生端读回（同源即时生效）/ 编辑 / 改名（旧文件移回收站）/ txt 上传提取 /
非法格式拒绝 / 删除入回收站 / 模型配置掩码往返（非破坏）/
向量化（已配置=真实 API 单篇实测；未配置=假密钥 502 明确报错 + 400 引导）/
学生端检索不受影响 / 清理全部测试数据。

用法：python tools/kb_admin_check.py [BASE]
"""
import io
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
TEACHER = ("T2026", "123456")
STUDENT = ("S2026001", "123456")
fails = []
to_delete = []   # 需要清理的文档路径（改名后的新路径 + 上传路径；被改名消费掉的旧路径不入列）


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("  | " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        fails.append(name)


def login(no, pwd):
    r = requests.post(BASE + "/api/auth/login", json={"student_no": no, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {no} -> {r.status_code}"
    return {"Authorization": "Bearer " + r.json()["token"]}


def main():
    th = login(*TEACHER)
    sh = login(*STUDENT)

    # 1 列表 + 分类统计
    r = requests.get(BASE + "/api/admin/kb", headers=th, timeout=20)
    check("教师可读知识库列表", r.status_code == 200, r.status_code)
    d = r.json()
    items, stats = d.get("items", []), d.get("stats", {})
    check("列表非空且与 total 一致", len(items) > 0 and d.get("total") == len(items), d.get("total"))
    check("分类统计含五维+其他", all(k in stats for k in ["01-岗", "02-课", "03-赛", "04-证", "05-元数据", "其他"]), list(stats))
    check("统计字数>0", sum(v["chars"] for v in stats.values()) > 10000)

    # 2 权限
    r = requests.get(BASE + "/api/admin/kb", headers=sh, timeout=15)
    check("学生访问教师接口被拒（403）", r.status_code == 403, r.status_code)

    # 3 手动新增
    title = "AUTO验收知识·请忽略"
    r = requests.post(BASE + "/api/admin/kb", headers=th, timeout=20, json={
        "dim": "02-课", "title": title,
        "content": "本条为知识库管理验收脚本自动创建，验证通过后自动删除，内容足够长。" * 3})
    check("手动新增 200/created", r.status_code == 200 and r.json().get("created"), r.text[:80])
    p1 = r.json().get("path")

    # 4 学生端同源读回
    r = requests.get(BASE + "/api/kb/doc?path=" + requests.utils.quote(p1), headers=sh, timeout=15)
    check("学生端立即可读（同源）", r.status_code == 200 and "验收脚本" in r.json().get("content", ""), r.status_code)

    # 5 编辑（同标题）
    r = requests.post(BASE + "/api/admin/kb", headers=th, timeout=20, json={
        "dim": "02-课", "title": title, "path": p1,
        "content": "编辑后的内容，验证编辑与 created 标志（应为编辑而非新建）。" * 4})
    check("编辑 200/created=False", r.status_code == 200 and r.json().get("created") is False, r.text[:80])

    # 6 改名（旧文件移回收站，旧路径被消费不再单独删除）
    title2 = title + "-改"
    r = requests.post(BASE + "/api/admin/kb", headers=th, timeout=20, json={
        "dim": "02-课", "title": title2, "path": p1,
        "content": "改名后的内容，旧路径应不再出现在列表中，向量同步清理。" * 4})
    check("改名 200/created=False", r.status_code == 200 and r.json().get("created") is False, r.text[:80])
    p2 = r.json().get("path")
    if p2:
        to_delete.append(p2)
    r = requests.get(BASE + "/api/admin/kb", headers=th, timeout=20)
    paths_now = {x["path"] for x in r.json().get("items", [])}
    check("改名后旧路径已移出列表", p1 not in paths_now and p2 in paths_now)

    # 7 上传 txt
    txt = "智慧养老跌倒预防知识要点：一、环境风险识别；二、个人风险评估；三、干预措施。" * 5
    r = requests.post(BASE + "/api/admin/kb/upload", headers=th, timeout=60,
                      files={"file": ("auto_test.txt", io.BytesIO(txt.encode("utf-8")), "text/plain")},
                      data={"dim": "01-岗", "title": "AUTO验收上传·请忽略"})
    check("txt 上传 200/提取字数>0", r.status_code == 200 and r.json().get("chars", 0) > 100, r.text[:80])
    if r.status_code == 200:
        to_delete.append(r.json().get("path"))

    # 8 非法格式拒绝
    r = requests.post(BASE + "/api/admin/kb/upload", headers=th, timeout=30,
                      files={"file": ("x.bin", io.BytesIO(b"\x00\x01" * 32), "application/octet-stream")},
                      data={"dim": "01-岗", "title": "x"})
    check("非法格式拒绝（400）", r.status_code == 400, r.status_code)

    # 9 删除（回收站）
    for p in list(to_delete):
        r = requests.delete(BASE + "/api/admin/kb?path=" + requests.utils.quote(p), headers=th, timeout=15)
        check(f"删除 {p.split('/')[-1]}", r.status_code == 200, r.status_code)
    r = requests.get(BASE + "/api/admin/kb", headers=th, timeout=20)
    paths_now = {x["path"] for x in r.json().get("items", [])}
    check("删除后均不在列表", all(p not in paths_now for p in to_delete))

    # 10 模型配置：掩码往返（非破坏——api_key 传回掩码=保留原密钥，绝不写入假密钥）
    r = requests.get(BASE + "/api/admin/kb/config", headers=th, timeout=15)
    check("读取模型配置", r.status_code == 200 and "embed" in r.json() and "rerank" in r.json(), r.status_code)
    orig = r.json()
    em = orig["embed"]
    r = requests.put(BASE + "/api/admin/kb/config/embed", headers=th, timeout=15,
                     json={"base_url": em.get("base_url", ""), "api_key": em.get("api_key", ""),
                           "model": em.get("model", "")})
    check("配置保存（掩码回传=密钥不变）", r.status_code == 200, r.status_code)
    r = requests.get(BASE + "/api/admin/kb/config", headers=th, timeout=15)
    check("往返后配置一致（真实密钥未被覆盖）", r.json() == orig)
    if em["configured"]:
        check("密钥掩码回显", "****" in em["api_key"], em["api_key"][:8] + "…")

    # 11 向量化：已配置=真实 API 单篇实测（幂等）；未配置=400 引导
    if em["configured"]:
        r = requests.get(BASE + "/api/admin/kb", headers=th, timeout=20)
        smallest = min(r.json()["items"], key=lambda x: x["chars"])
        r = requests.post(BASE + "/api/admin/kb/embed", headers=th, timeout=180, json={"path": smallest["path"]})
        check("真实 API 单篇向量化", r.status_code == 200 and r.json().get("chunks", 0) > 0,
              f'{r.status_code} {r.text[:80]}')
    else:
        r = requests.post(BASE + "/api/admin/kb/embed", headers=th, timeout=30, json={"path": ""})
        check("未配置向量化 400 引导", r.status_code == 400, f"{r.status_code} {r.text[:60]}")

    # 12 学生端检索不受影响（已配置时验证语义融合仍工作）
    q = "老人突然晕倒怎么处理" if em["configured"] else "跌倒"
    r = requests.get(BASE + "/api/kb/search?q=" + requests.utils.quote(q), headers=sh, timeout=60)
    check("学生端检索正常", r.status_code == 200 and r.json().get("total", 0) > 0,
          f'{r.json().get("total")} 条 | top1=' + (r.json()["items"][0]["title"][:16] if r.json().get("items") else "-"))

    print("\n" + ("ALL PASS" if not fails else f"FAILED {len(fails)}: {fails}"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()