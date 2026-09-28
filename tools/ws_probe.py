# -*- coding: utf-8 -*-
"""WS /api/events.mux 实测：pending 问题是否会重放/持续广播。"""
import asyncio
import json
import sys

import websockets

sys.stdout.reconfigure(encoding="utf-8")
URL = "ws://127.0.0.1:3090/api/events.mux"
OUT = r"E:\lilei\platform\tools\ws_frames.json"


async def main():
    frames = []
    async with websockets.connect(URL, max_size=8 * 1024 * 1024) as ws:
        print("WS connected:", URL, flush=True)
        for i in range(30):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                print("RAW:", raw[:200], flush=True)
                continue
            frames.append(obj)
            m = obj.get("method", "")
            pl = obj.get("payload") or {}
            ptype = pl.get("type") if isinstance(pl, dict) else type(pl).__name__
            sid = pl.get("sessionId", "") if isinstance(pl, dict) else ""
            print(f"#{len(frames)} {obj.get('type')} method={m} sid={sid[:8]} ptype={ptype}", flush=True)
            if "question" in m.lower() or ptype == "ask-user-question" or (isinstance(pl, dict) and pl.get("questions")):
                print("  >>> QUESTION FRAME:", json.dumps(obj, ensure_ascii=False)[:1500], flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(frames, f, ensure_ascii=False, indent=1)
    print(f"DONE {len(frames)} frames -> {OUT}")


asyncio.run(main())