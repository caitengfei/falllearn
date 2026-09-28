# -*- coding: utf-8 -*-
"""DSH Web /api 协议客户端（实测 2026-09-28）：
- 一元调用: POST /api/<method>，envelope {type:client-request, rpcId, method, payload}
- 事件下行: WS /api/events.mux（SSE GET 返回 426，必须 WS 升级）
- 问题应答: POST /api/respond {type:client-response, rpcId:<问题rpcId>, result:{ok,value:{sessionId,answer:{answers:[{id,selected}]}}}}
"""
import asyncio
import json
import uuid

import httpx

BASE = "http://127.0.0.1:3090"  # DSH Web 学生端实例（生产由 settings 注入）


class DshError(Exception):
    pass


async def call(client: httpx.AsyncClient, method: str, payload: dict) -> dict:
    msg = {"type": "client-request", "rpcId": str(uuid.uuid4()), "method": method, "payload": payload}
    r = await client.post(f"{BASE}/api/{method}", json=msg, timeout=60)
    if r.status_code != 200:
        raise DshError(f"{method} HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    res = body.get("result", {})
    if res.get("ok") is False:
        raise DshError(f"{method} error: {json.dumps(res.get('error'), ensure_ascii=False)[:300]}")
    return res.get("value", {})


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


async def create_session(client, session_id: str, cwd: str, preset: str) -> dict:
    return await call(client, "session.create",
                      {"sessionId": session_id, "cwd": cwd, "agentPreset": preset})


async def send_prompt(client, session_id: str, text: str) -> dict:
    return await call(client, "session.prompt",
                      {"sessionId": session_id, "mode": "queue",
                       "content": [{"type": "text", "text": text}]})


async def get_history(client, session_id: str, max_messages: int = 40) -> dict:
    return await call(client, "session.history",
                      {"sessionId": session_id, "maxMessages": max_messages})


async def list_models(client, session_id: str) -> dict:
    """实时模型目录：{current, routable, groups:[{id,name,models:[...]}], failures}"""
    return await call(client, "session.models", {"sessionId": session_id})


async def select_model(client, session_id: str, provider: str, model: str) -> dict:
    return await call(client, "session.selectModel",
                      {"sessionId": session_id, "provider": provider, "model": model})


async def respond_question(client, question_rpc_id: str, session_id: str, answers: list) -> dict:
    msg = {
        "type": "client-response",
        "rpcId": question_rpc_id,
        "result": {"ok": True, "value": {"sessionId": session_id, "answer": {"answers": answers}}},
    }
    r = await client.post(f"{BASE}/api/respond", json=msg, timeout=30)
    if r.status_code != 200:
        raise DshError(f"respond HTTP {r.status_code}: {r.text[:200]}")
    return r.json() if r.content else {}


async def fetch_pending_question(session_id: str, timeout: float = 15.0):
    """短 WS 连接：pending 问题会在连接时重放为 question/requested 帧。
    返回 (rpc_id, questions) 或 None。"""
    import websockets

    url = f"{BASE.replace('http', 'ws')}/api/events.mux"
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(0.5, deadline - asyncio.get_event_loop().time()))
                except asyncio.TimeoutError:
                    break
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if obj.get("method") != "question/requested":
                    continue
                pl = obj.get("payload") or {}
                if pl.get("sessionId") != session_id:
                    continue
                return obj.get("rpcId"), pl.get("questions") or []
    except Exception:
        pass
    return None


# ---------- 事件下行（WS，长连接，备用） ----------
class EventHub:
    """平台级单 WS 连接 /api/events.mux；按 session_id 分发帧。"""

    def __init__(self):
        self.subs = {}  # session_id -> asyncio.Queue
        self.task = None
        self.alive = False

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        self.subs[session_id] = q
        return q

    def unsubscribe(self, session_id: str):
        self.subs.pop(session_id, None)

    async def start(self):
        if self.task and not self.task.done():
            return
        import websockets

        async def _run():
            while True:
                try:
                    async with websockets.connect(f"{BASE.replace('http', 'ws')}/api/events.mux",
                                                  max_size=8 * 1024 * 1024) as ws:
                        self.alive = True
                        async for raw in ws:
                            try:
                                obj = json.loads(raw)
                            except Exception:
                                continue
                            for sid, q in list(self.subs.items()):
                                pl = obj.get("payload") or {}
                                if isinstance(pl, dict) and pl.get("sessionId") == sid:
                                    await q.put(obj)
                except Exception:
                    self.alive = False
                await asyncio.sleep(2)

        self.task = asyncio.get_event_loop().create_task(_run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        self.alive = False