# -*- coding: utf-8 -*-
"""探针：抓取 Learn /exam 页面的完整 console 错误栈 + 检查 minified 源码定位"""
import sys, os, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"

# 1) 下载 minified chunk 查看错误位置源码
for chunk, pos in [("Learn-49Uy6TsU.js", 3454), ("ExamTake-DY9KDM66.js", 4660)]:
    try:
        url = BASE + "/assets/" + chunk
        js = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", "replace")
        a, b = max(0, pos - 260), min(len(js), pos + 260)
        print("=== %s @%d ===" % (chunk, pos), flush=True)
        print(js[a:b], flush=True)
        print("total len", len(js), flush=True)
    except Exception as e:
        print("chunk fetch fail", chunk, e, flush=True)
    print(flush=True)

# 2) 浏览器里抓完整 console 错误
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    errs = []
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.locator(".field input").nth(0).fill("S2026001")
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=20000)

    p.goto(BASE + "/learn", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_timeout(4000)
    print("=== /learn body 前600字 ===", flush=True)
    print(p.evaluate("document.body.innerText")[:600], flush=True)
    # 学习历史条数 & 是否有 qcard
    print("learn msgs:", p.evaluate("document.querySelectorAll('.msg').length"), flush=True)
    print("learn flow empty?", p.evaluate("!document.querySelector('.chat-flow .msg')"), flush=True)

    p.goto(BASE + "/exam/99999", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_timeout(2500)
    print("=== /exam/99999 body 全文 ===", flush=True)
    print(repr(p.evaluate("document.body.innerText")), flush=True)

    print("=== 完整 console 错误 ===", flush=True)
    for i, e in enumerate(errs):
        print("--- error %d ---" % i, flush=True)
        print(e, flush=True)
    b.close()
print("DONE probe", flush=True)