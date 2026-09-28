# -*- coding: utf-8 -*-
"""管理后台 E2E（B 期）：教师 8 页 + 学生端公告条/轮播 DB 驱动回归。headless msedge。"""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
P = "\u2713"
F = "\u2717"
results = []

def check(name, ok, extra=""):
    results.append((name, ok))
    print(f"{P if ok else F} {name} {extra}")

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("dialog", lambda d: d.accept())

    def url():
        return pg.evaluate("location.href")

    import re
    def login(sno):
        pg.goto(BASE + "/login", wait_until="networkidle")
        pg.locator(".dh-btn").filter(has_text=sno).first.click()
        pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
        pg.wait_for_timeout(1500)
        return url()

    # ---------- T2026 教师 ----------
    u = login("T2026")
    check("教师登录直达 /admin", u.rstrip("/").endswith("/admin"), u)

    # 1 数据总览
    pg.wait_for_selector(".mcard", timeout=15000)
    check("总览·核心指标卡", pg.locator(".mcard").count() >= 5)
    check("总览·六簇掌握度条", pg.locator(".bar-row .bl").first.inner_text() in ("Morse评估", "Morse 评估") or "Morse" in pg.locator(".bar-row .bl").first.inner_text())
    check("总览·排行榜", "排行榜" in pg.content())
    check("总览·学时统计表", "学时统计" in pg.content())

    # 2 课程预告 & 轮播
    pg.goto(BASE + "/admin/content", wait_until="networkidle")
    pg.wait_for_selector(".atable", timeout=10000)
    check("内容页·轮播表 4 行", pg.locator(".atable").nth(1).locator("tbody tr").count() >= 4)
    # 通过 API 造一条公告，再验证列表出现（验证 CRUD + 学生端数据源同源）
    r = pg.evaluate("""async () => {
        const token = localStorage.getItem('falllearn_token')
        const res = await fetch('/api/admin/announcements', {method:'POST', headers:{'content-type':'application/json', authorization:'Bearer '+token},
          body: JSON.stringify({title:'E2E 公告 · 12 月 5 日应急演练', summary:'实训楼 203，14:00', pinned:1, enabled:1, start_date:'', end_date:''})})
        return {ok: res.ok, status: res.status}
    }""")
    check("内容页·公告创建(API)", r["ok"], str(r["status"]))
    pg.reload(wait_until="networkidle")
    check("内容页·公告列表出现", pg.get_by_text("E2E 公告 · 12 月 5 日应急演练").count() >= 1)

    # 3 考试管理
    pg.goto(BASE + "/admin/exams", wait_until="networkidle")
    pg.wait_for_selector(".atable", timeout=10000)
    check("考试页·标题", "考试管理" in pg.content())
    check("考试页·有记录或空态", pg.locator("tbody tr").count() >= 1)

    # 4 学生管理
    pg.goto(BASE + "/admin/students", wait_until="networkidle")
    pg.wait_for_selector(".atable", timeout=10000)
    nstu = pg.locator(".atable tbody tr").count()
    check("学生页·学生行 ≥3", nstu >= 3, str(nstu))

    # 5 账号管理
    pg.goto(BASE + "/admin/accounts", wait_until="networkidle")
    pg.wait_for_selector(".atable", timeout=10000)
    nacct = pg.locator(".atable tbody tr").count()
    check("账号页·行 ≥4（含教师）", nacct >= 4, str(nacct))
    check("账号页·当前账号标记", pg.get_by_text("我", exact=True).count() >= 1)

    # 6 培训管理
    pg.goto(BASE + "/admin/trainings", wait_until="networkidle")
    pg.wait_for_selector(".card", timeout=10000)
    check("培训页·有培训卡", "完成率" in pg.content() or "还没有培训" in pg.content())

    # 7 培训统计
    pg.goto(BASE + "/admin/stats", wait_until="networkidle")
    pg.wait_for_selector(".mcard", timeout=10000)
    check("统计页·总览卡", pg.locator(".mcard").count() >= 4)
    check("统计页·培训表", "负责教师" in pg.content())
    pg.locator(".pill", has_text="学生培训画像").click()
    pg.wait_for_timeout(400)
    check("统计页·学生画像 tab", "AI 问答" in pg.content())
    pg.locator(".pill", has_text="教师带训").click()
    pg.wait_for_timeout(400)
    check("统计页·教师 tab", "带训情况" in pg.content())

    # 8 AI 管理
    pg.goto(BASE + "/admin/ai", wait_until="networkidle")
    pg.wait_for_selector(".pill", timeout=10000)
    check("AI页·四个 tab", pg.locator(".pill").count() == 4)
    # 模型目录（DSH 实时探测，给 60s）
    try:
        pg.wait_for_selector(".mp", timeout=60000)
        nmodel = pg.locator(".mp").count()
        check("AI页·模型目录加载", nmodel >= 2, str(nmodel) + " 个模型")
    except Exception:
        check("AI页·模型目录加载", False, pg.locator(".card").first.inner_text()[:80])
    pg.locator(".pill", has_text="知识库").click()
    pg.wait_for_timeout(800)
    nkb = pg.locator(".kb-item").count()
    check("AI页·知识库列表 ≥20", nkb >= 20, str(nkb))
    pg.locator(".pill", has_text="AI 出题").click()
    pg.wait_for_timeout(400)
    check("AI页·出题表单", "知识簇" in pg.content())
    pg.locator(".pill", has_text="AI 判卷").click()
    pg.wait_for_timeout(400)
    # UX-7 修复后：无已交卷时显示空态提示（表单隐藏），有已交卷时显示表单——两者都算通过
    check("AI页·判卷表单/空态", "开始 AI 判卷" in pg.content() or "刷新卷单" in pg.content()
          or "暂无已交卷" in pg.content())

    # ---------- S2026001 学生：公告条 + 轮播回归 ----------
    pg.goto(BASE + "/login", wait_until="networkidle")
    pg.evaluate("localStorage.clear()")
    pg.reload(wait_until="networkidle")
    pg.locator(".dh-btn").filter(has_text="S2026001").first.click()
    pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
    pg.wait_for_timeout(2500)
    check("学生端·首页加载", pg.locator(".banner").count() >= 1)
    pg.wait_for_selector(".notice-strip", timeout=8000)
    nstrip = pg.locator(".notice-strip").count()
    check("学生端·公告条出现（DB 驱动）", nstrip == 1)
    check("学生端·公告条文案", "E2E 公告" in pg.locator(".notice-strip").inner_text())
    pg.locator(".notice-strip").click()
    pg.wait_for_timeout(500)
    check("学生端·公告弹窗", "课程预告" in pg.content())
    check("学生端·轮播 4 帧", pg.locator(".banner-dots i").count() >= 4)

    b.close()

ok = sum(1 for _, x in results if x)
print(f"\n===== 管理后台 E2E: {ok}/{len(results)} 通过 =====")
sys.exit(0 if ok == len(results) else 1)