# -*- coding: utf-8 -*-
"""QA 专家共享工具：登录、请求封装、结果记录。"""
import json
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8010"
TAG = "EXPERT-qa"


class Recorder:
    def __init__(self):
        self.results = []
        self.findings = []

    def log(self, tag, name, ok, detail, severity=None, finding_id=None):
        line = f"[{'PASS' if ok else 'FAIL'}] {name}"
        if not ok:
            line += f"  -> {detail}"
        print(line, flush=True)
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok and severity:
            self.findings.append({
                "id": finding_id or f"QA-{len(self.findings) + 1}",
                "severity": severity,
                "title": name,
                "evidence": detail,
            })
        return ok

    def summary(self):
        n_fail = sum(1 for r in self.results if not r["ok"])
        return f"TOTAL={len(self.results)} PASS={len(self.results) - n_fail} FAIL={n_fail}"


def login(student_no, password="123456"):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"student_no": student_no, "password": password}, timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:300]


def req(method, path, token=None, json_body=None, files=None, params=None, timeout=60, raw=False):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, BASE + path, json=json_body, files=files,
                         params=params, headers=headers, timeout=timeout)
    if raw:
        return r
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:500]


def jbody(status, body):
    """统一取 detail/message 文本"""
    if isinstance(body, dict):
        return body.get("detail") or body.get("message") or json.dumps(body, ensure_ascii=False)[:200]
    return str(body)[:200]