# -*- coding: utf-8 -*-
"""UX-3: /admin/students + /admin/accounts — CRUD, confirm behaviors, self-protect."""
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
token = login_api()
login(page)

def get_students():
    code, data = api(token, "GET", "/api/admin/students")
    return data["items"]

def get_accounts():
    code, data = api(token, "GET", "/api/admin/accounts")
    return data["items"]

STU_NAME = PREFIX + "学生甲"
TCH_NAME = PREFIX + "教师乙"
report = {"dialogs": []}
# idempotent: remove leftovers from crashed previous runs
for a in get_accounts():
    if a["name"] in (STU_NAME, TCH_NAME):
        api(token, "DELETE", f"/api/admin/accounts/{a['id']}")
        log(f"precleanup account {a['id']} {a['name']}")
try:
    # ---------- students page ----------
    page.goto(BASE + "/admin/students", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    page.click("button:has-text('＋ 新增学生')")
    page.wait_for_timeout(300)
    page.fill(".mask input >> nth=0", STU_NAME)
    page.click(".mask .btn:has-text('创建')")
    page.wait_for_timeout(800)
    report["dialog_student_created"] = dialogs[-1] if dialogs else None
    stu = [s for s in get_students() if s["name"] == STU_NAME]
    report["student_created"] = {"found": bool(stu), "sno": stu[0]["student_no"] if stu else None}
    shot(page, "ux-students-created.png")
    stu_id = stu[0]["id"] if stu else None

    if stu_id:
        # disable WITHOUT confirm? capture whether a dialog appears
        n0 = len(dialogs)
        row = f"tr:has-text('{STU_NAME}')"
        # .switch span is zero-size (inline, no display); user can only hit the 18px knob dot
        report["student_switch_box"] = page.eval_on_selector(row + " .switch",
            "e => {const r = e.getBoundingClientRect(); return {w: r.width, h: r.height, display: getComputedStyle(e).display}}")
        page.click(row + " .switch i")
        page.wait_for_timeout(1500)
        report["disable_confirm_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
        s = [x for x in get_students() if x["id"] == stu_id][0]
        report["student_after_disable"] = {"ui_class": page.eval_on_selector(row + " .switch", "e => e.className"), "db_enabled": s["enabled"]}
        # re-enable (confirm expected)
        n0 = len(dialogs)
        page.click(row + " .switch i")
        page.wait_for_timeout(1500)
        report["enable_confirm_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
        s = [x for x in get_students() if x["id"] == stu_id][0]
        report["student_after_enable"] = {"ui_class": page.eval_on_selector(row + " .switch", "e => e.className"), "db_enabled": s["enabled"]}
        # reset password (confirm expected)
        n0 = len(dialogs)
        page.click(row + " button:has-text('重置密码')")
        page.wait_for_timeout(1500)
        report["resetpwd_dialogs"] = dialogs[n0:] if len(dialogs) > n0 else None
        shot(page, "ux-students-switch-states.png")

    # empty state of students table (not expected with 3 seeds; just capture header)
    # ---------- accounts page ----------
    page.goto(BASE + "/admin/accounts", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    # create teacher account
    page.click("button:has-text('＋ 新建账号')")
    page.wait_for_timeout(300)
    page.fill(".mask input >> nth=0", TCH_NAME)
    page.select_option(".mask select", "teacher")
    page.click(".mask .btn:has-text('创建')")
    page.wait_for_timeout(900)
    report["dialog_teacher_created"] = dialogs[-1] if dialogs else None
    acc = [a for a in get_accounts() if a["name"] == TCH_NAME]
    report["teacher_created"] = {"found": bool(acc), "sno": acc[0]["student_no"] if acc else None, "role": acc[0]["role"] if acc else None}
    shot(page, "ux-accounts-created.png")
    tch_id = acc[0]["id"] if acc else None

    # self-disable T2026 -> alert 不能停用自己的账号 (exact row match via JS; 'T2026' is a substring of T2026002)
    def self_row_js(action_js):
        return page.evaluate("""(action) => {
            const rows = [...document.querySelectorAll('table.atable tr')];
            const r = rows.find(x => {const td = x.querySelector('td.num'); return td && td.textContent.trim() === 'T2026';});
            if (!r) return {found: false};
            const sw = r.querySelector('.switch');
            if (action === 'click') sw.click();
            return {found: true, cls: sw.className};
        }""", action_js)

    n0 = len(dialogs)
    self_row_js("click")
    page.wait_for_timeout(900)
    report["self_disable_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
    report["self_switch_ui"] = self_row_js("read")

    # self-delete hidden?
    report["self_delete_button_visible"] = page.evaluate("""() => {
        const rows = [...document.querySelectorAll('table.atable tr')];
        const r = rows.find(x => {const td = x.querySelector('td.num'); return td && td.textContent.trim() === 'T2026';});
        return r ? !!([...r.querySelectorAll('button')].some(b => b.textContent.includes('删除'))) : null;
    }""")

    # delete my teacher account (confirm expected, irreversible text)
    if tch_id:
        n0 = len(dialogs)
        page.click(f"tr:has-text('{TCH_NAME}') button.danger:has-text('删除')")
        page.wait_for_timeout(900)
        report["delete_account_dialog"] = dialogs[n0:] if len(dialogs) > n0 else None
        report["teacher_after_delete"] = [a["name"] for a in get_accounts() if a["name"] == TCH_NAME]

    # delete my student (cleanup)
    if stu_id:
        page.goto(BASE + "/admin/accounts", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        page.click(f"tr:has-text('{STU_NAME}') button.danger:has-text('删除')")
        page.wait_for_timeout(900)
        report["delete_student_dialog"] = dialogs[-1] if dialogs else None
        report["student_after_delete"] = [a["name"] for a in get_accounts() if a["name"] == STU_NAME]
    report["dialogs_all"] = dialogs
    dump("ux-students-accounts-report.json", report)
finally:
    browser.close()
    pw.stop()
log("UX-3 done")