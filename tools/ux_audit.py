# -*- coding: utf-8 -*-
"""UX / 兼容性 / 无障碍走查（只读）：多视口溢出、键盘可达性与焦点可见、打印样式、
触控目标尺寸、文本对比度（WCAG AA）、reduced-motion 降级、长列表规模。

用法：
    python tools/ux_audit.py [http://127.0.0.1:8010]
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
fails = []


def note(name, ok, extra=""):
    print(("  \u2713 " if ok else "  \u2717 ") + name + (" " + str(extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


def login(p, no="S2026001"):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)
    p.locator(".field input").nth(0).fill(no)
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    time.sleep(3)


VIEWPORTS = [(360, 780), (390, 844), (768, 1024), (1024, 768), (1440, 950), (1920, 1080)]
STUDENT_PAGES = ["/", "/learn", "/kb", "/practice", "/wrong", "/report", "/competition", "/mine"]

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 950})
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    login(p)

    print("=== A. 多视口横向溢出 ===", flush=True)
    for w, h in VIEWPORTS:
        p.set_viewport_size({"width": w, "height": h})
        bad = []
        for path in STUDENT_PAGES:
            p.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
            time.sleep(1.6)
            ov = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if ov > 0:
                bad.append(f"{path}({ov}px)")
        note(f"{w}×{h} 八个学生页无横向溢出", not bad, bad)

    print("=== B. 键盘可达性与焦点可见 ===", flush=True)
    # 用独立 context（p 已登录，访问 /login 会被守卫重定向到首页）
    kb_ctx = b.new_context(viewport={"width": 1440, "height": 950})
    pk = kb_ctx.new_page()
    pk.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.8)
    seq, focus_ok = [], True
    for _ in range(6):
        pk.keyboard.press("Tab")
        info = pk.evaluate("""() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const cs = getComputedStyle(el);
          return {tag: el.tagName, txt: (el.innerText || el.placeholder || '').trim().slice(0, 12),
                  outline: cs.outlineStyle + '/' + cs.outlineWidth, boxShadow: cs.boxShadow !== 'none'};
        }""")
        if info is None:
            continue
        seq.append(f"{info['tag']}:{info['txt']}")
        if info["outline"].startswith("none/0") and not info["boxShadow"]:
            focus_ok = False
    note("登录页 Tab 可聚焦多个元素", len(seq) >= 3, " → ".join(seq[:6]))
    note("焦点样式可见（outline 或 box-shadow）", focus_ok)

    # 键盘提交登录（独立页面、干净流程：等挂载 → 输入 → Enter → 等 URL 变化）
    #  注：不要在同一页面先做 Tab 走查，也不要注入 history hook——实测两者都会干扰该断言
    pk2 = kb_ctx.new_page()
    pk2.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    pk2.wait_for_selector(".dh-btn", timeout=20000)   # 等 Vue 真正挂载（表单提交处理器已绑定）
    time.sleep(1)
    pk2.locator(".field input").nth(0).fill("S2026001")
    pk2.locator(".field input").nth(1).fill("123456")
    pk2.locator(".field input").nth(1).press("Enter")
    try:
        pk2.wait_for_url(lambda u: "/login" not in u, timeout=12000)
        ok_enter = True
    except Exception:
        ok_enter = False
    note("回车可提交登录（form submit）", ok_enter, pk2.evaluate("location.pathname"))
    kb_ctx.close()

    print("=== C. 打印样式（导出 PDF 场景）===", flush=True)
    p.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    p.emulate_media(media="print")
    time.sleep(0.5)
    hides = p.evaluate("""() => {
      const sel = ['.topbar', '.sidenav', '.tabs', 'button'];
      const out = {};
      for (const s of sel) {
        const el = document.querySelector(s);
        out[s] = el ? getComputedStyle(el).display : 'absent';
      }
      return out;
    }""")
    p.emulate_media(media="screen")
    note("打印时导航隐藏", hides.get(".sidenav") in ("none", "absent"), hides)
    note("打印时按钮隐藏", hides.get("button") == "none", hides.get("button"))

    print("=== D. 触控目标尺寸（390 宽）===", flush=True)
    p.set_viewport_size({"width": 390, "height": 844})
    small_total, biggest = 0, []
    for path in ["/", "/wrong", "/practice", "/mine"]:
        p.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
        time.sleep(1.8)
        res = p.evaluate("""() => {
          const out = [];
          document.querySelectorAll('button,a.nav,.op,.btn,.tab').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width < 4 || r.height < 4) return;
            if (r.height < 32) out.push(((el.innerText || '').trim().slice(0, 10) || el.className) + ':' + Math.round(r.height));
          });
          return out;
        }""")
        small_total += len(res)
        if res:
            biggest.append(f"{path} → {res[:4]}")
    note("移动端可点元素高度 ≥32px（除图标按钮）", small_total <= 6, f"共 {small_total} 个偏小 {biggest[:2]}")

    print("=== E. 文本对比度（WCAG AA ≥ 4.5）===", flush=True)
    p.set_viewport_size({"width": 1440, "height": 950})
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    contrast = p.evaluate("""() => {
      const lum = (c) => { const m = c.map(v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
        return 0.2126*m[0] + 0.7152*m[1] + 0.0722*m[2]; };
      const parse = (s) => (s.match(/\\d+(\\.\\d+)?/g) || [0,0,0]).slice(0,3).map(Number);
      const out = [];
      document.querySelectorAll('body *').forEach(el => {
        if (!el.innerText || el.children.length) return;
        // 跳过：Banner 内（深色渐变/图片背景，脚本取不到真实底色）
        if (el.closest('.banner') || el.closest('.banner-deco')) return;
        const t = el.innerText.trim();
        if (t.length < 2 || t.length > 40) return;
        const cs = getComputedStyle(el);
        const fs = parseFloat(cs.fontSize);
        if (fs < 12) return;
        const big = fs >= 18.66 || (fs >= 14 && parseInt(cs.fontWeight) >= 700);   // WCAG 大字定义
        const fg = parse(cs.color);
        let bgEl = el, bg = [255,255,255];
        while (bgEl) { const c = getComputedStyle(bgEl).backgroundColor; const a = (c.match(/[\\d.]+/g)||[]); 
          if (a.length >= 3 && (a.length < 4 || parseFloat(a[3]) > 0.5)) { bg = a.slice(0,3).map(Number); break; } bgEl = bgEl.parentElement; }
        const L1 = lum(fg), L2 = lum(bg);
        const ratio = (Math.max(L1,L2) + 0.05) / (Math.min(L1,L2) + 0.05);
        out.push({t: t.slice(0,14), ratio: +ratio.toFixed(2), need: big ? 3.0 : 4.5});
      });
      return out;
    }""")
    # Python 侧过滤：emoji/图标类文本不属于正文（JS 里写 emoji 范围会与 Python 转义冲突）
    _EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u2190-\u21FF]")
    low = [f"{x['t']}={x['ratio']}/{x['need']}" for x in contrast
           if x["ratio"] < x["need"] and _EMOJI.sub("", x["t"]).strip(" ·、，。！？：%()（）")]
    note("未发现对比度低于 WCAG AA 的正文文本", not low, low[:5])

    print("=== F. reduced-motion 降级 ===", flush=True)
    ctx2 = b.new_context(viewport={"width": 1440, "height": 950}, reduced_motion="reduce")
    p2 = ctx2.new_page()
    p2.goto(BASE + "/login", wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)
    durs = p2.evaluate("""() => {
      const el = document.querySelector('.login-body .btn') || document.body;
      const cs = getComputedStyle(el);
      return [cs.transitionDuration, cs.animationDuration];
    }""")
    note("reduced-motion 下过渡时长被压缩", all(d in ("0s", "0ms", "0.01s") or float(d.replace('s','') or 0) <= 0.05 for d in durs), durs)
    ctx2.close()

    print("=== G. 长列表与页面规模 ===", flush=True)
    p.goto(BASE + "/kb", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    n_kb = p.evaluate("document.querySelectorAll('.kdoc,.kitem,li').length")
    note("知识库列表 DOM 规模可控（<400 节点）", n_kb < 400, f"{n_kb} 节点")
    p.set_viewport_size({"width": 1440, "height": 950})
    p.goto(BASE + "/mine", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    nodes = p.evaluate("document.querySelectorAll('body *').length")
    note("我的页 DOM 节点 < 1200", nodes < 1200, f"{nodes} 节点")

    note("全程无 JS 异常", not errs, str(errs[:2]))
    b.close()

print(f"\n===== UX/兼容性走查: 失败 {len(fails)} 项 → {BASE} =====")
print("FAILS:", fails if fails else "无")
sys.exit(1 if fails else 0)
