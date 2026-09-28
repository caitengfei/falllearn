# -*- coding: utf-8 -*-
"""决定性诊断：用页面内 PerformanceResourceTiming 精确定位 quiz/start 的
浏览器侧 send/receive 时间，并枚举所有资源条目找卡住(长耗时)的请求。"""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"

_t = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
_r = requests.post(BASE + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + _t["token"]}, timeout=30)
assert _r.ok
print("[preset] reset done", flush=True)

JS_PERF = """
() => {
  const t0 = performance.timeOrigin;
  const out = performance.getEntriesByType('resource')
    .map(e => ({
      name: e.name.replace('http://127.0.0.1:8010',''),
      start: +(e.startTime/1000).toFixed(2),
      dur: +(e.duration/1000).toFixed(2),
      resp: e.responseEnd ? +((e.responseEnd-e.startTime)/1000).toFixed(2) : -1
    }))
    .sort((a,b)=>a.start-b.start);
  return JSON.stringify(out);
}
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026002")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=15000)
    _btn = p.locator(".checkin-row .btn-sm")
    if _btn.is_enabled():
        _btn.click()

    # 学习
    p.locator(".navtabs a", has_text="学习中心").click()
    p.wait_for_selector(".chat-input textarea", timeout=10000)
    p.locator(".chat-input textarea").fill("老年人跌倒")
    p.locator(".chat-input .btn").click()
    t0 = time.time()
    while time.time() - t0 < 150:
        if p.locator(".qcard").count() > 0:
            p.locator(".qopt").first.click()
            print(f"[learn] qcard answered +{int(time.time()-t0)}s", flush=True)
            break
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body:
            print("[learn] direct fourcol", flush=True)
            break
        time.sleep(3)
    t1 = time.time()
    while time.time() - t1 < 600:
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body and "来源：" in body:
            break
        time.sleep(4)
    print(f"[learn] fourcol ok +{int(time.time()-t1)}s", flush=True)

    # 练习
    p.locator(".navtabs a", has_text="练习考试").click()
    p.wait_for_selector(".card .btn", timeout=10000)
    # 记录点击前的 perf 快照
    before = json.loads(p.evaluate(JS_PERF))
    p.locator(".card .btn", has_text="开始").first.click()
    print("[practice] clicked 开始", flush=True)
    t0 = time.time()
    nav_seen = False
    for i in range(40):
        time.sleep(1)
        # 每 2 秒抓一次 perf（点击后）
        if (i + 1) % 2 == 0:
            try:
                cur = json.loads(p.evaluate(JS_PERF))
                new = [e for e in cur if e not in before]
                stuck = [e for e in cur if e["dur"] > 3 and e["resp"] == -1]
                qs = [e for e in cur if "quiz/start" in e["name"]]
                if qs or stuck:
                    print(f"t={i+1}s quiz/start={qs} stuck={stuck}", flush=True)
            except Exception as e:
                print(f"t={i+1}s perf-err {e}", flush=True)
        if "/exam/" in p.url:
            nav_seen = True
            print(f"t={i+1}s NAV to {p.url}", flush=True)
            break
    print(f"[practice] nav_seen={nav_seen} final_url={p.url}", flush=True)
    # 最终完整 perf
    try:
        fin = json.loads(p.evaluate(JS_PERF))
        qs = [e for e in fin if "quiz" in e["name"] or "exam" in e["name"]]
        print("[final] quiz/exam resources:", qs, flush=True)
    except Exception as e:
        print("final perf err", e, flush=True)
    b.close()