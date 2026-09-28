# -*- coding: utf-8 -*-
"""数据总览指标卡下钻验收（Playwright，只读）。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = r"E:\lilei\platform\tools\shots"
fails = []


def bck(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + info) if info else ""))
    if not ok:
        fails.append(name)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.on("dialog", lambda dd: dd.accept())

        pg.goto(f"{BASE}/login", wait_until="load")
        pg.wait_for_timeout(600)
        pg.locator(".dh-btn", has_text="T2026").first.click()
        pg.locator("button", has_text=re.compile("登\\s*录")).first.click()
        pg.wait_for_timeout(2500)
        bck("登录→/admin", "/admin" in pg.url, pg.url)

        # 1) 活跃卡 → 展开明细面板
        hero = pg.locator(".mcard.hero")
        hero.click()
        pg.wait_for_timeout(500)
        drill = pg.locator(".drill")
        bck("活跃卡展开明细面板", drill.count() == 1, "")
        today_txt = pg.locator(".drill").inner_text()
        bck("面板含今日/7日两栏", "今日活跃" in today_txt and "近 7 日活跃" in today_txt, today_txt[:40].replace("\n", " "))
        hero_cls = hero.get_attribute("class") or ""
        bck("活跃卡高亮态 .on", "on" in hero_cls, hero_cls)
        pg.screenshot(path=OUT + "/drill-active.png")
        # 再点一次收起
        hero.click()
        pg.wait_for_timeout(300)
        bck("再次点击收起面板", pg.locator(".drill").count() == 0, "")

        # 2) 在读学生 → /admin/students
        pg.locator(".mcard", has_text="在读学生").click()
        pg.wait_for_timeout(800)
        bck("在读学生→学生管理", pg.url.rstrip("/").endswith("/admin/students"), pg.url)

        # 3) 题库规模 → 分簇面板
        pg.goto(f"{BASE}/admin", wait_until="load")
        pg.wait_for_timeout(1200)
        pg.locator(".mcard", has_text="题库规模").click()
        pg.wait_for_timeout(800)
        qtxt = pg.locator(".drill").inner_text() if pg.locator(".drill").count() else ""
        ok = pg.locator(".drill").count() == 1 and "Morse评估" in qtxt and "CPR启动" in qtxt and "题" in qtxt
        bck("题库卡展开六簇分布", ok, qtxt[:60].replace("\n", " "))
        pg.screenshot(path=OUT + "/drill-questions.png")

        # 4) AI 问答 → /admin/stats?tab=students 且落在学生画像 tab
        pg.goto(f"{BASE}/admin", wait_until="load")
        pg.wait_for_timeout(1200)
        pg.locator(".mcard", has_text="AI 问答总量").click()
        pg.wait_for_timeout(1500)
        bck("AI问答→统计页学生画像", "/admin/stats" in pg.url and "tab=students" in pg.url, pg.url)
        on_pill = pg.locator(".pill", has_text="学生培训画像").get_attribute("class") or ""
        bck("学生画像 tab 已激活", "on" in on_pill, on_pill)

        # 5) 累计练习 → /admin/exams
        pg.goto(f"{BASE}/admin", wait_until="load")
        pg.wait_for_timeout(1200)
        pg.locator(".mcard", has_text="累计练习").click()
        pg.wait_for_timeout(800)
        bck("累计练习→考试管理", pg.url.rstrip("/").endswith("/admin/exams"), pg.url)

        # 6) 累计学时 → 本页滚动到学时表
        pg.goto(f"{BASE}/admin", wait_until="load")
        pg.wait_for_timeout(1500)
        hours_card = pg.locator(".mcard", has_text="累计学时")
        hours_card.scroll_into_view_if_needed()
        hours_card.click()
        pg.wait_for_timeout(1200)  # 平滑滚动
        # 页面总高有限，滚到文档底部即止；学时表只要进入视口即算成功
        box = pg.locator(".card", has_text="学时统计（按学生）").bounding_box()
        sy = pg.evaluate("window.scrollY")
        bck("累计学时→滚动到学时表（表已入视口）",
            box is not None and 0 < box["y"] < 900 and sy > 100,
            f"scrollY={sy} y={box['y'] if box else None}")

        b.close()
    print(f"\n===== 下钻验收: {'全部通过' if not fails else str(len(fails)) + ' 失败: ' + '、'.join(fails)} =====")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())