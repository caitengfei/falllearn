# -*- coding: utf-8 -*-
import sys
import uuid

import requests

sys.stdout.reconfigure(encoding="utf-8")
D = "http://127.0.0.1:3090"


def call(method, payload, timeout=30):
    msg = {"type": "client-request", "rpcId": str(uuid.uuid4()), "method": method, "payload": payload}
    r = requests.post(f"{D}/api/{method}", json=msg, timeout=timeout)
    return r.status_code, r.json() if r.text else {}


# 1. 用自定义 UUID 创建会话
custom = str(uuid.uuid4())
sc, sr = call("session.create", {"sessionId": custom, "cwd": r"E:\lilei\跌倒-岗课赛证知识库", "agentPreset": "gksc-student"})
val = sr.get("result", {}).get("value", {})
print("create(custom id):", sc, "->", val.get("sessionId"), "preset:", val.get("agentPreset"))
sid = val.get("sessionId") or custom

# 2. 给该会话发 prompt（用一句无歧义、不会触发澄清卡的短指令）
sc, sr = call("session.prompt", {"sessionId": sid, "mode": "queue",
                                 "content": [{"type": "text", "text": "请用一句话介绍 Morse 跌倒风险评估量表。"}]})
print("prompt:", sc, str(sr)[:200])

# 3. 等 40s 后看 history 是否开始产出
import time
time.sleep(40)
sc, sr = call("session.history", {"sessionId": sid, "maxMessages": 100})
evs = sr.get("result", {}).get("value", {}).get("events", [])
types = {}
for ev in evs:
    t = ev.get("event", ev).get("type")
    types[t] = types.get(t, 0) + 1
print("history events:", types)
for ev in evs[-4:]:
    e = ev.get("event", ev)
    print("  ", e.get("type"), str(e.get("data", ""))[:120])

# 4. 清理：关掉这个测试会话
sc, sr = call("session.cancel", {"sessionId": sid})
print("cancel:", sc, str(sr)[:100])