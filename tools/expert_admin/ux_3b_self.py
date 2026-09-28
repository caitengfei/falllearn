# -*- coding: utf-8 -*-
"""UX-3b: self-protect checks on /admin/accounts (T2026 row)."""
import sys
sys.path.insert(0, sys.path[0])
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
token = login_api()
login(page)
report = {}
try:
    page.goto(BASE + "/admin/accounts", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    FIND = """() => {
        const rows = [...document.querySelectorAll('table.atable tr')];
        const isSelf = td => td && /^T2026($|\s)/.test(td.textContent.trim());
        const r = rows.find(x => isSelf(x.querySelector('td.num')));
        if (!r) return {found: false, firstCells: rows.slice(1, 5).map(x => (x.querySelector('td') || {textContent: '?'}).textContent.trim())};
        return {found: true, firstCell: r.querySelector('td.num').textContent.trim(),
                meTag: !!r.querySelector('.tag.red'),
                hasDeleteBtn: [...r.querySelectorAll('button')].some(b => b.textContent.includes('删除')),
                hasResetBtn: [...r.querySelectorAll('button')].some(b => b.textContent.includes('重置密码'))};
    }"""
    report["self_row_probe"] = page.evaluate(FIND)
    log(f"probe: {report['self_row_probe']}")
    # click the self switch knob via JS and capture the alert
    n0 = len(dialogs)
    page.evaluate("""() => {
        const rows = [...document.querySelectorAll('table.atable tr')];
        const isSelf = td => td && /^T2026($|\s)/.test(td.textContent.trim());
        const r = rows.find(x => isSelf(x.querySelector('td.num')));
        if (r && r.querySelector('.switch')) r.querySelector('.switch').click();
    }""")
    page.wait_for_timeout(1000)
    report["self_disable_alert"] = dialogs[n0:] if len(dialogs) > n0 else None
    report["self_enabled_after"] = api(token, "GET", "/api/admin/accounts")[1]["items"]
    shot(page, "ux-accounts-self-protect.png")
    dump("ux-accounts-self-report.json", report)
finally:
    browser.close()
    pw.stop()
log("UX-3b done")