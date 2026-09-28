# -*- coding: utf-8 -*-
"""内容专家(content) · 管理后台 + 学生端 DOM 文案采集（只读，不点删除/重置/真实AI生成）"""
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = {}

def grab(pg, key):
    t = pg.evaluate("document.body.innerText")
    OUT[key] = t
    print(f"===== {key} ({len(t)} chars) =====")
    print(t[:1800])
    print("...\n")

def nav(pg, url, wait_ms=1200):
    pg.goto(url, wait_until="domcontentloaded")
    for _ in range(40):
        if pg.evaluate("location.href") == url or url.rstrip("/") in pg.evaluate("location.href"):
            break
        pg.wait_for_timeout(100)
    pg.wait_for_timeout(wait_ms)

def fill_login(pg, sno):
    pg.goto(BASE + "/login", wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    pg.locator("input").nth(0).fill(sno)
    pg.locator("input[type=password]").fill("123456")
    pg.locator("button", has_text="登 录").click()
    for _ in range(60):
        if "/login" not in pg.evaluate("location.href"):
            break
        pg.wait_for_timeout(100)
    pg.wait_for_timeout(1200)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})

    # ---------- 登录页（未登录） ----------
    pg.goto(BASE + "/login", wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    grab(pg, "01_login")
    OUT["login_placeholders"] = pg.eval_on_selector_all("input", "els => els.map(e => e.placeholder)")
    OUT["login_demo_buttons"] = pg.eval_on_selector_all(".dh-btn", "els => els.map(e => e.innerText.trim().replace(/\\n/g,' '))")

    # ---------- 教师端 ----------
    fill_login(pg, "T2026")
    assert "/admin" in pg.evaluate("location.href"), pg.evaluate("location.href")
    OUT["teacher_landed"] = pg.evaluate("location.href")
    grab(pg, "02_admin_overview")

    nav(pg, BASE + "/admin/content"); grab(pg, "03_admin_content")
    # 新建预告弹窗
    pg.click(".card .more:has-text('新建预告')")
    pg.wait_for_timeout(400)
    OUT["notice_modal_fields"] = pg.eval_on_selector_all(".mask .field", "els => els.map(e => { const l=e.querySelector('label'); const i=e.querySelector('input,textarea'); return (l?l.innerText.trim():'') + ' || placeholder=' + (i? (i.placeholder||'(无)') : '(无输入框)') })")
    OUT["notice_modal_title"] = pg.locator(".mask .modal-h").first.inner_text()
    pg.click(".mask .modal-h .more"); pg.wait_for_timeout(300)
    # 新增轮播卡弹窗
    pg.click(".card .more:has-text('新增轮播卡')")
    pg.wait_for_timeout(400)
    OUT["banner_modal_fields"] = pg.eval_on_selector_all(".mask .field", "els => els.map(e => { const l=e.querySelector('label'); const i=e.querySelector('input,textarea'); return (l?l.innerText.trim():'') + ' || placeholder=' + (i? (i.placeholder||'(无)') : '(无输入框)') })")
    pg.click(".mask .modal-h .more"); pg.wait_for_timeout(300)

    nav(pg, BASE + "/admin/exams"); grab(pg, "04_admin_exams")
    nav(pg, BASE + "/admin/students"); grab(pg, "05_admin_students")
    pg.click("button:has-text('新增学生')"); pg.wait_for_timeout(400)
    OUT["student_modal_fields"] = pg.eval_on_selector_all(".mask .field", "els => els.map(e => { const l=e.querySelector('label'); const i=e.querySelector('input,textarea'); return (l?l.innerText.trim():'') + ' || placeholder=' + (i? (i.placeholder||'(无)') : '(无输入框)') })")
    pg.click(".mask .modal-h .more"); pg.wait_for_timeout(300)
    nav(pg, BASE + "/admin/accounts"); grab(pg, "06_admin_accounts")
    nav(pg, BASE + "/admin/trainings"); grab(pg, "07_admin_trainings")
    nav(pg, BASE + "/admin/stats"); grab(pg, "08_admin_stats")

    nav(pg, BASE + "/admin/ai"); pg.wait_for_timeout(500)
    grab(pg, "09_admin_ai_model")
    OUT["ai_model_desc"] = pg.locator(".card p").first.inner_text()
    OUT["ai_models_shown"] = pg.eval_on_selector_all(".model-pick .mp", "els => els.slice(0,12).map(e => e.innerText.trim().replace(/\\n/g,' | '))")
    OUT["ai_model_btn"] = pg.locator("button:has-text('应用到平台')").first.inner_text()
    OUT["ai_current_tag"] = pg.evaluate("(() => { const t=document.querySelector('.card-title .tag.green'); return t? t.innerText : null })()")
    # 知识库 tab
    pg.click(".pill:has-text('知识库')"); pg.wait_for_timeout(700)
    OUT["ai_kb_head"] = pg.locator(".card-title").first.inner_text()
    OUT["ai_kb_root_line"] = pg.locator(".card p").first.inner_text()
    OUT["ai_kb_filter_placeholder"] = pg.locator("input[placeholder]").first.get_attribute("placeholder")
    pg.click(".more:has-text('新增文档')"); pg.wait_for_timeout(300)
    OUT["ai_kb_new_default_path"] = pg.eval_on_selector_all(".mask input, .card input", "els => els.map(e => e.value)")
    OUT["ai_kb_new_placeholders"] = pg.eval_on_selector_all(".card input, .card textarea", "els => els.map(e => e.placeholder || '(无)')")
    # AI 出题 tab
    pg.click(".pill:has-text('AI 出题')"); pg.wait_for_timeout(400)
    OUT["ai_gen_labels"] = pg.eval_on_selector_all(".field", "els => els.map(e => { const l=e.querySelector('label'); const i=e.querySelector('input,select,textarea'); return (l?l.innerText.trim():'') + ' || ' + (i? (i.placeholder||'(select/无placeholder)') : '') })")
    OUT["ai_gen_flow_text"] = pg.locator("span:has-text('流程：')").first.inner_text()
    # AI 判卷 tab
    pg.click(".pill:has-text('AI 判卷')"); pg.wait_for_timeout(400)
    OUT["ai_grade_desc"] = pg.locator(".card p").first.inner_text()
    OUT["ai_grade_label"] = pg.locator("label:has-text('选择已交卷')").first.inner_text()
    OUT["ai_grade_options"] = pg.eval_on_selector_all("select option", "els => els.map(e => e.innerText).slice(0,5)")
    OUT["ai_grade_btn"] = pg.locator("button:has-text('开始 AI 判卷')").first.inner_text()

    # ---------- 学生端 ----------
    pg.evaluate("() => { localStorage.clear(); location.href='/login' }")
    pg.wait_for_timeout(1000)
    fill_login(pg, "S2026001")
    assert pg.evaluate("location.href") == BASE + "/", pg.evaluate("location.href")
    pg.wait_for_timeout(1500)
    grab(pg, "10_student_home")
    OUT["home_banner_slide1"] = pg.evaluate("(() => { const b=document.querySelector('.banner'); return b? b.innerText.trim().replace(/\\n/g,' | ') : null })()")
    OUT["home_notice_strip"] = pg.evaluate("(() => { const n=document.querySelector('.notice-strip'); return n? n.innerText.trim() : '(无公告条)' })()")
    OUT["home_icon_grid"] = pg.eval_on_selector_all(".icon-item .lbl", "els => els.map(e => e.innerText)")
    OUT["home_kcard_meta"] = pg.eval_on_selector_all(".kcard", "els => els.map(e => e.querySelector('.kname').innerText + ': ' + (e.querySelector('.kmeta')? e.querySelector('.kmeta').innerText.replace(/\\n/g,' ') : ''))")
    # 点第一张轮播的 CTA，观察跳转
    cta_text = pg.locator(".b-cta").first.inner_text()
    OUT["home_cta1_text"] = cta_text
    pg.locator(".b-cta").first.click(); pg.wait_for_timeout(800)
    OUT["home_cta1_landed"] = pg.evaluate("location.href")
    # 学习中心
    nav(pg, BASE + "/learn"); pg.wait_for_timeout(1500)
    grab(pg, "11_student_learn")
    OUT["learn_header"] = pg.locator(".chat-card .card-title").first.inner_text()
    OUT["learn_onlyweak_label"] = pg.locator(".onlyweak").first.inner_text()
    # 练习考试
    nav(pg, BASE + "/practice"); pg.wait_for_timeout(800)
    OUT["practice_menu"] = pg.eval_on_selector_all(".menu-item", "els => els.map(e => e.innerText.trim().replace(/\\n/g,' '))")
    OUT["practice_cards"] = pg.eval_on_selector_all(".rtitle", "els => els.map(e => e.innerText).slice(0,4)")
    # 我的
    nav(pg, BASE + "/mine"); pg.wait_for_timeout(800)
    OUT["mine_overview_stats"] = pg.eval_on_selector_all(".mine-grid .stat-item", "els => els.map(e => e.innerText.replace(/\\n/g,' ')).slice(0,8)")
    OUT["mine_titles"] = pg.eval_on_selector_all(".card-title", "els => els.map(e => e.innerText).slice(0,8)")

    b.close()

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_dom_results.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("saved content_dom_results.json")