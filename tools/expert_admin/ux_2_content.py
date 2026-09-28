# -*- coding: utf-8 -*-
"""UX-2: /admin/content — modal CSS, toast, notice CRUD, long text, switch race, banner sort."""
import time
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
token = login_api()
login(page)

def get_notices():
    code, data = api(token, "GET", "/api/admin/announcements")
    return data["items"]

def get_banners():
    code, data = api(token, "GET", "/api/admin/banners")
    return data["items"]

report = {"dialogs": []}
seed_banners = {}
# idempotent: remove leftover EXPERT-ux notices from previous runs
for n in get_notices():
    if n["title"].startswith(PREFIX):
        api(token, "DELETE", f"/api/admin/announcements/{n['id']}")
        log(f"precleanup notice {n['id']}")
try:
    page.goto(BASE + "/admin/content", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    # ---------- 1) modal computed styles (missing .mask/.modal CSS?) ----------
    page.click(".card-title:has-text('课程预告') >> text=＋ 新建预告")
    page.wait_for_timeout(400)
    mask = page.query_selector(".mask")
    modal = page.query_selector(".modal")
    if mask and modal:
        report["mask_style"] = page.eval_on_selector(".mask", "e => {const s=getComputedStyle(e); return {position:s.position, background:s.backgroundColor, inset:[s.top,s.right,s.bottom,s.left].join(','), zIndex:s.zIndex}}")
        report["modal_style"] = page.eval_on_selector(".modal", "e => {const s=getComputedStyle(e); const r=e.getBoundingClientRect(); return {width:Math.round(r.width), maxWidth:s.maxWidth, background:s.backgroundColor, borderRadius:s.borderRadius, position:s.position, marginTop:s.marginTop}}")
        report["modal_header_style"] = page.eval_on_selector(".modal-h", "e => {const s=getComputedStyle(e); return {fontSize:s.fontSize, fontWeight:s.fontWeight, borderBottom:s.borderBottomWidth}}")
    else:
        report["modal_present"] = bool(mask)
    shot(page, "ux-content-modal-open.png")

    # validation: empty title -> alert text
    page.click(".mask .btn:has-text('保存')")
    page.wait_for_timeout(300)
    report["dialog_empty_title"] = dialogs[-1] if dialogs else None
    report["modal_still_open"] = bool(page.query_selector(".mask"))

    # fill 40-char title + long summary
    title40 = PREFIX + "课程预告超长标题测试这是一条非常非常长的标题啊"
    title40 = title40[:40]
    summary = PREFIX + "摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要摘要"  # long summary
    page.fill(".mask input >> nth=0", title40)
    page.fill(".mask input >> nth=1", summary)
    # mask click-to-close test: find a point inside mask rect but outside modal rect
    page.wait_for_timeout(200)
    report["title_input_value"] = page.eval_on_selector(".mask input >> nth=0", "e => e.value")
    try:
        geom = page.eval_on_selector_all(".mask, .modal", "els => els.map(e => {const r = e.getBoundingClientRect(); return {cls: e.className, x: r.x, y: r.y, w: Math.round(r.width), h: Math.round(r.height)}})")
        report["mask_modal_geom"] = geom
        mk = next((g for g in geom if g["cls"] == "mask"), None)
        md = next((g for g in geom if g["cls"] == "modal"), None)
        if mk and md and mk["w"] > 0 and mk["h"] > 0:
            # point inside mask, above modal if possible, else to the left
            px, py = mk["x"] + 5, min(md["y"] - 5, mk["y"] + mk["h"] - 5)
            if py < md["y"] and py >= mk["y"]:
                page.mouse.click(px, py)
            elif mk["w"] > md["w"]:
                page.mouse.click(mk["x"] + 5, md["y"] + 5)
            else:
                report["maskclick_note"] = "mask rect not larger than modal (unstyled); skipping click"
            page.wait_for_timeout(300)
            report["after_maskclick_modal_open"] = bool(page.query_selector(".mask"))
        else:
            report["maskclick_note"] = "mask has no layout area (unstyled/zero-size)"
    except Exception as e:
        report["maskclick_err"] = str(e)
    # reopen and save
    if not page.query_selector(".mask"):
        page.click(".card-title:has-text('课程预告') >> text=＋ 新建预告")
        page.wait_for_timeout(300)
        page.fill(".mask input >> nth=0", title40)
        page.fill(".mask input >> nth=1", summary)
    page.click(".mask .btn:has-text('保存')")
    page.wait_for_timeout(600)
    toast = page.query_selector(".toast")
    report["toast_text"] = toast.inner_text() if toast else None
    report["toast_style"] = page.eval_on_selector(".toast", "e => {const s=getComputedStyle(e); const r=e.getBoundingClientRect(); return {position:s.position, background:s.backgroundColor, color:s.color, top:Math.round(r.top), bottom:Math.round(r.bottom)}}") if toast else None
    shot(page, "ux-content-notice-40char.png")

    # measure layout with 40-char title
    m = page.eval_on_selector_all(
        "table.atable tr",
        "rows => rows.filter(r => r.textContent.includes('" + PREFIX + "')).map(r => {const td = r.children[0]; return {titleCellW: Math.round(td.getBoundingClientRect().width), scrollW: td.scrollWidth, clientW: td.clientWidth, rowH: Math.round(r.getBoundingClientRect().height)}})[0]")
    report["long_title_cell"] = m
    tbl = page.eval_on_selector("table.atable", "e => ({scrollWidth: e.scrollWidth, clientWidth: e.clientWidth, pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth})")
    report["table_layout"] = tbl

    # ---------- 2) switch race: pin toggle, UI vs API ----------
    # NOTE: .switch is an inline <span> with no display:inline-block -> zero layout box.
    # Playwright normal click is blocked ("not visible"); a real user could only hit the 18px knob dot.
    row_sel = f"table.atable tr:has-text('{PREFIX}')"
    report["switch_box"] = page.eval_on_selector(row_sel + " .switch >> nth=0",
        "e => {const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return {w: r.width, h: r.height, display: s.display, position: s.position}}")
    report["switch_knob_box"] = page.eval_on_selector(row_sel + " .switch i >> nth=0",
        "e => {const r = e.getBoundingClientRect(); return {w: r.width, h: r.height, x: Math.round(r.x), y: Math.round(r.y)}}")
    shot(page, "ux-content-switch-broken.png")
    ui_before = page.eval_on_selector(row_sel + " .switch >> nth=0", "e => e.className")
    page.click(row_sel + " .switch i >> nth=0")         # pin on (user clicks the visible knob dot)
    page.wait_for_timeout(120)
    ui_fast = page.eval_on_selector(row_sel + " .switch >> nth=0", "e => e.className")
    page.wait_for_timeout(2500)
    ui_after = page.eval_on_selector(row_sel + " .switch >> nth=0", "e => e.className")
    db_pin = [n for n in get_notices() if n["title"] == title40][0]["pinned"]
    report["switch_pin"] = {"ui_before": ui_before, "ui_120ms": ui_fast, "ui_2500ms": ui_after, "db": db_pin,
                            "ui_matches_db": ("on" in ui_after) == bool(db_pin)}
    shot(page, "ux-content-pin-switch.png")

    # ---------- 3) rapid double click on enabled switch ----------
    ui_e0 = page.eval_on_selector(row_sel + " .switch >> nth=1", "e => e.className")
    page.click(row_sel + " .switch i >> nth=1")
    page.wait_for_timeout(80)
    page.click(row_sel + " .switch i >> nth=1")
    page.wait_for_timeout(2500)
    ui_e = page.eval_on_selector(row_sel + " .switch >> nth=1", "e => e.className")
    db_en = [n for n in get_notices() if n["title"] == title40][0]["enabled"]
    report["switch_doubleclick"] = {"ui_before": ui_e0, "ui_final": ui_e, "db": db_en,
                                    "ui_matches_db": ("on" in ui_e) == bool(db_en)}

    # ---------- 4) edit + delete notice ----------
    page.click(row_sel + " button:has-text('编辑')")
    page.wait_for_timeout(300)
    inp = page.eval_on_selector(".mask input >> nth=0", "e => e.value")
    report["edit_prefill"] = inp == title40
    page.fill(".mask input >> nth=0", title40 + "-改")
    page.click(".mask .btn:has-text('保存')")
    page.wait_for_timeout(600)
    report["toast_after_edit"] = (page.query_selector(".toast").inner_text() if page.query_selector(".toast") else None)
    title40 = title40 + "-改"
    page.click(f"table.atable tr:has-text('{PREFIX}') button.danger:has-text('删除')")
    page.wait_for_timeout(400)
    report["dialog_delete_notice"] = dialogs[-1] if dialogs else None
    page.wait_for_timeout(800)
    report["toast_after_delete"] = (page.query_selector(".toast").inner_text() if page.query_selector(".toast") else None)
    report["notices_after_delete"] = [n["title"] for n in get_notices()]
    shot(page, "ux-content-empty-notices.png")
    empty_row = page.eval_on_selector(".card:has-text('课程预告') .atable", "t => t.querySelector('tbody tr') ? t.querySelector('tbody tr').textContent.trim() : null")
    report["notice_empty_state"] = empty_row

    # ---------- 5) banner CRUD + default sort collision (use own banners; never touch seeds) ----------
    seed_banners = {b["id"]: dict(b) for b in get_banners() if not b["title"].startswith(PREFIX)}
    report["banner_order_before"] = [(b["title"][:16], b["sort"]) for b in get_banners()]

    def create_banner(title, sub=""):
        page.click(".card-title:has-text('主界面图片轮播') >> text=＋ 新增轮播卡")
        page.wait_for_timeout(300)
        page.fill(".mask input >> nth=0", title)
        if sub:
            page.fill(".mask input >> nth=2", sub)
        page.click(".mask .btn:has-text('保存')")
        page.wait_for_timeout(800)

    create_banner(PREFIX + "轮播A", PREFIX + "副标题" * 8)  # long sub (34 chars)
    order_after = [(b["title"][:16], b["sort"]) for b in get_banners()]
    report["banner_order_after_create_A"] = order_after
    report["my_banner_A_position"] = [b["title"] for b in get_banners()].index(PREFIX + "轮播A") + 1
    shot(page, "ux-content-banner-created.png")
    # long sub layout
    bsub = page.eval_on_selector(
        f"table.atable tr:has-text('{PREFIX}轮播A')",
        "r => {const d = r.querySelector('td:nth-child(2) div:nth-child(2)'); const s = getComputedStyle(d); return {whiteSpace: s.whiteSpace, overflow: s.overflow, text: d.textContent, rowH: Math.round(r.getBoundingClientRect().height)}}")
    report["banner_longsub_cell"] = bsub
    create_banner(PREFIX + "轮播B")
    report["banner_order_after_create_B"] = [(b["title"][:16], b["sort"]) for b in get_banners()]
    # move B up (swap with A) — both are my banners
    page.click(f"table.atable tr:has-text('{PREFIX}轮播B') button[title='上移']")
    page.wait_for_timeout(1500)
    report["banner_order_after_B_moveup"] = [(b["title"][:16], b["sort"]) for b in get_banners()]
    # toggle B enabled via knob
    page.click(f"table.atable tr:has-text('{PREFIX}轮播B') .switch i")
    page.wait_for_timeout(1500)
    b_en = [b for b in get_banners() if b["title"] == PREFIX + "轮播B"][0]["enabled"]
    report["banner_B_enabled_after_toggle"] = b_en
    # delete B then A
    page.click(f"table.atable tr:has-text('{PREFIX}轮播B') button.danger:has-text('删除')")
    page.wait_for_timeout(400)
    report["dialog_delete_banner"] = dialogs[-1] if dialogs else None
    page.wait_for_timeout(800)
    page.click(f"table.atable tr:has-text('{PREFIX}轮播A') button.danger:has-text('删除')")
    page.wait_for_timeout(400)
    page.wait_for_timeout(800)
    final_banners = {b["id"]: dict(b) for b in get_banners() if not b["title"].startswith(PREFIX)}
    report["banner_order_after_delete"] = [(b["title"][:16], b["sort"]) for b in get_banners()]
    report["seeds_untouched"] = seed_banners == final_banners
    report["dialogs_all"] = dialogs
    if not report["seeds_untouched"]:
        for bid, orig in seed_banners.items():
            cur = final_banners.get(bid, orig)
            if cur != orig:
                api(token, "PUT", f"/api/admin/banners/{bid}", orig)
                log(f"RESTORED seed banner {bid}")

    dump("ux-content-report.json", report)
finally:
    # safety net: ensure seed banners exactly match the baseline snapshot
    try:
        seed_now = {b["id"]: dict(b) for b in get_banners() if not b["title"].startswith(PREFIX)}
        if seed_banners:
            for bid, orig in seed_banners.items():
                cur = seed_now.get(bid)
                if cur is None or cur != orig:
                    api(token, "PUT", f"/api/admin/banners/{bid}", orig)
                    log(f"FINALLY restored seed banner {bid}")
        for b in get_banners():
            if b["title"].startswith(PREFIX):
                api(token, "DELETE", f"/api/admin/banners/{b['id']}")
                log(f"FINALLY deleted my banner {b['id']}")
    except Exception as e:
        log(f"finally cleanup err: {e}")
    browser.close()
    pw.stop()
log("UX-2 done")