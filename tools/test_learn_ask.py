# -*- coding: utf-8 -*-
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8010"
D = "http://127.0.0.1:3090"

# 1. 直接打 3090：session.list（确认 API 通）
import uuid


def call(method, payload):
    msg = {"type": "client-request", "rpcId": str(uuid.uuid4()), "method": method, "payload": payload}
    r = requests.post(f"{D}/api/{method}", json=msg, timeout=30)
    return r.status_code, r.json() if r.text else {}


print("session.list:", call("session.list", {})[:1] if isinstance(call, str) else "")
sc, sl = call("session.list", {})
print("  ->", sc, str(sl)[:300])

# 2. session.create（平台同款参数）
sc, sr = call("session.create", {"cwd": r"E:\lilei\跌倒-岗课赛证知识库", "agentPreset": "gksc-student"})
print("session.create:", sc, str(sr)[:400])

# 3. 走平台 API 看 502 的具体 message
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026003", "password": "123456"}, timeout=10).json()
H = {"authorization": "Bearer " + s["token"]}
r = requests.post(B + "/api/learn/ask", json={"question": "测试"}, headers=H, timeout=60)
print("平台 /api/learn/ask:", r.status_code, r.text[:300])