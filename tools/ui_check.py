# -*- coding: utf-8 -*-
"""界面与交互优化验收（P3 前端）：一键体验登录 / 答案朗读·复制 / 错题打印 /
知识库高亮与转义 / 错误态可见 / 无 JS 异常。

用法（本地）：
    D:\\python123\\python.exe E:\\lilei\\platform\\tools\\ui_check.py
"""
import sys
import time

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
fails = []
total = 0


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def check(name, cond, extra=""):
    global total
    total += 1
    if cond:
        log(f"  \u2713 {name} {extra}")
    else:
        log(f"  \u2717 {name} {extra}")
        fails.append(name)


with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    js_errors = []
    p.on("pageerror", lambda e: js_errors.append(str(e)))

    # 1) 登录页：一键体验直接进入（无需再点登录）
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)  # 等 Vue 挂载完成
    p.locator(".dh-btn").first.click()
    try:
        p.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        ok_jump = True
    except Exception:
        ok_jump = False
    check("一键体验直接登录进入首页", ok_jump, p.url)
    check("顶栏用户已加载", p.locator(".userchip .uname").count() == 1)

    # 2) 学习中心：答案朗读 / 复制按钮（多模态 + 可用性）
    p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.5)
    ops = p.locator(".msg-ops .op")
    n_ops = ops.count()
    check("AI 答案带操作条（朗读/复制）", n_ops >= 2, f"{n_ops} 个按钮")
    txt = p.inner_text("body")
    check("操作条含「朗读」", "朗读" in txt, "")
    check("操作条含「复制」", "复制" in txt, "")

    # 3) 错题本：打印按钮存在；错误条不误报
    p.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    check("错题本有打印/导出按钮", p.locator("button:has-text('打印')").count() >= 1)
    check("错题本无加载失败误报", "加载失败" not in p.inner_text("body"))
    # 正确答案字段（x.answer）应能显示
    check("错题本显示正确答案", p.locator("text=正确答案").count() >= 1)

    # 4) 知识库：检索高亮（esc 后 mark 仍生效）+ 无 HTML 注入元素
    p.goto(BASE + "/kb", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    p.fill(".ksearch", "Morse")
    p.keyboard.press("Enter")
    time.sleep(2.5)
    check("检索结果有 <mark> 高亮", p.locator(".ksnip mark").count() >= 1, f"{p.locator('.ksnip mark').count()} 处")
    check("检索片段无注入元素（img/script）",
          p.evaluate("document.querySelectorAll('.ksnip img,.ksnip script').length") == 0)

    # 5) 移动端 390：首页与错题本无横向溢出 + 导航可滑动
    pm = b.new_page(viewport={"width": 390, "height": 844})
    pm.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    ov = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("移动端首页无横向溢出", ov <= 0, f"overflow={ov}")
    pm.goto(BASE + "/wrong", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    ov2 = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("移动端错题本无横向溢出", ov2 <= 0, f"overflow={ov2}")

    check("全程无 JS 异常", not js_errors, str(js_errors[:3]))
    b.close()

print("\n===== 界面优化验收: %d 项检查，失败 %d =====" % (total, len(fails)))
print("FAILS:", fails if fails else "无")
sys.exit(1 if fails else 0)
