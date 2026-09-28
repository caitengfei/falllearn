# -*- coding: utf-8 -*-
"""UX-4: /admin/trainings CRUD + /admin/stats tabs."""
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
token = login_api()
login(page)

def get_trainings():
    code, data = api(token, "GET", "/api/admin/trainings")
    return data["items"]

STU = PREFIX + "培训学员"
report = {"dialogs": []}
stu_id = None
try:
    # create a dedicated student via API (cleanup-safe)
    code, data = api(token, "POST", "/api/admin/students", {"name": STU, "password": "123456"})
    report["create_student_api"] = (code, data)
    if code == 200:
        stu_id = data["id"]

    # ---------- trainings page ----------
    page.goto(BASE + "/admin/trainings", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    shot(page, "ux-trainings-baseline.png")

    page.click("button:has-text('＋ 新建培训')")
    page.wait_for_timeout(300)
    shot(page, "ux-trainings-modal-open.png")
    page.fill(".mask input >> nth=0", PREFIX + "演练班")
    page.fill(".mask input >> nth=1", "EXPERT-ux 批次")
    # capacity input is number: nth=2
    page.fill(".mask input >> nth=2", "5")
    # pick my student chip
    page.click(f"label:has-text('{STU}')")
    page.wait_for_timeout(200)
    n0 = len(dialogs)
    page.click(".mask .btn:has-text('创建')")
    page.wait_for_timeout(1200)
    report["training_create_dialogs"] = dialogs[n0:] if len(dialogs) > n0 else None
    report["toast_after_training_create"] = (page.query_selector(".toast").inner_text() if page.query_selector(".toast") else None)
    tr = [t for t in get_trainings() if t["title"] == PREFIX + "演练班"]
    report["training_created"] = {"found": bool(tr), "enrolled": tr[0]["enrolled"] if tr else None, "done": tr[0]["done"] if tr else None, "rate": tr[0]["rate"] if tr else None}
    tid = tr[0]["id"] if tr else None
    row = f".card:has-text('{PREFIX}演练班')"
    shot(page, "ux-trainings-created.png")

    if tid:
        # mark complete
        page.click(row + f" button:has-text('标记完成')")
        page.wait_for_timeout(1200)
        t = [x for x in get_trainings() if x["id"] == tid][0]
        report["after_mark_done"] = {"done": t["done"], "rate": t["rate"],
                                     "chip_class": page.eval_on_selector(row + " span:has-text('" + STU + "')", "e => e.style.background || '(none)'")}
        shot(page, "ux-trainings-marked-done.png")
        # toggle back (destructive revert without confirm?)
        n0 = len(dialogs)
        page.click(row + " button:has-text('✓ 已完成')")
        page.wait_for_timeout(1200)
        report["toggle_back_dialogs"] = dialogs[n0:] if len(dialogs) > n0 else None
        t = [x for x in get_trainings() if x["id"] == tid][0]
        report["after_toggle_back"] = {"done": t["done"], "rate": t["rate"]}
        # no-enroll empty hint inside my card (I enrolled one; check the existing seed trainings instead)
        report["seed_training_enroll_hint"] = page.eval_on_selector(
            ".card:has-text('跌倒应急演练班')",
            "c => {const e = c.querySelector('div[style*=\"font-size: 12.5px\"]'); return e ? e.textContent.trim() : null}")
        # delete my training
        n0 = len(dialogs)
        page.click(row + " button:has-text('删除')")
        page.wait_for_timeout(900)
        report["delete_training_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
        page.wait_for_timeout(900)
        report["training_after_delete"] = [t["title"] for t in get_trainings() if t["title"] == PREFIX + "演练班"]
        shot(page, "ux-trainings-after-delete.png")

    # ---------- stats page ----------
    page.goto(BASE + "/admin/stats", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    shot(page, "ux-stats-trainings.png")
    for pill, name in [("学生培训画像", "ux-stats-students.png"), ("教师带训", "ux-stats-teachers.png")]:
        page.click(f".pill:has-text('{pill}')")
        page.wait_for_timeout(500)
        shot(page, name)
    report["stats_totals"] = page.eval_on_selector_all(".mcard", "els => els.map(e => e.textContent.replace(/\\s+/g,' ').trim())")
    report["dialogs_all"] = dialogs
    dump("ux-trainings-stats-report.json", report)
finally:
    # cleanup my student (also any leftover training)
    for t in get_trainings():
        if t["title"].startswith(PREFIX):
            api(token, "DELETE", f"/api/admin/trainings/{t['id']}")
            log(f"cleanup training {t['id']}")
    if stu_id:
        c, d = api(token, "DELETE", f"/api/admin/accounts/{stu_id}")
        log(f"cleanup student {stu_id}: {c} {d}")
    browser.close()
    pw.stop()
log("UX-4 done")