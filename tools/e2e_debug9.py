# -*- coding: utf-8 -*-
"""页面内 fetch 埋点：精确记录 quiz/start 的 header/完成时间（页面时钟），
区分『网络层卡』 vs『JS 层卡』。"""
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

INJECT = """
window.__fl = [];
const __of = window.fetch;
window.fetch = function(...a) {
  const t0 = performance.now();
  const p = __of.apply(this, a);
  p.then(r => {
    window.__fl.push({url: String(a[0]).replace('http://127.0.0.1:8010','').slice(-45), head: +(performance.now()-t0).toFixed(0)});
    try { r.clone().text().then(() => { const e = window.__fl[window.__fl.length-1]; e.body = +(performance.now()-t0).toFixed(0); }); } catch(e){}
  }).catch(e => window.__fl.push({url: String(a[0]).slice(-45), ERR: String(e)}));
  return p;
};
window.__clk = 0;
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

    p.locator(".navtabs a", has_text="学习中心").click()
    p.wait_for_selector(".chat-input textarea", timeout=10000)
    p.locator(".chat-input textarea").fill("老年人跌倒")
    p.locator(".chat-input .btn").click()
    t0 = time.time()
    while time.time() - t0 < 150:
        if p.locator(".qcard").count() > 0:
            p.locator(".qopt").first.click()
            print(f"[learn] qcard +{int(time.time()-t0)}s", flush=True)
            break
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body:
            print("[learn] direct", flush=True)
            break
        time.sleep(3)
    t1 = time.time()
    while time.time() - t1 < 600:
        body = p.inner_text("body")
        if "【岗】" in body and "【证】" in body and "来源：" in body:
            break
        time.sleep(4)
    print(f"[learn] fourcol +{int(time.time()-t1)}s", flush=True)

    p.locator(".navtabs a", has_text="练习考试").click()
    p.wait_for_selector(".card .btn", timeout=10000)
    p.evaluate(INJECT)
    print("[practice] fetch hook installed", flush=True)
    p.locator(".card .btn", has_text="开始").first.click()
    t0 = time.time()
    for i in range(30):
        time.sleep(1)
        try:
            fl = p.evaluate("window.__fl")
            qs = [e for e in fl if "quiz/start" in e.get("url", "")]
            url = p.url
            if qs or "/exam/" in url:
                print(f"t={i+1}s url={url} quizLog={qs} last3={fl[-3:]}", flush=True)
            else:
                print(f"t={i+1}s url={url} last={fl[-1] if fl else None}", flush=True)
            if "/exam/" in url:
                break
        except Exception as e:
            print(f"t={i+1} eval-err {e}", flush=True)
    print(f"[end] url={p.url}", flush=True)
    b.close()