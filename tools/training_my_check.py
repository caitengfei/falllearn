# -*- coding: utf-8 -*-
"""学生端「我的培训」闭环验收（本地或远程）。

覆盖：教师建培训并报名 → 学生端 /api/trainings/my 可见（label=进行中）→
教师标记完成 → 学生端 label=已完成 → 权限拦截（未登录 401 / 学生访问教师接口 403）→
删除培训后学生端不再出现 → 清理测试数据。

用法：python tools/training_my_check.py [BASE]
"""
import sys
import time

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
TEACHER = ("T2026", "123456")
STUDENT = ("S2026001", "123456")
fails = []
created_tid = None


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("  | " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        fails.append(name)


def login(no, pwd):
    r = requests.post(BASE + "/api/auth/login", json={"student_no": no, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {no} -> {r.status_code}"
    return {"Authorization": "Bearer " + r.json()["token"]}


def my_trainings(h):
    r = requests.get(BASE + "/api/trainings/my", headers=h, timeout=15)
    return r.status_code, (r.json().get("items", []) if r.status_code == 200 else [])


def main():
    global created_tid
    th = login(*TEACHER)
    sh = login(*STUDENT)

    # 学生 id
    r = requests.get(BASE + "/api/admin/students", headers=th, timeout=15)
    check("教师可读学生列表", r.status_code == 200, r.status_code)
    students = r.json().get("items", [])
    me = next((x for x in students if x.get("student_no") == STUDENT[0]), None)
    check("找到演示学生 " + STUDENT[0], bool(me))
    if not me:
        return

    code, before = my_trainings(sh)
    check("学生可读 我的培训（200）", code == 200, code)
    before_ids = {x["id"] for x in before}

    today = time.strftime("%Y-%m-%d")
    end = time.strftime("%Y-%m-%d", time.localtime(time.time() + 7 * 86400))
    r = requests.post(BASE + "/api/admin/trainings", headers=th, timeout=15, json={
        "title": "AUTO验收培训·请忽略", "batch": "AUTO", "start_date": today, "end_date": end,
        "capacity": 5, "note": "自动验收", "student_ids": [me["id"]],
    })
    check("教师建培训并报名（200）", r.status_code == 200, r.status_code)
    created_tid = r.json().get("id")
    check("返回培训 id", bool(created_tid), r.text[:120])

    code, after = my_trainings(sh)
    item = next((x for x in after if x["id"] == created_tid), None)
    check("学生端可见新培训", bool(item), [x["id"] for x in after])
    if item:
        check("状态标签=进行中", item["label"] == "进行中", item["label"])
        check("带训教师已带出", item.get("teacher") == "陈老师" or bool(item.get("teacher")), item.get("teacher"))
        check("批次/起止日期正确", item.get("batch") == "AUTO" and item.get("end_date") == end, item)

    # 教师标记完成 → 学生端同步
    r = requests.post(BASE + f"/api/admin/trainings/{created_tid}/students/{me['id']}/status",
                      headers=th, json={"status": "done"}, timeout=15)
    check("教师标记完成（200）", r.status_code == 200, r.status_code)
    code, after2 = my_trainings(sh)
    item2 = next((x for x in after2 if x["id"] == created_tid), None)
    check("学生端标签同步=已完成", bool(item2) and item2["label"] == "已完成", item2 and item2["label"])

    # 权限：未登录 401 / 学生调教师接口 403
    r = requests.get(BASE + "/api/trainings/my", timeout=15)
    check("未登录访问 我的培训 → 401", r.status_code == 401, r.status_code)
    r = requests.get(BASE + f"/api/admin/trainings", headers=sh, timeout=15)
    check("学生访问教师培训接口 → 403", r.status_code == 403, r.status_code)

    # 清理
    r = requests.delete(BASE + f"/api/admin/trainings/{created_tid}", headers=th, timeout=15)
    check("删除培训（200）", r.status_code == 200, r.status_code)
    created_tid = None
    code, after3 = my_trainings(sh)
    check("删除后学生端不再显示", not any(x["title"] == "AUTO验收培训·请忽略" for x in after3),
          [x["title"] for x in after3])
    check("学生原有培训记录未受影响", {x["id"] for x in after3} >= before_ids,
          f"before={before_ids} after={[x['id'] for x in after3]}")


if __name__ == "__main__":
    try:
        main()
    finally:
        if created_tid:
            try:
                th = login(*TEACHER)
                requests.delete(BASE + f"/api/admin/trainings/{created_tid}", headers=th, timeout=15)
                print("（异常退出：已清理测试培训）")
            except Exception as e:
                print("清理失败：", e)
        print("\n===== 我的培训闭环验收：失败 %d 项 =====" % len(fails))
        sys.exit(1 if fails else 0)
