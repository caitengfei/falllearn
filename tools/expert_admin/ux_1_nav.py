# -*- coding: utf-8 -*-
"""UX-1: login landing (teacher -> /admin), sidebar active states, back-to-student entry."""
import sys
sys.path.insert(0, sys.path[0])
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
try:
    # --- teacher login landing ---
    href = login(page)
    log(f"teacher login landing: {href}")
    shot(page, "ux-admin-overview.png")

    # sidebar active count on /admin
    active = page.eval_on_selector_all(
        ".admin-side a.router-link-active", "els => els.map(e => e.textContent.trim())")
    log(f"/admin active sidebar items: {active}")

    # --- go to /admin/content, check active again (prefix match bug?) ---
    page.goto(BASE + "/admin/content", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    active2 = page.eval_on_selector_all(
        ".admin-side a.router-link-active", "els => els.map(e => e.textContent.trim())")
    log(f"/admin/content active sidebar items: {active2}")
    shot(page, "ux-admin-content-sidebar.png")

    # --- teacher on student side: entry to admin + 回学生端 button ---
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    back = page.query_selector(".back-student")
    log(f"student side has 回学生端 link: {bool(back)}" + (f" -> {back.get_attribute('href')}" if back else ""))
    userchip = page.eval_on_selector(
        ".userchip", "e => e.textContent.trim()")
    log(f"userchip text: {userchip!r}")
    shot(page, "ux-teacher-on-studentside.png")

    # click 回学生端 (to=/) then click userchip to enter admin
    if back:
        page.click(".back-student")
        page.wait_for_timeout(700)
        log(f"after 回学生端 click: {page.evaluate('location.href')}")
    page.click(".userchip")
    page.wait_for_timeout(900)
    log(f"after userchip click (teacher entry to admin): {page.evaluate('location.href')}")

    # logo click on admin page -> where?
    page.click(".logo")
    page.wait_for_timeout(900)
    log(f"after logo click on /admin: {page.evaluate('location.href')}")

    # student login landing (clear teacher session first: /login redirects when auth.ready)
    page.evaluate("localStorage.clear()")
    href3 = login(page, "S2026001", "123456")
    log(f"student login landing: {href3}")
finally:
    browser.close()
    pw.stop()
log("UX-1 done")