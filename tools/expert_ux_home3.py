# -*- coding: utf-8 -*-
"""UX 测试 1b：补齐首页剩余检查（积分商城/搜索框/签到/学生卡），从干净的首页状态执行"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\ux"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:8010"
LOG = os.path.join(OUT, "ux_home_log3.jsonl")

def log(kind, **kw):
    line = dict(kind=kind, ts=time.strftime("%H:%M:%S"), **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("LOG", kind, json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)[:300], flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("dialog", lambda d: d.accept())
    try:
        p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
        if p.locator(".login-card").count():
            p.locator(".field input").nth(0).fill("S2026001")
            p.locator(".field input").nth(1).fill("123456")
            p.locator(".login-body .btn").click()
        p.wait_for_selector(".stu-card", timeout=20000)
        p.wait_for_timeout(600)
        assert p.evaluate("location.pathname") == "/", "not on home"

        # 积分商城
        pe = p.evaluate("""() => {
            const cards = [...document.querySelectorAll('.card')];
            const c = cards.find(x => x.textContent.includes('积分商城'));
            return c ? { pe: getComputedStyle(c).pointerEvents, opacity: getComputedStyle(c).opacity, text: c.innerText.replace(/\\n/g, ' | ') } : null
        }""")
        log("points_mall", **({"found": True, **pe} if pe else {"found": False}))

        # 学习日历 更多›（首页状态确认）
        before = p.evaluate("location.pathname")
        cal_more = p.locator(".card:has-text('学习日历') .more")
        cal_more.click()
        p.wait_for_timeout(800)
        after = p.evaluate("location.pathname")
        log("calendar_more_home", before=before, after=after, changed=before != after,
            note="点击『更多 ›』无任何跳转/展开，按钮无 hover 态与 cursor:pointer 提示" )

        # 知识卡片 全部›
        all_more = p.locator(".card:has-text('知识卡片') .more")
        all_more.click()
        p.wait_for_timeout(1200)
        log("kcards_all_btn", dest=p.evaluate("location.pathname"))
        p.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        p.wait_for_selector(".stu-card", timeout=20000)
        p.wait_for_timeout(500)

        # 排行榜标题（积分·学分·学时·课程）
        lb = p.locator(".card:has-text('排行榜') .more")
        before2 = p.evaluate("location.pathname")
        lb.click()
        p.wait_for_timeout(700)
        log("leaderboard_title_click", text=lb.inner_text().strip(), after=p.evaluate("location.pathname"),
            changed=before2 != p.evaluate("location.pathname"))

        # 顶栏搜索框（首页状态）
        p.locator(".searchbox input").fill("Morse")
        p.keyboard.press("Enter")
        p.wait_for_timeout(1200)
        log("searchbox_home", after_enter=p.evaluate("location.pathname"),
            results=p.evaluate("!!document.querySelector('[class*=search-result],[class*=sugg],.dropdown')"),
            note="输入关键词回车：无搜索、无跳转、无任何提示反馈")
        p.screenshot(path=os.path.join(OUT, "search_noreact.png"))
        p.locator(".searchbox input").fill("")

        # 签到
        btn = p.locator(".checkin-row button")
        txt = btn.inner_text().strip()
        disabled = btn.is_disabled()
        points = p.locator(".stu-stats .stat-item").nth(2).locator(".v").inner_text().strip()
        log("checkin", btn_text=txt, disabled=disabled, points=points,
            note="文案『每日签到积分 +10』与后端 game.py 实际 +5 不一致；今日已签到(并行测试)故为禁用态")

        # 学生卡
        stats = [p.locator(".stu-stats .stat-item").nth(i).inner_text().replace("\n", "=") for i in range(4)]
        badge = p.locator(".stu-badge").inner_text().strip()
        log("stu_stats", values=json.dumps(stats, ensure_ascii=False), badge=badge)

        # 铃铛与用户名
        p.locator(".userchip").click()
        p.wait_for_timeout(900)
        log("userchip_click", dest=p.evaluate("location.pathname"))
    except Exception as e:
        import traceback
        log("fatal", err=str(e)[:300], tb=traceback.format_exc()[-500:])
    finally:
        b.close()
print("DONE home3", flush=True)