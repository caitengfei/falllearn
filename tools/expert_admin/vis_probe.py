# -*- coding: utf-8 -*-
"""vis 追加探针：390 溢出根因链 / switch 真实颜色 / 390 下其余表格页"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\docs\expert-admin"

CHAIN_JS = r"""
() => {
  const wide = [];
  for (const el of document.querySelectorAll('body *')) {
    const w = el.getBoundingClientRect().width;
    if (w > window.innerWidth + 1) {
      wide.push({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 60),
        w: Math.round(w * 10) / 10, x: Math.round(el.getBoundingClientRect().x) });
    }
  }
  const q = (s) => { const el = document.querySelector(s); if (!el) return null;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return { w: Math.round(r.width), x: Math.round(r.x), d: cs.display, fd: cs.flexDirection, pos: cs.position, ow: el.scrollWidth }; };
  return { innerW: window.innerWidth, docW: document.documentElement.scrollWidth,
    app: q('#app'), topbar: q('.topbar'), wrap: q('.admin-wrap'), side: q('.admin-side'),
    main: q('.admin-main'), page: q('.page'), cards: [...document.querySelectorAll('.card')].map(c => ({ w: Math.round(c.getBoundingClientRect().width), sw: c.scrollWidth })),
    tables: [...document.querySelectorAll('.atable')].map(t => ({ w: Math.round(t.getBoundingClientRect().width), sw: t.scrollWidth })),
    wide: wide.slice(0, 12) };
}
"""

SWITCH_JS = r"""
() => [...document.querySelectorAll('.switch')].slice(0, 6).map(s => {
  const cs = getComputedStyle(s); const r = s.getBoundingClientRect();
  return { cls: s.className, on: s.classList.contains('on'), bg: cs.backgroundColor,
    x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
})
"""

def main():
    r = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10)
    token = r.json()["token"]
    me = requests.get(BASE + "/api/auth/me", headers={"authorization": f"Bearer {token}"}).json()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="domcontentloaded")
        page.evaluate("t => localStorage.setItem('falllearn_token', t)", token)
        page.evaluate("u => localStorage.setItem('falllearn_user', JSON.stringify(u))", me)

        out = {}
        for name, path in [("content", "/admin/content"), ("students", "/admin/students"),
                           ("exams", "/admin/exams"), ("accounts", "/admin/accounts"),
                           ("trainings", "/admin/trainings"), ("stats", "/admin/stats"),
                           ("overview", "/admin")]:
            page.goto(BASE + path, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            out[name] = page.evaluate(CHAIN_JS)
            print(f"390/{name}: docW={out[name]['docW']} innerW={out[name]['innerW']} "
                  f"wrap={out[name]['wrap'] and out[name]['wrap']['w']} main={out[name]['main'] and out[name]['main']['w']} "
                  f"tables={[t['sw'] for t in out[name]['tables']]}")
            if out[name]["wide"]:
                print("   wide elements:", json.dumps(out[name]["wide"][:6], ensure_ascii=False))

        # switch 颜色（students 页 3 个 on + accounts 4 个）
        for name, path in [("students", "/admin/students"), ("accounts", "/admin/accounts"), ("content", "/admin/content")]:
            page.goto(BASE + path, wait_until="domcontentloaded")
            page.wait_for_timeout(500)
            out["switch_" + name] = page.evaluate(SWITCH_JS)
            print(f"switch {name}:", json.dumps(out["switch_" + name], ensure_ascii=False))
            # 截一个 switch 局部放大（students 第一个）
            if name == "students":
                sw = page.locator(".switch").first
                sw.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                box = sw.bounding_box()
                if box:
                    page.screenshot(path=OUT + r"\vis-switch-zoom-390.png",
                                    clip={"x": max(0, box["x"] - 30), "y": max(0, box["y"] - 20),
                                          "width": 130, "height": 70})
                    print("switch zoom saved")
        ctx.close()

        # 1440 下也截一张 switch 放大（内容页启用列）
        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
        p2 = ctx2.new_page()
        p2.goto(BASE + "/login", wait_until="domcontentloaded")
        p2.evaluate("t => localStorage.setItem('falllearn_token', t)", token)
        p2.evaluate("u => localStorage.setItem('falllearn_user', JSON.stringify(u))", me)
        p2.goto(BASE + "/admin/content", wait_until="domcontentloaded")
        p2.wait_for_timeout(600)
        out["switch_content_1440"] = p2.evaluate(SWITCH_JS)
        print("switch content 1440:", json.dumps(out["switch_content_1440"], ensure_ascii=False))
        sw = p2.locator(".switch").first
        sw.scroll_into_view_if_needed()
        p2.wait_for_timeout(200)
        box = sw.bounding_box()
        if box:
            p2.screenshot(path=OUT + r"\vis-switch-zoom-1440.png",
                          clip={"x": max(0, box["x"] - 30), "y": max(0, box["y"] - 20),
                                "width": 130, "height": 70})
        ctx2.close()
        browser.close()

    with open(OUT + r"\vis-probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("probe saved")


if __name__ == "__main__":
    main()