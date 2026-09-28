# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, sys.path[0])
from ux_common import *

pw, browser, ctx, page, dialogs = launch()
try:
    page.goto(BASE + "/admin/content", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("URL:", page.evaluate("location.href"))
    html = page.content()
    print("len:", len(html))
    import re
    print("body classes:", page.eval_on_selector("body", "e => e.innerHTML.slice(0, 600)"))
finally:
    browser.close()
    pw.stop()