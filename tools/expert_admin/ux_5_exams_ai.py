# -*- coding: utf-8 -*-
"""UX-5: /admin/exams (empty state, CSV export) + /admin/ai (4 tabs, grade empty, error path)."""
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
token = login_api()
login(page)
report = {"dialogs": []}
try:
    # ---------- exams page ----------
    page.goto(BASE + "/admin/exams", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    empty = page.eval_on_selector(".card .atable", "t => {const tr = t.querySelector('tbody tr'); return tr ? tr.textContent.trim() : null}")
    report["exams_empty_state"] = empty
    report["exams_count_label"] = page.eval_on_selector(".page", "e => e.textContent.match(/\\d+ 条记录[^·]*/)[0]")
    shot(page, "ux-exams-empty.png")

    # CSV export: frontend does location.href = /api/admin/exams/export (no auth header possible on navigation!)
    page.click("button:has-text('导出 CSV')")
    page.wait_for_timeout(2500)
    after_url = page.evaluate("location.href")
    body = page.evaluate("document.body ? document.body.innerText.slice(0, 300) : '(no body)'")
    is_json_page = after_url.endswith("/api/admin/exams/export")
    report["csv_export_browser"] = {"url_after_click": after_url, "rendered_body": body,
                                    "navigated_to_api": is_json_page}
    if is_json_page:
        shot(page, "ux-exams-export-401.png")
        page.goto(BASE + "/admin/exams", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
    # authenticated API-level export (control)
    import requests
    r = requests.get(BASE + "/api/admin/exams/export", headers={"authorization": "Bearer " + token}, timeout=20)
    csv_path = os.path.join(DOCS, "ux-export-exams-api.csv")
    with open(csv_path, "wb") as f:
        f.write(r.content)
    report["csv_export_api"] = {"status": r.status_code, "content_disp": r.headers.get("content-disposition"),
                                "content": r.content.decode("utf-8-sig", "replace")[:200],
                                "rows": len(r.content.decode("utf-8-sig", "replace").strip().splitlines()) - 1}

    # status pills exist?
    report["status_pills"] = page.eval_on_selector_all(".pill", "els => els.map(e => e.textContent.trim())")

    # ---------- ai page ----------
    page.goto(BASE + "/admin/ai", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    shot(page, "ux-ai-model-loading-or-ready.png")
    report["ai_model_loading_text_visible"] = bool(page.query_selector("text=正在探测模型目录"))
    # wait up to 10s for model cards
    for _ in range(20):
        if page.query_selector(".model-pick .mp"):
            break
        page.wait_for_timeout(500)
    report["ai_model_cards"] = page.eval_on_selector_all(".model-pick .mp", "els => els.map(e => e.querySelector('.mn') ? e.querySelector('.mn').textContent.trim() : e.textContent.trim()).slice(0, 12)")
    report["ai_model_current_tag"] = (page.eval_on_selector(".card-title .tag.green", "e => e.textContent.trim()") if page.query_selector(".card-title .tag.green") else None)
    shot(page, "ux-ai-models.png")

    # kb tab
    page.click(".pill:has-text('知识库')")
    page.wait_for_timeout(900)
    report["kb_count_label"] = page.eval_on_selector(".card-title", "e => e.textContent.trim()")
    report["kb_items"] = page.eval_on_selector_all(".kb-item", "els => els.length")
    shot(page, "ux-ai-kb.png")
    # long KB path test: create my own file with a long name, check DOM, delete
    long_name = "EXPERT-ux-这是一个非常非常长的知识库文档路径名称用来测试布局"[:24]
    kbpath = f"05-元数据/{long_name}.md"
    code, data = api(token, "POST", "/api/admin/ai/kb", {"path": kbpath, "content": "# EXPERT-ux 长路径测试\n\n临时文件，收尾删除。\n"})
    report["kb_create_long"] = (code, data)
    page.goto(BASE + "/admin/ai", wait_until="domcontentloaded")  # remount to reload kb list
    page.wait_for_timeout(900)
    page.click(".pill:has-text('知识库')")
    page.wait_for_timeout(900)
    long_item = page.eval_on_selector(
        f".kb-item:has-text('{long_name}')",
        "e => {const p = e.querySelector('.kb-path'); const r = p.getBoundingClientRect(); return {w: Math.round(r.width), scrollW: p.scrollWidth, clientW: p.clientWidth, whiteSpace: getComputedStyle(p).whiteSpace, overflow: getComputedStyle(p).overflow}}")
    report["kb_long_path_cell"] = long_item
    shot(page, "ux-ai-kb-longpath.png")
    # delete via UI (confirm expected)
    n0 = len(dialogs)
    page.click(f".kb-item:has-text('{long_name}') button:has-text('删除')")
    page.wait_for_timeout(1200)
    report["kb_delete_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
    code, data = api(token, "GET", "/api/admin/ai/kb")
    report["kb_still_there"] = [x["path"] for x in data["items"] if long_name in x["path"]]
    report["kb_count_after"] = len(data["items"])

    # gen tab (form only; do NOT trigger real generation)
    page.click(".pill:has-text('AI 出题')")
    page.wait_for_timeout(500)
    report["gen_form_defaults"] = page.eval_on_selector_all(".mgrid.c3 input, .mgrid.c3 select", "els => els.map(e => e.value)")
    report["gen_button_text"] = page.eval_on_selector("button:has-text('生成题目')", "e => e.textContent.trim()")
    shot(page, "ux-ai-gen.png")

    # grade tab: is the select auto-loaded? (loadAttempts never called on mount)
    page.click(".pill:has-text('AI 判卷')")
    page.wait_for_timeout(1200)
    opts = page.eval_on_selector(".mgrid.c2 select", "s => [...s.options].map(o => o.textContent.trim())")
    report["grade_select_options_before_refresh"] = opts
    report["grade_empty_hint_visible"] = page.evaluate("""() => {
        const el = document.querySelector('.mgrid.c2');
        return el ? /暂无|没有.*交卷|学生交卷后/.test(el.textContent) : null;
    }""")
    shot(page, "ux-ai-grade-empty.png")
    # click 刷新卷单
    page.click("button:has-text('刷新卷单')")
    page.wait_for_timeout(1500)
    report["grade_select_options_after_refresh"] = page.eval_on_selector(".mgrid.c2 select", "s => [...s.options].map(o => o.textContent.trim())")
    report["grade_btn_disabled"] = page.eval_on_selector("button:has-text('开始 AI 判卷')", "e => e.disabled")

    # AI grade endpoint: synchronous error path only (nonexistent attempt)
    code, data = api(token, "POST", "/api/admin/ai/grade", {"attempt_id": 999999})
    report["grade_err_path"] = (code, data)
    report["dialogs_all"] = dialogs
    dump("ux-exams-ai-report.json", report)
finally:
    # ensure my kb file is gone
    code, data = api(token, "GET", "/api/admin/ai/kb")
    for x in data.get("items", []):
        if x["path"].split("/")[-1].startswith("EXPERT-ux-"):
            c, d = api(token, "DELETE", "/api/admin/ai/kb", {"path": x["path"]})
            log(f"cleanup kb {x['path']}: {c} {d}")
    browser.close()
    pw.stop()
log("UX-5 done")