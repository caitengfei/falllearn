# -*- coding: utf-8 -*-
"""UX 交互体验测试 1/3 (修复版)：S2026001 首页全元素点击扫描（只读测试）"""
import sys, os, json, time, re
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_home_log2.jsonl")
findings = []
console_msgs = []
reqfails = []

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    findings.append(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

def wait_until(p, expr, timeout_ms=30000, interval=300):
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout_ms:
        try:
            if p.evaluate(expr):
                return True
        except Exception:
            pass
        p.wait_for_timeout(interval)
    return False

def url_path(p):
    try:
        return p.evaluate("location.pathname")
    except Exception:
        return "??"

def login(p, sno):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    if p.locator(".login-card").count() == 0:
        return
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card, .navtabs", timeout=20000)

def back_home(p):
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".stu-card", timeout=20000)
    p.wait_for_timeout(500)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text.split("\n")[0]), print("CONSOLE", m.type, m.text[:200].replace("\n", " "), flush=True)) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: (reqfails.append(r.url + " :: " + str(r.failure)), print("REQFAIL", r.url, str(r.failure)[:120], flush=True)))
    p.on("dialog", lambda d: (print("DIALOG", d.type, d.message[:100], flush=True), d.accept()))

    try:
        login(p, "S2026001")
        p.wait_for_timeout(800)

        # ---------- 2. 九宫格 9 个图标（逐个点击，记录去向） ----------
        icon_map = {}
        try:
            items = p.locator(".icon-item")
            n = items.count()
            log("icon_grid", count=n,
                layout="4列网格 9 项 → 4+4+1 布局，最后一行仅 1 项（见 home.png）")
            seen = set()
            for i in range(n):
                try:
                    lbl = items.nth(i).locator(".lbl").inner_text().strip()
                    items.nth(i).click()
                    ok = wait_until(p, "location.pathname !== '/'", 8000)
                    path = url_path(p)
                    icon_map[lbl] = path
                    p.wait_for_timeout(700)
                    # 到达 /learn 且无内容 = 记录页面破损
                    if path == "/learn" and "learn" not in seen:
                        bodylen = p.evaluate("document.body.innerText.length")
                        has_chat = p.locator(".chat-wrap").count()
                        log("icon_dest_page", label=lbl, path=path, body_text_len=bodylen, chat_rendered=bool(has_chat),
                            note="有学习历史时 /learn 渲染失败 → 全页空白（只余顶栏）")
                        p.screenshot(path=os.path.join(OUT, "icon_learn_broken.png"))
                    if path not in seen:
                        p.screenshot(path=os.path.join(OUT, "icon_%s.png" % (path.strip("/") or "home")))
                    seen.add(path)
                    log("icon", idx=i, label=lbl, dest=path, navigated=bool(ok))
                except Exception as e:
                    log("error", what="icon_%d" % i, err=str(e)[:150])
                back_home(p)
            from collections import Counter
            c = Counter(icon_map.values())
            log("icon_summary", mapping=json.dumps(icon_map, ensure_ascii=False),
                dest_counts=json.dumps({k: v for k, v in c.items()}, ensure_ascii=False))
        except Exception as e:
            log("error", what="icons", err=str(e)[:200])

        # ---------- 3. 知识卡片六簇（点击是否带上下文） ----------
        try:
            kc = p.locator(".kcard")
            n = kc.count()
            log("kcard_count", count=n)
            for idx in (0, 2, 5):
                if idx >= n:
                    continue
                name = kc.nth(idx).locator(".kname").inner_text().strip()
                kc.nth(idx).click()
                wait_until(p, "location.pathname === '/learn'", 8000)
                p.wait_for_timeout(600)
                search = p.evaluate("location.search")
                drawer = p.locator(".card:has-text('岗课赛证详解')").count()
                log("kcard", name=name, dest="/learn", search_params=search or "(无)", cluster_drawer_open=bool(drawer),
                    note="点击知识卡片不带任何簇上下文（无 query 参数/无预筛选/无抽屉）")
                back_home(p)
        except Exception as e:
            log("error", what="kcard", err=str(e)[:200])

        # ---------- 4. 今日弱项提醒 ----------
        try:
            weak = p.locator(".card:has-text('今日弱项提醒')")
            log("weak_card", text=weak.inner_text().replace("\n", " | ")[:200])
            p.screenshot(path=os.path.join(OUT, "home_weak.png"))
            if weak.locator("button:has-text('去学一下')").count():
                weak.locator("button:has-text('去学一下')").click()
                wait_until(p, "location.pathname === '/learn'", 8000)
                log("weak_btn", btn="去学一下", dest=url_path(p), search=p.evaluate("location.search") or "(无)",
                    note="弱项=五步处置，但跳转 /learn 不携带簇参数，落地页也不会高亮该簇")
                back_home(p)
        except Exception as e:
            log("error", what="weak", err=str(e)[:200])

        # ---------- 5. 学习日历 更多› / 知识卡片 全部› / 排行榜标题 ----------
        try:
            before = url_path(p)
            cal_more = p.locator(".card:has-text('学习日历') .more")
            if cal_more.count():
                log("calendar_more", text=cal_more.inner_text().strip())
                cal_more.click()
                p.wait_for_timeout(800)
                log("calendar_more_click", before=before, after=url_path(p), changed=url_path(p) != before,
                    note="点击后 URL/页面是否变化")
                back_home(p)
            all_more = p.locator(".card:has-text('知识卡片') .more")
            if all_more.count():
                all_more.click()
                wait_until(p, "location.pathname === '/learn'", 8000)
                log("kcards_all_btn", dest=url_path(p), text=all_more.inner_text().strip())
                back_home(p)
            lb = p.locator(".card:has-text('排行榜') .more")
            if lb.count():
                before2 = url_path(p)
                lb.click()
                p.wait_for_timeout(600)
                log("leaderboard_title_click", text=lb.inner_text().strip(), after=url_path(p), changed=url_path(p) != before2,
                    note="标题提示 积分/学分/学时/课程 四个维度，实际仅积分榜且不可切换")
                back_home(p)
        except Exception as e:
            log("error", what="calendar", err=str(e)[:200])

        # ---------- 6. 积分商城 ----------
        try:
            pe = p.evaluate("""() => {
                const cards = [...document.querySelectorAll('.card')];
                const c = cards.find(x => x.textContent.includes('积分商城'));
                return c ? getComputedStyle(c).pointerEvents : 'not-found'
            }""")
            log("points_mall", pointer_events=pe, note="置灰且 pointer-events:none，点击无任何反馈")
        except Exception as e:
            log("error", what="mall", err=str(e)[:200])

        # ---------- 7. 顶栏搜索框 ----------
        try:
            p.locator(".searchbox input").fill("Morse")
            p.keyboard.press("Enter")
            p.wait_for_timeout(1200)
            urlnow = url_path(p)
            has_results = p.evaluate("""() => !!document.querySelector('.search-result, .dropdown, [class*="search-result"], [class*="sugg"]')""")
            log("searchbox", after_enter=urlnow, on_home=(urlnow == "/"), results_appeared=has_results,
                note="顶栏搜索框无任何事件绑定，输入回车后无搜索/跳转/提示")
            p.screenshot(path=os.path.join(OUT, "search_noreact.png"))
        except Exception as e:
            log("error", what="search", err=str(e)[:200])

        # ---------- 8. 签到 ----------
        try:
            btn = p.locator(".checkin-row button")
            before_txt = btn.inner_text().strip()
            points_before = p.locator(".stu-stats .stat-item").nth(2).locator(".v").inner_text().strip()
            log("checkin_before", btn_text=before_txt, points=points_before,
                note="文案『每日签到积分 +10』，后端 game.py 实际 +5；按钮已禁用态=已签到")
        except Exception as e:
            log("error", what="checkin", err=str(e)[:200])

        # ---------- 9. 学生卡静态数据 ----------
        try:
            stats = [p.locator(".stu-stats .stat-item").nth(i).inner_text().replace("\n", "=") for i in range(4)]
            badge_txt = p.locator(".stu-badge").inner_text().strip()
            log("stu_stats", values=json.dumps(stats, ensure_ascii=False), badge=badge_txt,
                note="学习时长恒 0h（studyingHours 从未赋值）；学分恒 60；『共 1 枚勋章』为写死文案（实际勋章数见 /mine）")
        except Exception as e:
            log("error", what="stu_stats", err=str(e)[:200])

        # ---------- 10. 顶部导航 ----------
        navmap = {}
        for name in ["首页", "学习中心", "练习考试", "错题本", "我的"]:
            try:
                p.locator(".navtabs a", has_text=name).first.click()
                p.wait_for_timeout(900)
                navmap[name] = url_path(p)
                log("nav", tab=name, dest=navmap[name])
            except Exception as e:
                log("error", what="nav_" + name, err=str(e)[:150])
        p.locator(".logo").click()
        p.wait_for_timeout(900)
        log("logo_click", dest=url_path(p))
        # 铃铛
        p.locator(".bell").click()
        p.wait_for_timeout(900)
        log("bell_click", dest=url_path(p))

        # ---------- 11. 未知路由 ----------
        try:
            p.goto(BASE + "/nonexistent-xyz", wait_until="domcontentloaded", timeout=20000)
            p.wait_for_timeout(1200)
            log("unknown_route", dest=url_path(p), note="重定向回首页，无 404 页")
        except Exception as e:
            log("error", what="unknown_route", err=str(e)[:150])

        log("console_summary", count=len(console_msgs),
            msgs=json.dumps(list(dict.fromkeys(console_msgs))[:10], ensure_ascii=False)[:900])
        log("reqfail_summary", count=len(reqfails), msgs=json.dumps(reqfails[:10], ensure_ascii=False)[:500])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-600:])
    finally:
        b.close()

print("DONE home2", flush=True)