# -*- coding: utf-8 -*-
"""UX 测试 3b：教师 T2026 → /admin（只看不重置）。精确等待，避免 .navtabs 假阳性。"""
import sys, os, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_admin_log.jsonl")

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

# 1) API 确认 T2026 角色
try:
    r = urllib.request.Request(BASE + "/api/auth/login", method="POST",
                               data=json.dumps({"student_no": "T2026", "password": "123456"}).encode(),
                               headers={"content-type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as resp:
        t = json.loads(resp.read().decode())
    log("api_t2026", role=t["user"]["role"], name=t["user"]["name"], student_no=t["user"]["student_no"])
except Exception as e:
    log("api_t2026", error=str(e)[:200])

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    console_msgs = []
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text.split("\n")[0]), print("CONSOLE", m.type, m.text[:180].replace("\n"," "), flush=True)) if m.type in ("error","warning") else None)
    p.on("dialog", lambda d: (print("DIALOG", d.type, d.message[:100], flush=True), d.dismiss()))  # 一律不 accept，确保绝不误触重置
    try:
        p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_selector(".login-card", timeout=30000)
        p.locator(".field input").nth(0).fill("T2026")
        p.locator(".field input").nth(1).fill("123456")
        p.locator(".login-body .btn").click()
        # 登录成功后跳转 /；用顶部用户名确认身份，而非 .navtabs
        p.wait_for_timeout(2500)
        uname = p.evaluate("() => { const e=document.querySelector('.uname'); return e? e.textContent : '' }")
        udept = p.evaluate("() => { const e=document.querySelector('.udept'); return e? e.textContent : '' }")
        urlnow = p.evaluate("location.pathname")
        log("teacher_login", url=urlnow, uname=uname, udept=udept)
        admin_link = p.locator(".navtabs a", has_text="管理看板")
        visible = admin_link.count() > 0
        log("teacher_nav", admin_link_visible=visible)
        if visible:
            admin_link.click()
        else:
            p.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_timeout(1500)
        # 等待学生表格或错误卡
        try:
            p.wait_for_selector("table tbody tr, .card.err", timeout=15000)
        except Exception:
            pass
        p.wait_for_timeout(600)
        p.screenshot(path=os.path.join(OUT, "admin.png"))
        urlnow2 = p.evaluate("location.pathname")
        rows = p.locator("table tbody tr").count()
        row1 = p.locator("table tbody tr").first.inner_text().replace("\n", " | ")[:160] if rows else ""
        errcard = p.locator(".card.err").inner_text().strip()[:120] if p.locator(".card.err").count() else ""
        weak = p.evaluate("""() => { const c=[...document.querySelectorAll('.card')].find(x=>x.textContent.includes('班级弱项')); return c ? c.innerText.slice(0,260).replace(/\\n+/g,' | ') : '' }""")
        reset_btn = p.locator("button", has_text="一键重置演示账号")
        log("admin_page", url=urlnow2, student_rows=rows, first_row=row1, err=errcard,
            weak_clusters=weak[:240], reset_btn_present=reset_btn.count() > 0,
            note="只读查看；重置按钮存在但未点击（dialog 一律 dismiss 双保险）")
        log("console_summary", count=len(console_msgs), msgs=json.dumps(list(dict.fromkeys(console_msgs))[:6], ensure_ascii=False)[:500])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-500:])
    finally:
        b.close()
print("DONE admin", flush=True)