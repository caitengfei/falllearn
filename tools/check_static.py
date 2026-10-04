# -*- coding: utf-8 -*-
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
r = requests.get(B + "/", timeout=5)
print("static /:", r.status_code, "app div:", 'id="app"' in r.text, "title:", "康养智行" in r.text)
print("health:", requests.get(B + "/api/health", timeout=5).json())