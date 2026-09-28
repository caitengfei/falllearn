# -*- coding: utf-8 -*-
"""内容专家只读实测：防跌学堂 127.0.0.1:8010
只读原则：不交卷、不签到、不重答错题、不调 reset-demo。
S2026002 仅做：开一张模拟考卷(不交) + 1 次真实 AI 提问。
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"E:\lilei\docs\expert-test\content"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "test_log.txt"), "w", encoding="utf-8")

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n")
    LOG.flush()

BASE = "http://127.0.0.1:8010"

def wait_url(p, prefix, timeout=15000):
    """用 evaluate 读 URL（泵消息循环，避免 p.url 假死）"""
    t0 = time.time()
    while time.time() - t0 < timeout / 1000:
        u = p.evaluate("location.href")
        if u.startswith(prefix):
            return u
        p.wait_for_timeout(200)
    return p.evaluate("location.href")

def login(p, sno):
    p.goto(BASE + "/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_selector(".login-card", timeout=30000)
    p.locator(".field input").nth(0).fill(sno)
    p.locator(".field input").nth(1).fill("123456")
    p.locator(".login-body .btn").click()
    p.wait_for_selector(".stu-card", timeout=20000)
    log("LOGIN", sno, "->", p.evaluate("location.href"))

def shot(p, name):
    p.screenshot(path=os.path.join(OUT, name))
    log("SHOT", name)

def click_grid(p, label, shotname):
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector(".icon-item", timeout=15000)
    p.locator(".icon-item", has_text=label).first.click()
    p.wait_for_timeout(900)
    url = p.evaluate("location.href")
    first_title = p.evaluate("""() => {
        const els = [...document.querySelectorAll('.page .card-title, .page h2, .page .card-title')];
        return els.slice(0,3).map(e => e.innerText.trim()).join(' | ');
    }""")
    log(f"GRID[{label}] -> url={url} | 页面首标题: {first_title[:120]}")
    shot(p, shotname)

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1440, "height": 950})
    p.on("console", lambda m: log("CONSOLE", m.type, m.text[:200]) if m.type in ("error", "warning") else None)
    p.on("requestfailed", lambda r: log("REQFAIL", r.url, r.failure))

    # ================= S2026001 有数据学生 =================
    try:
        login(p, "S2026001")
        p.wait_for_timeout(1200)
        shot(p, "home.png")
        home = p.evaluate("""() => ({
            banner: (document.querySelector('.banner')||{}).innerText || '',
            badgeLine: (document.querySelector('.stu-badge')||{}).innerText || '',
            stats: [...document.querySelectorAll('.stu-card .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
            checkin: (document.querySelector('.checkin-row')||{}).innerText || '',
            grid: [...document.querySelectorAll('.icon-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
            weakCard: (document.querySelector('.card-title') ? [...document.querySelectorAll('.card')].find(c=>c.innerText.includes('弱项')) : null)?.innerText || '',
            timeline: (document.querySelector('.tl')||{}).innerText || '(空)',
            kcards: [...document.querySelectorAll('.kcard')].map(e=>e.innerText.replace(/\\n/g,' ')).slice(0,8)
        })""")
        log("HOME_S1 ==", json.dumps(home, ensure_ascii=False, indent=1))
    except Exception as e:
        log("ERR_HOME_S1", e)

    # 九宫格三个被质疑入口
    for label, name in [("比赛资料", "grid_competition.png"), ("我的报告", "grid_myreport.png"),
                        ("学习日历", "grid_calendar.png"), ("学习榜单", "grid_leaderboard.png"),
                        ("知识地图", "grid_map.png"), ("12分钟模拟考", "grid_mock.png")]:
        try:
            click_grid(p, label, name)
        except Exception as e:
            log(f"ERR_GRID[{label}]", e)

    # 学习中心：历史 + 簇抽屉
    try:
        p.goto(BASE + "/learn", wait_until="domcontentloaded")
        p.wait_for_selector(".chat-flow", timeout=15000)
        p.wait_for_timeout(800)
        flow = p.evaluate("""() => [...document.querySelectorAll('.chat-flow .msg')]
            .map(e => e.innerText.trim().replace(/\\n+/g,' ¶ ').slice(0,220))""")
        log("LEARN_FLOW_S1 ==", json.dumps(flow, ensure_ascii=False, indent=1))
        shot(p, "learn_s1.png")
        # 点「五步处置」簇
        p.locator(".kcard", has_text="五步处置").first.click()
        p.wait_for_timeout(600)
        drawer = p.evaluate("""() => {
            const cards = [...document.querySelectorAll('.card')];
            const d = cards.find(c => c.innerText.includes('岗课赛证详解'));
            return d ? d.innerText.trim() : null;
        }""")
        log("LEARN_DRAWER(五步处置) ==", drawer)
        shot(p, "learn_drawer.png")
    except Exception as e:
        log("ERR_LEARN_S1", e)

    # 练习页四个菜单
    try:
        p.goto(BASE + "/practice", wait_until="domcontentloaded")
        p.wait_for_selector(".menu-item", timeout=15000)
        p.wait_for_timeout(600)
        for menu, name in [("日常练习", "practice_daily.png"), ("12分钟模拟考", "practice_mock.png"),
                           ("教师布置", "practice_teacher.png"), ("错题重练", "practice_retrain.png")]:
            p.locator(".menu-item", has_text=menu).first.click()
            p.wait_for_timeout(500)
            tasks = p.evaluate("""() => [...document.querySelectorAll('.page .card')]
                .filter(c => c.querySelector('.rtitle') || c.innerText.includes('暂无任务'))
                .map(c => c.innerText.trim().replace(/\\n+/g,' ¶ ').slice(0,300))""")
            log(f"PRACTICE[{menu}] ==", json.dumps(tasks, ensure_ascii=False, indent=1))
            shot(p, name)
    except Exception as e:
        log("ERR_PRACTICE_S1", e)

    # 错题本 + 讲解弹层
    try:
        p.goto(BASE + "/wrong", wait_until="domcontentloaded")
        p.wait_for_selector(".row-item, .empty", timeout=15000)
        p.wait_for_timeout(600)
        wrong = p.evaluate("""() => ({
            title: (document.querySelector('.card-title')||{}).innerText || '',
            due: (document.querySelector('.tag.red')||{}).innerText || '(无到期标)',
            items: [...document.querySelectorAll('.row-item')].map(e=>e.innerText.trim().replace(/\\n+/g,' ¶ ').slice(0,260))
        })""")
        log("WRONG_S1 ==", json.dumps(wrong, ensure_ascii=False, indent=1))
        shot(p, "wrong_s1.png")
        p.locator("button:has-text('讲解')").first.click()
        p.wait_for_selector(".modal-mask", timeout=8000)
        p.wait_for_timeout(400)
        modal = p.evaluate("""() => (document.querySelector('.modal-mask')||{}).innerText || ''""")
        log("WRONG_EXPLAIN_MODAL ==", modal.replace("\n", " ¶ ")[:400])
        shot(p, "wrong_explain_modal.png")
        p.locator(".modal-mask .more:has-text('关闭')").first.click()
        p.wait_for_timeout(300)
    except Exception as e:
        log("ERR_WRONG_S1", e)

    # 我的页
    try:
        p.goto(BASE + "/mine", wait_until="domcontentloaded")
        p.wait_for_selector(".radar-box", timeout=15000)
        p.wait_for_timeout(600)
        mine = p.evaluate("""() => ({
            stats: [...document.querySelectorAll('.stu-stats .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
            badges: [...document.querySelectorAll('.card')].find(c=>c.innerText.includes('勋章'))
                ? [...document.querySelectorAll('.card')].find(c=>c.innerText.includes('勋章墙')).innerText.replace(/\\n+/g,' ¶ ') : ''
        })""")
        log("MINE_S1 ==", json.dumps(mine, ensure_ascii=False, indent=1))
        shot(p, "mine_s1.png")
    except Exception as e:
        log("ERR_MINE_S1", e)

    # 顶栏搜索框（装饰性验证）
    try:
        p.goto(BASE + "/", wait_until="domcontentloaded")
        p.wait_for_selector(".searchbox input", timeout=10000)
        p.locator(".searchbox input").fill("Morse")
        p.locator(".searchbox input").press("Enter")
        p.wait_for_timeout(700)
        log("SEARCH_ENTER -> url=", p.evaluate("location.href"), "（若无跳转=搜索无功能）")
        # 退出
        p.locator("button:has-text('退出')").first.click()
        p.wait_for_timeout(900)
        log("LOGOUT_S1 ->", p.evaluate("location.href"))
    except Exception as e:
        log("ERR_TOPBAR_S1", e)

    # ================= S2026002 空白学生 =================
    try:
        login(p, "S2026002")
        p.wait_for_timeout(1200)
        shot(p, "home_s2_blank.png")
        home2 = p.evaluate("""() => ({
            badgeLine: (document.querySelector('.stu-badge')||{}).innerText || '',
            stats: [...document.querySelectorAll('.stu-card .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
            weakCard: ([...document.querySelectorAll('.card')].find(c=>c.innerText.includes('弱项'))||{}).innerText || '',
            timeline: (document.querySelector('.tl')||{}).innerText || '(空)',
            kcards: [...document.querySelectorAll('.kcard')].map(e=>e.innerText.replace(/\\n/g,' '))
        })""")
        log("HOME_S2 ==", json.dumps(home2, ensure_ascii=False, indent=1))
    except Exception as e:
        log("ERR_HOME_S2", e)

    # 模拟考：点开 mock-1（不交卷）
    try:
        p.goto(BASE + "/practice", wait_until="domcontentloaded")
        p.wait_for_selector(".menu-item", timeout=15000)
        p.locator(".menu-item", has_text="12分钟模拟考").first.click()
        p.wait_for_timeout(500)
        p.locator(".page .card .btn:has-text('开始')").first.click()
        url = wait_url(p, BASE + "/exam/", 20000)
        log("MOCK_START ->", url)
        p.wait_for_selector(".page .card .opt", timeout=15000)
        p.wait_for_timeout(500)
        exam_head = p.evaluate("""() => {
            const head = [...document.querySelectorAll('.page .card')][0];
            return head ? head.innerText.trim().replace(/\\n+/g,' ¶ ').slice(0,400) : '';
        }""")
        log("EXAM_HEADER_S2 ==", exam_head)
        has_timer = p.evaluate("""() => {
            const t = document.body.innerText;
            return /剩余|倒计时|还剩|超时/.test(t);
        }""")
        log("EXAM_HAS_TIMER_TEXT =", has_timer)
        shot(p, "exam_mock_s2_q1.png")
        # 逐题浏览 10 题，记录题干+簇标签
        qrows = []
        for i in range(10):
            row = p.evaluate("""() => {
                const cards = [...document.querySelectorAll('.page .card')];
                const head = cards[0] ? cards[0].innerText.trim().split('\\n')[0] : '';
                const body = cards[1] ? cards[1].innerText.trim() : '';
                const tag = (document.querySelector('.page .tag')||{}).innerText || '';
                const stem = body.split('\\n')[0] || '';
                return {head, tag, stem: stem.slice(0,80)};
            }""")
            qrows.append(row)
            if i < 9:
                p.locator("button:has-text('下一题')").first.click()
                p.wait_for_timeout(300)
        log("EXAM_QUESTIONS_S2 ==", json.dumps(qrows, ensure_ascii=False, indent=1))
        gen = [r for r in qrows if r["tag"] == "general" or r["tag"] == "通用"]
        if gen:
            log("GENERAL_QUESTIONS_FOUND =", len(gen))
            shot(p, "exam_general_tag.png")
        # 记录到文件
        with open(os.path.join(OUT, "exam_questions_s2.txt"), "w", encoding="utf-8") as f:
            for i, r in enumerate(qrows, 1):
                f.write(f"Q{i} [tag={r['tag']}] {r['stem']}\n")
        # 返回，不交卷
        p.goto(BASE + "/practice", wait_until="domcontentloaded")
    except Exception as e:
        log("ERR_MOCK_S2", e)

    # 学习闭环：1 次真实提问
    try:
        p.goto(BASE + "/learn", wait_until="domcontentloaded")
        p.wait_for_selector(".chat-flow", timeout=15000)
        p.locator(".chat-input textarea").fill("什么是跌倒")
        p.locator(".chat-input .btn").click()
        log("ASK_SENT(什么是跌倒) t0=", time.strftime("%H:%M:%S"))
        p.wait_for_selector(".qopt", timeout=150000)
        p.wait_for_timeout(400)
        qcard = p.evaluate("""() => {
            const q = document.querySelector('.qcard');
            return q ? q.innerText.trim().replace(/\\n+/g,' ¶ ') : null;
        }""")
        log("CLARIFY_CARD ==", qcard)
        shot(p, "learn_s2_clarify.png")
        p.locator(".qopt").first.click()
        log("OPTION_CLICKED t=", time.strftime("%H:%M:%S"))
        t0 = time.time()
        try:
            p.wait_for_function("!!document.querySelector('.chat-flow .col')", timeout=180000)
            log("FOUR_COL_DONE elapsed=", round(time.time()-t0, 1), "s")
        except Exception:
            log("FOUR_COL_TIMEOUT 180s")
        p.wait_for_timeout(800)
        ans = p.evaluate("""() => {
            const ms = [...document.querySelectorAll('.chat-flow .msg.ai')];
            const last = ms[ms.length-1];
            return last ? last.innerText.trim() : '';
        }""")
        log("AI_ANSWER_S2 ==", ans.replace("\n", " ¶ ")[:1200])
        shot(p, "learn_s2_done.png")
        with open(os.path.join(OUT, "ai_answer_s2.txt"), "w", encoding="utf-8") as f:
            f.write(ans)
    except Exception as e:
        log("ERR_ASK_S2", e)

    # S2 我的页：首答之章应已点亮
    try:
        p.goto(BASE + "/mine", wait_until="domcontentloaded")
        p.wait_for_selector(".radar-box", timeout=15000)
        p.wait_for_timeout(600)
        mine2 = p.evaluate("""() => ({
            stats: [...document.querySelectorAll('.stu-stats .stat-item')].map(e=>e.innerText.replace(/\\n/g,' ')),
            badges: ([...document.querySelectorAll('.card')].find(c=>c.innerText.includes('勋章墙'))||{}).innerText.replace(/\\n+/g,' ¶ ') || ''
        })""")
        log("MINE_S2 ==", json.dumps(mine2, ensure_ascii=False, indent=1))
        shot(p, "mine_s2.png")
    except Exception as e:
        log("ERR_MINE_S2", e)

    b.close()
LOG.close()
log("ALL_DONE")