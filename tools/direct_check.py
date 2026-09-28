# -*- coding: utf-8 -*-
"""直连通道端到端验收（2026-09-28，比赛链接部署前必跑）。

环境变量：
  FALLLEARN_BASE        默认 http://127.0.0.1:8010
  FALLLEARN_TEST_KEY    平台未配置直连时，用该 key 自动配置（必填场景之一）
  FALLLEARN_TEST_BASE   默认 https://api.deepseek.com
  FALLLEARN_TEST_MODEL  默认 deepseek-flash

场景：① 管理端直连配置/测试 ② 模糊提问→澄清卡→应答→四栏(来源+120提醒)
      ③ 明确提问→四栏 ④ 超范围提问 ⑤ 管理端 AI 出题（直连任务分支）
"""
import os
import sys
import time

import requests

BASE = os.environ.get("FALLLEARN_BASE", "http://127.0.0.1:8010")
S = requests.Session()
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"   [{str(detail)[:300]}]"))


def api(method, path, body=None, token=None, timeout=300):
    r = S.request(method, BASE + path, json=body,
                  headers={"authorization": f"Bearer {token}"} if token else {}, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = {"detail": r.text[:200]}
    return r.status_code, data


def login(sno, pwd):
    code, d = api("POST", "/api/auth/login", {"student_no": sno, "password": pwd})
    if code != 200:
        print(f"登录失败 {sno}: {code} {d}")
        sys.exit(2)
    return d["token"]


def poll(sid, log_id, token, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        code, d = api("GET", f"/api/learn/status?session_id={sid}&log_id={log_id}", token=token)
        if d.get("status") in ("done", "question", "failed"):
            return d
        time.sleep(2.5)
    return {"status": "timeout"}


def ask(q, token):
    code, d = api("POST", "/api/learn/ask", {"question": q}, token)
    if code != 200:
        check(f"ask({q[:12]})", False, f"{code} {d}")
        return None, None, None
    sid, log_id = d["session_id"], d["log_id"]
    return poll(sid, log_id, token), sid, log_id


def main():
    t_admin = login("T2026", "123456")
    # ① 直连配置（未配置则用 env key 自动配置）
    code, cfg = api("GET", "/api/admin/ai/direct", token=t_admin)
    key = os.environ.get("FALLLEARN_TEST_KEY", "")
    if code != 200 or not cfg.get("configured"):
        if not key:
            print("平台未配置直连且未提供 FALLLEARN_TEST_KEY，无法验收直连链路")
            sys.exit(2)
        code, d = api("POST", "/api/admin/ai/direct",
                      {"base_url": os.environ.get("FALLLEARN_TEST_BASE", "https://api.deepseek.com"),
                       "model": os.environ.get("FALLLEARN_TEST_MODEL", "deepseek-flash"),
                       "api_key": key}, token=t_admin)
        check("直连配置保存", code == 200, f"{code} {d}")
    else:
        print(f"沿用平台现有直连配置：{cfg.get('base_url')} / {cfg.get('model')}")
    code, d = api("POST", "/api/admin/ai/direct/test", {}, token=t_admin, timeout=120)
    check("直连通测（管理端测试按钮同链路）", code == 200 and d.get("ok"), f"{code} {d}")

    t_stu = login("S2026001", "123456")
    # ② 模糊提问 → 澄清卡 → 应答 → 四栏
    r, sid, log_id = ask("跌倒", t_stu)
    opts = (r.get("question") or {}).get("options") if r else []
    check("澄清卡（模糊提问「跌倒」，≥4 选项）", r is not None and r.get("status") == "question" and len(opts) >= 4,
          f"{str(r)[:200]}")
    ans = ""
    if r and r.get("status") == "question":
        code, d = api("POST", "/api/learn/answer", {"log_id": log_id, "option_index": 2}, t_stu)
        check("澄清卡应答（/answer）", code == 200 and d.get("ok"), f"{code} {d}")
        r2 = poll(sid, log_id, t_stu)
        # 兜底：模型若再次澄清，最多再应答 1 轮（正常情况 persona 已禁止重复澄清）
        extra = 0
        while r2.get("status") == "question" and extra < 1:
            extra += 1
            api("POST", "/api/learn/answer", {"log_id": log_id, "option_index": 0}, t_stu)
            r2 = poll(sid, log_id, t_stu)
        ans = r2.get("answer", "") if r2.get("status") == "done" else ""
        check("四栏回答（澄清后，未重复澄清）", r2.get("status") == "done" and extra == 0
              and all(m in ans for m in ("【岗】", "【课】", "【赛】", "【证】")),
              f"extra_rounds={extra} status={r2.get('status')} {str(r2)[:160]}")
    check("来源标注（（来源：…knowledge/…））", "（来源" in ans and "knowledge/" in ans, ans[:200])
    check("120 就医提醒（首答末尾）", "120" in ans, ans[-200:] if ans else "无答案")
    # ③ 明确提问 → 四栏
    r3, _s, _l = ask("大赛跌倒环节怎么扣分", t_stu)
    a3 = r3.get("answer", "") if r3 and r3.get("status") == "done" else ""
    check("明确提问四栏（含【赛】+来源）", r3 is not None and r3.get("status") == "done"
          and "【赛】" in a3 and "（来源" in a3, str(r3)[:200])
    # ④ 超范围提问
    r4, _s, _l = ask("老人噎食了怎么办", t_stu)
    a4 = r4.get("answer", "") if r4 and r4.get("status") == "done" else ""
    check("超范围提问友好拒答（只覆盖跌倒技能点）", "跌倒技能点" in a4 or "只覆盖" in a4,
          f"status={r4.get('status') if r4 else None} {a4[:200]}")
    # ⑤ 管理端 AI 出题（直连任务分支）
    code, d = api("POST", "/api/admin/ai/generate-questions",
                  {"cluster_id": "five", "count": 5, "qtypes": "单选,判断"}, t_admin, timeout=330)
    items = (d or {}).get("items") or []
    check("管理端 AI 出题（直连任务分支，≥3 题）", code == 200 and len(items) >= 3, f"{code} {str(d)[:200]}")

    n_pass = sum(1 for _n, ok in RESULTS if ok)
    print(f"\n===== direct_check: {n_pass}/{len(RESULTS)} PASS =====")
    sys.exit(0 if n_pass == len(RESULTS) else 1)


if __name__ == "__main__":
    main()