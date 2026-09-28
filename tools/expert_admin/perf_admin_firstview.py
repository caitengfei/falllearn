# -*- coding: utf-8 -*-
"""perf 专家 · /admin 首屏到可见计时（headless msedge，3 次新 context）。
测量：navigation 时序（DOM/Load/响应头）+ 首个指标卡(.mcard)可见时刻 + stats/overview XHR 耗时
      + /admin 首访 JS 资源总字节。
产物：E:\\lilei\\platform\\docs\\expert-admin\\perf_admin_firstview.json + perf_admin_firstview.png
"""
import json
import os
import statistics
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\docs\expert-admin\perf_admin_firstview.json"
SHOT = r"E:\lilei\platform\docs\expert-admin\perf_admin_firstview.png"

POLL = """
async () => {
  const nav = performance.getEntriesByType('navigation')[0];
  const t0 = performance.now();
  let found = false, at = null;
  while (performance.now() - t0 < 20000) {
    if (document.querySelector('.mcard')) { at = performance.now(); found = true; break; }
    await new Promise(r => setTimeout(r, 10));
  }
  const res = performance.getEntriesByType('resource').map(e => ({
    name: e.name.split('/').slice(-1)[0] || e.name, url: e.name,
    size: e.transferSize, start: Math.round(e.startTime), dur: Math.round(e.duration)
  }));
  const xhr = res.filter(x => x.url.includes('/api/'));
  const jsBytes = res.filter(x => x.url.includes('/assets/') && x.url.endsWith('.js'))
                     .reduce((s, x) => s + x.size, 0);
  return {
    nav: {
      redirect: Math.round(nav.redirectEnd),
      dns: Math.round(nav.domainLookupEnd),
      connect: Math.round(nav.connectEnd),
      ttfb: Math.round(nav.responseStart),
      respEnd: Math.round(nav.responseEnd),
      domInteractive: Math.round(nav.domInteractive),
      domContentLoaded: Math.round(nav.domContentLoadedEventEnd),
      load: Math.round(nav.loadEventEnd),
    },
    firstCardMs: found ? Math.round(at) : null,
    firstCardFound: found,
    apiCalls: xhr,
    jsTransferBytes: jsBytes,
    jsCount: res.filter(x => x.url.includes('/assets/') && x.url.endsWith('.js')).length
  };
}
"""


def main():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"student_no": "T2026", "password": "123456"}, timeout=15)
    r.raise_for_status()
    body = r.json()
    token, user = body["token"], body["user"]

    from playwright.sync_api import sync_playwright
    runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for i in range(3):
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            # init_script 在任何页面脚本前执行：预置已登录 token，直接冷访 /admin（无 /login 预热缓存）
            user_js = json.dumps(user, ensure_ascii=False)
            ctx.add_init_script(
                f"localStorage.setItem('falllearn_token', {json.dumps(token)}); "
                f"localStorage.setItem('falllearn_user', {json.dumps(user_js)});")
            page = ctx.new_page()
            page.on("dialog", lambda d: d.accept())
            t0 = time.perf_counter()
            page.goto(f"{BASE}/admin", wait_until="domcontentloaded")
            data = page.evaluate(POLL)
            wall = round((time.perf_counter() - t0) * 1000)
            if i == 0:
                page.screenshot(path=SHOT, full_page=False)
            runs.append({"run": i + 1, "wall_after_dcl_ms": wall, **data})
            print(f"run{i+1}: firstCard={data['firstCardMs']}ms nav={data['nav']['domContentLoaded']}ms(DCL) "
                  f"load={data['nav']['load']}ms js={data['jsTransferBytes']}B x{data['jsCount']} "
                  f"api={[ (x['name'], x['dur']) for x in data['apiCalls'] ]}")
            ctx.close()
        browser.close()

    def mean(key):
        vals = [r[key] for r in runs if r.get(key) is not None]
        return round(statistics.mean(vals), 1) if vals else None

    summary = {
        "tag": "perf", "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": f"{BASE}/admin", "viewport": "1440x900", "channel": "msedge(headless)",
        "note": "firstCardMs=导航起点→首个指标卡(.mcard)出现（10ms 轮询）；3 次独立 context（无 HTTP 缓存共享）",
        "mean_firstCard_ms": mean("firstCardMs"),
        "mean_DCL_ms": round(statistics.mean([r['nav']['domContentLoaded'] for r in runs]), 1),
        "mean_load_ms": round(statistics.mean([r['nav']['load'] for r in runs]), 1),
        "mean_ttfb_ms": round(statistics.mean([r['nav']['ttfb'] for r in runs]), 1),
        "mean_js_bytes": round(statistics.mean([r['jsTransferBytes'] for r in runs])),
        "runs": runs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"saved -> {OUT}\nscreenshot -> {SHOT}")


if __name__ == "__main__":
    main()