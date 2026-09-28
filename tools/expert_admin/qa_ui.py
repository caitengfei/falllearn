# -*- coding: utf-8 -*-
"""QA 专家 · UI 抽查（Playwright headless Edge）：
- /admin 各页渲染
- 考试页学生筛选是否真正过滤列表（api.js 未传 student_id 的 UI 层验证）
- 得分颜色静态 style 三元表达式是否生效
- AI 判卷下拉是否自动加载已交卷
截图存 docs/expert-admin/shots/
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
SHOT_DIR = r"E:\lilei\platform\docs\expert-admin\shots"
os.makedirs(SHOT_DIR, exist_ok=True)

results = []


def log(name, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    return ok


def shot(page, name):
    p = os.path.join(SHOT_DIR, name)
    page.screenshot(path=p, full_page=True)
    print(f"  [shot] {p}", flush=True)
    return p


api_reqs = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.accept())
    pg.on("request", lambda r: api_reqs.append(r.url) if "/api/admin/" in r.url else None)

    # ---------- 登录 ----------
    pg.goto(BASE + "/login", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(800)
    pg.locator("input[placeholder*='S2026001']").first.fill("T2026")
    pg.locator("input[type='password']").first.fill("123456")
    pg.locator("button:has-text('登 录')").first.click()
    pg.wait_for_timeout(2500)
    href = pg.evaluate("location.href")
    log("UI-登录", href.rstrip("/").endswith("/admin"), f"登录后 location={href} (教师默认进 /admin)")

    # ---------- 数据总览 ----------
    pg.wait_for_selector(".mgrid.c6", timeout=15000)
    n_cards = pg.locator(".mgrid.c6 > .mcard").count()
    log("UI-总览", n_cards == 6, f"指标卡数量={n_cards}（预期 6）")
    n_trend = pg.locator(".chart-bars .cb").count()
    log("UI-总览", n_trend == 7, f"7 日趋势条形数={n_trend}")
    n_hours = pg.locator(".card:has-text('学时统计') tbody tr").count()
    log("UI-总览", n_hours >= 4, f"学时统计表行数={n_hours}（含 E2E 学生）")
    reset_btn = pg.locator("button:has-text('演示数据重置')").count()
    log("UI-总览", reset_btn == 1, f"演示数据重置按钮存在={reset_btn}（不点击）")
    shot(pg, "qa_1_overview.png")

    # ---------- 业务管理 ----------
    pg.goto(BASE + "/admin/content", wait_until="domcontentloaded")
    pg.wait_for_selector(".card:has-text('主界面图片轮播') tbody tr", timeout=15000)
    n_banner_rows = pg.locator(".card:has-text('主界面图片轮播') tbody tr").count()
    log("UI-内容", n_banner_rows == 4, f"轮播行数={n_banner_rows}（4 张种子卡，未动）")
    n_notice_empty = pg.locator(".card:has-text('课程预告') tbody tr:has-text('暂无预告')").count()
    log("UI-内容", n_notice_empty == 1, f"预告空态提示={n_notice_empty}（基线 0 公告）")
    shot(pg, "qa_2_content.png")

    # ---------- 考试管理 ----------
    pg.goto(BASE + "/admin/exams", wait_until="domcontentloaded")
    pg.wait_for_selector("table.atable tbody tr", timeout=15000)
    n_before = pg.locator("table.atable tbody tr:has-text('逐题明细')").count()
    log("UI-考试", n_before == 1, f"已交卷行数={n_before}（E2E 1 份）")
    # 得分颜色（静态 style 三元）
    score_b = pg.locator("table.atable tbody b.num").first
    score_color = score_b.evaluate("el => getComputedStyle(el).color")
    score_txt = score_b.inner_text()
    # score=30 < 60 → 若三元生效应为 var(--primary)（红色 #e4393c 系）
    log("UI-考试", score_color in ("rgb(228, 57, 60)", "rgb(239, 68, 68)"),
        f"得分 {score_txt} 颜色={score_color}（score<60 预期红色 var(--primary)=#e4393c）")
    # 逐题明细弹窗
    pg.locator("button:has-text('逐题明细')").first.click()
    pg.wait_for_timeout(1200)
    n_detail = pg.evaluate(
        "() => document.querySelectorAll('.mask .modal > div[style*=\"border-bottom\"]').length")
    log("UI-考试", n_detail == 10, f"明细弹窗题目数={n_detail}（预期 10）")
    shot(pg, "qa_3_exam_detail.png")
    pg.locator(".mask .more:has-text('✕')").first.click()
    pg.wait_for_timeout(500)
    # 学生筛选（bug 验证）：选择张小明（S2026001，无交卷）
    api_reqs.clear()
    pg.locator(".card select").first.select_option("1")  # S2026001 的 user id=1
    pg.wait_for_timeout(2000)
    n_after = pg.locator("table.atable tbody tr:has-text('逐题明细')").count()
    exam_reqs = [u for u in api_reqs if "/api/admin/exams" in u and "export" not in u]
    log("UI-考试", n_after == 0,
        f"选学生筛选=张小明后列表行数={n_after}（预期 0；实际未过滤说明 student_id 未随请求发送）")
    print(f"  [info] 筛选触发的请求: {exam_reqs}")
    log("UI-考试", not any("student_id" in u for u in exam_reqs),
        f"筛选请求不含 student_id 参数（bug 实锤）: {exam_reqs}")
    shot(pg, "qa_4_exam_filter_bug.png")

    # ---------- AI 判卷下拉自动加载 ----------
    pg.goto(BASE + "/admin/ai", wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    pg.locator(".pill:has-text('AI 判卷')").first.click()
    pg.wait_for_timeout(800)
    n_opts_before = pg.locator(".card:has-text('选择已交卷') select option").count()
    log("UI-AI", n_opts_before == 1,
        f"判卷下拉初始选项数={n_opts_before}（仅占位项=未自动加载已交卷，需手动点刷新）")
    pg.locator("button:has-text('刷新卷单')").first.click()
    pg.wait_for_timeout(1500)
    n_opts_after = pg.locator(".card:has-text('选择已交卷') select option").count()
    log("UI-AI", n_opts_after == 2, f"刷新后选项数={n_opts_after}（占位+E2E 1 份）")
    shot(pg, "qa_5_ai_grade_tab.png")
    # 模型 tab（onMounted 已加载）
    pg.locator(".pill:has-text('模型选择')").first.click()
    pg.wait_for_timeout(1500)
    n_mp = pg.locator(".model-pick .mp").count()
    model_err = pg.locator(".card:has-text('获取模型目录失败')").count()
    log("UI-AI", n_mp > 0 and model_err == 0, f"模型卡片数={n_mp} 错误卡={model_err}")
    shot(pg, "qa_6_ai_model_tab.png")

    # ---------- 学生管理 ----------
    pg.goto(BASE + "/admin/students", wait_until="domcontentloaded")
    pg.wait_for_selector("table.atable tbody tr", timeout=15000)
    n_stu = pg.locator("table.atable tbody tr").count()
    has_e2e = pg.locator("table.atable tr:has-text('S2026004')").count()
    n_blocks = pg.locator("table.atable tr:has-text('S2026001') [title*='Morse']").count()
    log("UI-学生", n_stu == 5 and has_e2e == 1, f"学生行数={n_stu}（3 种子+2 EXPERT），S2026004 存在={has_e2e}")
    log("UI-学生", n_blocks == 1, f"六簇色块带 title 提示（Morse 块）={n_blocks}")
    shot(pg, "qa_7_students.png")

    # ---------- 培训管理 ----------
    pg.goto(BASE + "/admin/trainings", wait_until="domcontentloaded")
    pg.wait_for_selector(f".card:has-text('EXPERT-qa-UI截图培训')", timeout=15000)
    card = pg.locator(".card:has-text('EXPERT-qa-UI截图培训')").first
    enroll_n = card.locator("div:has-text('报名')").first
    txt = card.inner_text()
    ok_rate = ("报名" in txt and "完成" in txt and "33.3%" in txt)
    log("UI-培训", ok_rate, f"培训卡统计(报名3/完成1/33.3%): {'OK' if ok_rate else txt[:200]}")
    shot(pg, "qa_8_trainings.png")

    # ---------- 统计 ----------
    pg.goto(BASE + "/admin/stats", wait_until="domcontentloaded")
    pg.wait_for_selector("table.atable tbody tr", timeout=15000)
    n_pills = pg.locator(".pills .pill").count()
    n_t_rows = pg.locator("table.atable tbody tr").count()
    log("UI-统计", n_pills == 3 and n_t_rows >= 3, f"tab 数={n_pills}，培训情况行数={n_t_rows}")
    pg.locator(".pill:has-text('教师带训')").first.click()
    pg.wait_for_timeout(600)
    teach = pg.evaluate(
        "() => { const tr = [...document.querySelectorAll('table.atable tbody tr')]"
        ".find(t => t.innerText.includes('陈老师'));"
        " return tr ? [...tr.querySelectorAll('td')].map(td => td.innerText.trim()) : null; }")
    log("UI-统计", bool(teach) and teach[1] == "3",
        f"教师带训行 tds={teach}（培训期数应=3：2 基线+1 EXPERT）")
    shot(pg, "qa_9_stats.png")

    # ---------- 账号 ----------
    pg.goto(BASE + "/admin/accounts", wait_until="domcontentloaded")
    pg.wait_for_selector("table.atable tbody tr", timeout=15000)
    n_acc = pg.locator("table.atable tbody tr").count()
    self_tag = pg.locator("tr:has-text('T2026') .tag:has-text('我')").count()
    log("UI-账号", n_acc == 6 and self_tag == 1, f"账号行数={n_acc}（4 种子+2 EXPERT），T2026 有「我」标记={self_tag}")
    shot(pg, "qa_10_accounts.png")

    browser.close()

print("\nTOTAL=", len(results), "FAIL=", sum(1 for r in results if not r["ok"]))
import json
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_ui_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)