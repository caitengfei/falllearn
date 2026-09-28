# -*- coding: utf-8 -*-
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
for path in ["/learn", "/practice", "/wrong", "/mine", "/admin", "/login", "/assets", "/no-such-route-xyz"]:
    r = requests.get(B + path, timeout=5)
    is_index = 'id="app"' in r.text
    print(f"{path:24s} {r.status_code}  {'index.html (SPA)' if is_index else r.headers.get('content-type', '?')[:40]}")