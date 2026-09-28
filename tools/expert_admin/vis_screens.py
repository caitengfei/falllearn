# -*- coding: utf-8 -*-
"""视觉专家(TAG=vis)：管理后台截图矩阵 + 布局溢出/设计一致性度量。

- 1440x900 × 8 页；1024x768 × 3 页(overview/content/ai)；390x844 × 3 页(overview/content/ai)
- 每张图记录 documentElement.scrollWidth vs innerWidth、卡片撑破、侧栏形态、mgrid 列数、
  条形图柱高、六簇条颜色、tag 调色板、switch 两态、logo-mark 一致性
- 附加：AI 页 4 tab 截图；学生页/内容页弹窗(.mask/.modal)实测（只打开不提交）
- 只读：不点击「演示数据重置」，不调用 AI 生成/判卷，不创建任何数据
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\docs\expert-admin"
TAG = "vis"

PAGES = [
    ("overview", "/admin"),
    ("content", "/admin/content"),
    ("exams", "/admin/exams"),
    ("students", "/admin/students"),
    ("accounts", "/admin/accounts"),
    ("trainings", "/admin/trainings"),
    ("stats", "/admin/stats"),
    ("ai", "/admin/ai"),
]
MATRIX = [
    (1440, 900, [p[0] for p in PAGES]),
    (1024, 768, ["overview", "content", "ai"]),
    (390, 844, ["overview", "content", "ai"]),
]

METRIC_JS = r"""
() => {
  const inner = [window.innerWidth, window.innerHeight];
  const doc = document.documentElement;
  const out = {
    inner, docScrollW: doc.scrollWidth, docScrollH: doc.scrollHeight,
    pageOverflow: doc.scrollWidth > inner[0],
    cards: [], adminSide: null, topbar: null, mgrids: [], chart: null,
    clusterBars: [], qtypeBars: [], switches: { on: 0, off: 0 },
    tags: [], clusterBlocks: [], logoMarks: [], fonts: {},
    tables: [], bodyBg: getComputedStyle(document.body).backgroundColor
  };
  for (const c of document.querySelectorAll('.card'))
    out.cards.push({ sw: c.scrollWidth, cw: c.clientWidth, broken: c.scrollWidth > c.clientWidth + 1 });
  const s = document.querySelector('.admin-side');
  if (s) {
    const cs = getComputedStyle(s);
    out.adminSide = { w: s.clientWidth, h: s.clientHeight, display: cs.display,
      dir: cs.flexDirection, wrap: cs.flexWrap, bg: cs.backgroundColor, pos: cs.position, radius: cs.borderRadius };
  }
  const tb0 = document.querySelector('.topbar');
  if (tb0) out.topbar = { bg: getComputedStyle(tb0).backgroundColor, h: tb0.clientHeight };
  for (const m of document.querySelectorAll('.mgrid')) out.mgrids.push(getComputedStyle(m).gridTemplateColumns);
  const bars = [...document.querySelectorAll('.chart-bars .cb')];
  if (bars.length) out.chart = {
    n: bars.length, chartH: document.querySelector('.chart-bars').clientHeight,
    items: bars.map(cb => {
      const col = cb.querySelector('.col');
      return { h: Math.round(col.getBoundingClientRect().height * 10) / 10,
               cv: (cb.querySelector('.cv') || {}).textContent,
               cl: (cb.querySelector('.cl') || {}).textContent };
    })
  };
  for (const r of document.querySelectorAll('.bar-row')) {
    const i = r.querySelector('.bt i');
    if (!i) continue;
    const label = (r.querySelector('.bl') || {}).textContent || '(inline)';
    const rec = { label, w: i.style.width, bg: getComputedStyle(i).backgroundColor, bv: (r.querySelector('.bv') || {}).textContent };
    if (label.includes('单选') || label.includes('判断') || label.includes('多选')) out.qtypeBars.push(rec);
    else out.clusterBars.push(rec);
  }
  for (const sw of document.querySelectorAll('.switch')) sw.classList.contains('on') ? out.switches.on++ : out.switches.off++;
  for (const t of [...document.querySelectorAll('.tag')].slice(0, 10))
    out.tags.push({ text: t.textContent.trim().slice(0, 16), cls: (t.className.match(/tag\s+\S+/) || [''])[0].replace('tag ', ''),
      bg: getComputedStyle(t).backgroundColor, fg: getComputedStyle(t).color });
  for (const b of document.querySelectorAll('.atable td [title]'))
    if (b.style.width === '14px') out.clusterBlocks.push({ title: b.getAttribute('title'), bg: b.style.backgroundColor });
  for (const lm of document.querySelectorAll('.logo-mark')) {
    const cs = getComputedStyle(lm);
    out.logoMarks.push({ w: lm.clientWidth, h: lm.clientHeight, fs: cs.fontSize,
      grad: cs.backgroundImage.replace(/\s+/g, ' ').slice(0, 80), radius: cs.borderRadius });
  }
  const fs = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).fontSize : null; };
  out.fonts = { body: getComputedStyle(document.body).fontSize, atable: fs('.atable'), atableTh: fs('.atable th'),
    mv: fs('.mcard .mv'), mk: fs('.mcard .mk'), cardTitle: fs('.card-title'), pill: fs('.pill') };
  for (const t of document.querySelectorAll('.atable')) {
    out.tables.push({ theadCols: t.querySelectorAll('thead th').length, rows: t.querySelectorAll('tbody tr').length,
      tw: t.scrollWidth, containerW: t.parentElement.clientWidth, twBroken: t.scrollWidth > t.parentElement.clientWidth + 1 });
  }
  return out;
}
"""


def login():
    r = requests.post(BASE + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def get_tok():
    return requests


def snapshot(token):
    h = {"authorization": f"Bearer {token}"}
    snap = {}
    for name, url in [
        ("overview", "/api/admin/stats/overview"),
        ("banners", "/api/admin/banners"),
        ("announcements", "/api/admin/announcements"),
        ("students", "/api/admin/students"),
        ("accounts", "/api/admin/accounts"),
        ("trainings", "/api/admin/trainings"),
        ("exams", "/api/admin/exams?status="),
        ("kb", "/api/admin/ai/kb"),
    ]:
        try:
            r = requests.get(BASE + url, headers=h, timeout=30)
            snap[name] = r.json()
        except Exception as e:
            snap[name] = {"error": str(e)}
    return snap


def wait_page(page, name):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as e:
        print(f"  [warn] {name}: networkidle 未达: {e}")
    if name == "ai":
        try:
            page.wait_for_selector(".model-pick .mp", timeout=25000)
        except Exception as e:
            print(f"  [warn] ai: 模型目录未加载 .model-pick .mp: {e}")
    else:
        try:
            page.wait_for_selector(".page", timeout=10000)
        except Exception as e:
            print(f"  [warn] {name}: .page 未出现: {e}")
    page.wait_for_timeout(700)


def main():
    os.makedirs(OUT, exist_ok=True)
    token = login()
    print("login ok")
    me = requests.get(BASE + "/api/auth/me", headers={"authorization": f"Bearer {token}"}, timeout=10).json()
    print("me:", me.get("student_no"), me.get("name"))

    before = snapshot(token)
    with open(os.path.join(OUT, f"{TAG}-baseline-snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(before, f, ensure_ascii=False, indent=1)
    n_banners = len(before.get("banners", {}).get("items", []))
    n_notices = len(before.get("announcements", {}).get("items", []))
    n_train = len(before.get("trainings", {}).get("items", []))
    print(f"baseline: banners={n_banners} notices={n_notices} trainings={n_train} kb={len(before.get('kb', {}).get('items', []))}")

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for W, H, names in MATRIX:
            ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
            page = ctx.new_page()
            # 预置登录态
            page.goto(BASE + "/login", wait_until="domcontentloaded")
            page.evaluate("t => localStorage.setItem('falllearn_token', t)", token)
            page.evaluate("u => localStorage.setItem('falllearn_user', JSON.stringify(u))", me)
            for name in names:
                path = dict(PAGES)[name]
                try:
                    page.goto(BASE + path, wait_until="domcontentloaded")
                except Exception as e:
                    print(f"  [warn] goto {path}: {e}")
                wait_page(page, name)
                fn = os.path.join(OUT, f"vis-{name}-{W}.png")
                page.screenshot(path=fn, full_page=True)
                m = page.evaluate(METRIC_JS)
                m["screenshot"] = os.path.basename(fn)
                m["url"] = page.evaluate("location.href")
                results[f"{W}/{name}"] = m
                print(f"[{W}x{H}] {name}: overflow={m['pageOverflow']} docW={m['docScrollW']} innerW={m['inner'][0]} "
                      f"cards_broken={sum(1 for c in m['cards'] if c['broken'])} tables_broken={sum(1 for t in m['tables'] if t['twBroken'])}")

            if W == 1440:
                # ---- AI 页其余 3 tab ----
                for tab_id, label, shot in [
                    ("kb", "📚 知识库", "vis-ai-kb-1440.png"),
                    ("gen", "✍️ AI 出题", "vis-ai-gen-1440.png"),
                    ("grade", "⚖️ AI 判卷", "vis-ai-grade-1440.png"),
                ]:
                    try:
                        page.goto(BASE + "/admin/ai", wait_until="domcontentloaded")
                        page.wait_for_selector(".model-pick .mp", timeout=25000)
                        page.locator(f".pill:has-text('{label}')").click()
                        page.wait_for_timeout(900)
                        page.screenshot(path=os.path.join(OUT, shot), full_page=True)
                        m = page.evaluate(METRIC_JS)
                        m["screenshot"] = shot
                        results[f"1440/ai-{tab_id}"] = m
                        print(f"[1440] ai-{tab_id}: overflow={m['pageOverflow']}")
                    except Exception as e:
                        print(f"  [warn] ai tab {tab_id}: {e}")

                # ---- 弹窗实测（学生页 新增学生；内容页 编辑首张轮播）只打开不提交 ----
                try:
                    page.goto(BASE + "/admin/students", wait_until="domcontentloaded")
                    wait_page(page, "students")
                    page.locator("button:has-text('＋ 新增学生')").click()
                    page.wait_for_timeout(500)
                    m = page.evaluate("""
                      () => {
                        const mask = document.querySelector('.mask');
                        const modal = document.querySelector('.modal');
                        if (!mask) return { mask: false };
                        const mc = getComputedStyle(mask);
                        const mr = mask.getBoundingClientRect();
                        const mdc = modal ? getComputedStyle(modal) : null;
                        const dr = modal ? modal.getBoundingClientRect() : null;
                        return {
                          mask: true,
                          maskPos: mc.position, maskDisplay: mc.display, maskBg: mc.backgroundColor,
                          maskZ: mc.zIndex, maskRect: [mr.x, mr.y, mr.width, mr.height].map(v => Math.round(v)),
                          modalBg: mdc ? mdc.backgroundColor : null, modalRadius: mdc ? mdc.borderRadius : null,
                          modalShadow: mdc ? mdc.boxShadow.slice(0, 40) : null,
                          modalRect: dr ? [dr.x, dr.y, dr.width, dr.height].map(v => Math.round(v)) : null,
                          modalCentered: dr ? Math.abs(dr.x + dr.width / 2 - window.innerWidth / 2) < 20 : null,
                          inner: [window.innerWidth, window.innerHeight]
                        };
                      }
                    """)
                    page.screenshot(path=os.path.join(OUT, "vis-students-modal-1440.png"), full_page=True)
                    results["1440/students-modal"] = m
                    print("[1440] students modal:", json.dumps(m, ensure_ascii=False))
                    # 关闭弹窗（✕）
                    try:
                        page.locator(".mask .more").last.click()
                        page.wait_for_timeout(300)
                    except Exception as e:
                        print("  [warn] close modal:", e)
                except Exception as e:
                    print(f"  [warn] students modal: {e}")
                try:
                    page.goto(BASE + "/admin/content", wait_until="domcontentloaded")
                    wait_page(page, "content")
                    page.locator(".atable tr:has-text('老年人跌倒') .op button:has-text('编辑')").click()
                    page.wait_for_timeout(500)
                    page.screenshot(path=os.path.join(OUT, "vis-content-modal-1440.png"), full_page=True)
                    results["1440/content-modal"] = page.evaluate(
                        "() => { const m = document.querySelector('.modal'); return m ? getComputedStyle(m).backgroundColor : null; }")
                    print("[1440] content modal bg:", results["1440/content-modal"])
                    try:
                        page.locator(".mask .more").last.click()
                        page.wait_for_timeout(300)
                    except Exception as e:
                        print("  [warn] close content modal:", e)
                except Exception as e:
                    print(f"  [warn] content modal: {e}")
            ctx.close()
        browser.close()

    after = snapshot(token)
    with open(os.path.join(OUT, f"{TAG}-after-snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(after, f, ensure_ascii=False, indent=1)
    changed = {k: (before.get(k) != after.get(k)) for k in before}
    print("snapshot changed keys:", {k: v for k, v in changed.items() if v} or "无")

    with open(os.path.join(OUT, f"{TAG}-metrics.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("metrics saved ->", os.path.join(OUT, f"{TAG}-metrics.json"))
    print("DONE")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"elapsed {time.time() - t0:.0f}s")