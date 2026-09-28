# -*- coding: utf-8 -*-
"""UX-6: /admin overview — reset button + modal (OPEN only, never confirm)."""
import sys
sys.path.insert(0, sys.path[0])
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
login(page)
report = {}
try:
    page.goto(BASE + "/admin", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    btn = page.eval_on_selector("button:has-text('演示数据重置')",
        "e => {const s = getComputedStyle(e); return {bg: s.backgroundColor, color: s.color, cls: e.className}}")
    report["reset_button_style"] = btn
    # open modal (must NOT click 确认重置)
    page.click("button:has-text('演示数据重置')")
    page.wait_for_timeout(400)
    report["reset_modal_open"] = bool(page.query_selector(".mask"))
    report["reset_modal_text"] = page.eval_on_selector(".mask .modal", "e => e.textContent.replace(/\\s+/g,' ').trim().slice(0, 200)") if page.query_selector(".mask .modal") else None
    report["reset_modal_style"] = page.eval_on_selector(".mask .modal",
        "e => {const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return {position: s.position, background: s.backgroundColor, w: Math.round(r.width), top: Math.round(r.top)}}") if page.query_selector(".mask .modal") else None
    shot(page, "ux-overview-reset-modal.png")
    # close via ✕
    page.click(".mask .modal-h .more")
    page.wait_for_timeout(300)
    report["reset_modal_closed_via_x"] = not page.query_selector(".mask")
    # leaderboard tabs quick check
    for t in ("掌握度", "学时"):
        page.click(f".pill:has-text('{t}')")
        page.wait_for_timeout(300)
    report["lb_tab_hours_first_row"] = page.eval_on_selector(".card:has-text('排行榜') tbody tr",
        "r => r ? r.textContent.trim() : null")
    # refresh button feedback
    page.click("button:has-text('刷新')")
    page.wait_for_timeout(150)
    report["refresh_btn_label_while_loading"] = page.eval_on_selector("button:has-text('刷新'), button:has-text('刷新中')", "e => e.textContent.trim()")
    dump("ux-overview-reset-report.json", report)
finally:
    browser.close()
    pw.stop()
log("UX-6 done")