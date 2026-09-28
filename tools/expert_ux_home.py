# -*- coding: utf-8 -*-
"""UX 交互体验测试 1/3：S2026001 首页全元素点击扫描（只读测试，不重置数据）"""
import sys, os, json, time, re
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_home_log.jsonl")
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
        log("note", what="login", note="already logged in, no login card")
        return
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card, .navtabs", timeout=20000)
    log("note", what="login", account=sno)

def back_home(p):
    p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".stu-card", timeout=20000)
    p.wait_for_timeout(600)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: (console_msgs.append(m.type + " " + m.text), print("CONSOLE", m.type, m.text[:250], flush=True)) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: (reqfails.append(r.url + " :: " + str(r.failure)), print("REQFAIL", r.url, str(r.failure)[:120], flush=True)))
    p.on("dialog", lambda d: (print("DIALOG", d.type, d.message[:100], flush=True), d.accept()))

    try:
        login(p, "S2026001")
        p.wait_for_timeout(800)
        p.screenshot(path=os.path.join(OUT, "home.png"))
        log("screenshot", file="home.png")

        # ---------- 1. Banner 4 个点 ----------
        try:
            banner_before = p.locator(".banner").inner_text()
            dots = p.locator(".banner-dots i")
            ndots = dots.count()
            changed = []
            for i in range(ndots):
                dots.nth(i).click()
                p.wait_for_timeout(500)
                changed.append(p.locator(".banner").inner_text() != banner_before)
            p.screenshot(path=os.path.join(OUT, "home_banner.png"))
            p.wait_for_timeout(8000)  # 观察自动轮播
            auto = p.locator(".banner").inner_text() != banner_before
            log("banner", dots=ndots, dot_click_changes_content=any(changed), per_dot=changed, auto_rotates_8s=auto,
                note="banner 内容为静态文案，无轮播/点击响应则=装饰性假控件")
        except Exception as e:
            log("error", what="banner", err=str(e)[:200])

        # ---------- 2. 九宫格 9 个图标 ----------
        icon_map = {}
        try:
            items = p.locator(".icon-item")
            n = items.count()
            for i in range(n):
                lbl = items.nth(i).locator(".lbl").inner_text().strip()
                items.nth(i).click()
                ok = wait_until(p, "location.pathname !== '/'", 8000)
                path = url_path(p)
                icon_map[lbl] = path
                log("icon", idx=i, label=lbl, dest=path, navigated=bool(ok))
                if path not in [v for v in icon_map.values()[:-1]]:
                    p.wait_for_timeout(700)
                    p.screenshot(path=os.path.join(OUT, "icon_%s.png" % path.strip("/").replace("/", "_") or "home"))
                back_home(p)
            log("icon_summary", mapping=json.dumps(icon_map, ensure_ascii=False))
        except Exception as e:
            log("error", what="icons", err=str(e)[:200])

        # ---------- 3. 知识卡片六簇 ----------
        try:
            kc = p.locator(".kcard")
            n = kc.count()
            for idx in (0, 2, 5):
                if idx >= n:
                    continue
                name = kc.nth(idx).locator(".kname").inner_text().strip()
                kc.nth(idx).click()
                wait_until(p, "location.pathname === '/learn'", 8000)
                search = p.evaluate("location.search")
                drawer = p.locator(".card:has-text('岗课赛证详解')").count()
                log("kcard", name=name, dest="/learn", search_params=search or "(无)", cluster_drawer_open=bool(drawer),
                    note="点击知识卡片是否带上下文（簇 id / 预筛选 / 抽屉）")
                if idx == 2:
                    p.screenshot(path=os.path.join(OUT, "kcard_click.png"))
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
                log("weak_btn", btn="去学一下", dest=url_path(p), search=p.evaluate("location.search") or "(无)")
                back_home(p)
        except Exception as e:
            log("error", what="weak", err=str(e)[:200])

        # ---------- 5. 学习日历 更多› / 知识卡片 全部› ----------
        try:
            before = url_path(p)
            cal_more = p.locator(".card:has-text('学习日历') .more")
            log("calendar_more", text=cal_more.inner_text().strip() if cal_more.count() else "(不存在)", has_handler_click=cal_more.count())
            if cal_more.count():
                cal_more.click()
                p.wait_for_timeout(800)
                log("calendar_more_click", before=before, after=url_path(p), changed=url_path(p) != before)
            all_more = p.locator(".card:has-text('知识卡片') .more")
            if all_more.count():
                all_more.click()
                wait_until(p, "location.pathname === '/learn'", 8000)
                log("kcards_all_btn", dest=url_path(p))
                back_home(p)
            # 排行榜卡片的“积分·学分·学时·课程”
            lb = p.locator(".card:has-text('排行榜') .more")
            if lb.count():
                before2 = url_path(p)
                lb.click()
                p.wait_for_timeout(600)
                log("leaderboard_title_click", text=lb.inner_text().strip(), after=url_path(p), changed=url_path(p) != before2)
                back_home(p)
        except Exception as e:
            log("error", what="calendar", err=str(e)[:200])

        # ---------- 6. 积分商城 ----------
        try:
            mall = p.locator(".card:has-text('积分商城')")
            pe = p.evaluate("""() => {
                const cards = [...document.querySelectorAll('.card')];
                const c = cards.find(x => x.textContent.includes('积分商城'));
                return c ? getComputedStyle(c).pointerEvents : 'not-found'
            }""")
            log("points_mall", pointer_events=pe, text=mall.inner_text().replace("\n", " | ")[:120] if mall.count() else "(不存在)")
        except Exception as e:
            log("error", what="mall", err=str(e)[:200])

        # ---------- 7. 顶栏搜索框 ----------
        try:
            p.locator(".searchbox input").fill("Morse")
            p.keyboard.press("Enter")
            p.wait_for_timeout(1200)
            log("searchbox", after_enter=url_path(p), note="输入 Morse 回车后是否出现搜索结果/跳转")
            p.screenshot(path=os.path.join(OUT, "search_noreact.png"))
        except Exception as e:
            log("error", what="search", err=str(e)[:200])

        # ---------- 8. 签到 ----------
        try:
            btn = p.locator(".checkin-row button")
            before_txt = btn.inner_text().strip()
            points_before = p.locator(".stu-stats .stat-item").nth(2).locator(".v").inner_text().strip()
            log("checkin_before", btn_text=before_txt, points=points_before)
            if "签到" in before_txt and "已" not in before_txt:
                btn.click()
                p.wait_for_timeout(1500)
                after_txt = btn.inner_text().strip()
                points_after = p.locator(".stu-stats .stat-item").nth(2).locator(".v").inner_text().strip()
                log("checkin_after", btn_text=after_txt, points=points_after,
                    label_says="+10(前端文案) vs 后端实际+5(game.py checkin delta=5)")
                p.screenshot(path=os.path.join(OUT, "home_checkin.png"))
            else:
                log("checkin_skip", reason="今日已签到", btn_text=before_txt)
        except Exception as e:
            log("error", what="checkin", err=str(e)[:200])

        # ---------- 9. 学生卡静态数据核验 ----------
        try:
            stats = [p.locator(".stu-stats .stat-item").nth(i).inner_text().replace("\n", "=") for i in range(4)]
            log("stu_stats", values=json.dumps(stats, ensure_ascii=False),
                note="学习时长恒为0h(前端studyingHours未赋值)、学分恒60、勋章'共1枚'为写死文案")
        except Exception as e:
            log("error", what="stu_stats", err=str(e)[:200])

        # ---------- 10. 顶部导航 5 tab + logo ----------
        navmap = {}
        for name in ["首页", "学习中心", "练习考试", "错题本", "我的"]:
            try:
                p.locator(".navtabs a", has_text=name).first.click()
                wait_until(p, "1", 5000)
                p.wait_for_timeout(800)
                navmap[name] = url_path(p)
                log("nav", tab=name, dest=navmap[name])
            except Exception as e:
                log("error", what="nav_" + name, err=str(e)[:150])
        p.locator(".logo").click()
        wait_until(p, "location.pathname === '/'", 8000)
        log("logo_click", dest=url_path(p))

        # ---------- 11. 未知路由 ----------
        try:
            p.goto(BASE + "/nonexistent-xyz", wait_until="domcontentloaded", timeout=20000)
            p.wait_for_timeout(1200)
            log("unknown_route", dest=url_path(p), note="应重定向回首页")
        except Exception as e:
            log("error", what="unknown_route", err=str(e)[:150])

        # ---------- 12. /exam/99999 直达（未开卷） ----------
        try:
            p.goto(BASE + "/exam/99999", wait_until="domcontentloaded", timeout=20000)
            p.wait_for_timeout(1500)
            empty_txt = p.locator(".card.empty").inner_text() if p.locator(".card.empty").count() else "(无空态卡片)"
            log("exam_direct_nostart", text=empty_txt, note="未开卷直达 /exam/:id 的空态表现")
            p.screenshot(path=os.path.join(OUT, "exam_empty.png"))
        except Exception as e:
            log("error", what="exam_direct", err=str(e)[:150])

        log("console_summary", count=len(console_msgs), msgs=json.dumps(console_msgs[:30], ensure_ascii=False)[:1500])
        log("reqfail_summary", count=len(reqfails), msgs=json.dumps(reqfails[:20], ensure_ascii=False)[:800])
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-800:])
    finally:
        p.screenshot(path=os.path.join(OUT, "home_end.png"))
        b.close()

print("DONE home", flush=True)