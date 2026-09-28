# -*- coding: utf-8 -*-
"""复现：同一 keep-alive 连接上 css -> wrong -> quiz/start，测第 3 个请求的响应时间。"""
import socket
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

B = "http://127.0.0.1:8010"
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026003", "password": "123456"}, timeout=10).json()
tok = s["token"]
s2 = requests.post(B + "/api/auth/login", json={"student_no": "T2026", "password": "123456"}, timeout=10).json()
requests.post(B + "/api/admin/reset-demo", json={}, headers={"authorization": "Bearer " + s2["token"]}, timeout=30)


class Conn:
    def __init__(self):
        self.sock = socket.create_connection(("127.0.0.1", 8010), timeout=60)
        self.buf = b""

    def _fill(self, deadline):
        while time.time() < deadline:
            self.sock.settimeout(max(0.05, deadline - time.time()))
            try:
                c = self.sock.recv(65536)
            except socket.timeout:
                return
            if not c:
                return
            self.buf += c

    def _head_end(self):
        i = self.buf.find(b"\r\n\r\n")
        return i

    def _parse_cl(self, head: bytes) -> int:
        for line in head.decode("latin1").split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                return int(line.split(":")[1].strip())
        return 0

    def request(self, raw: bytes, timeout: float = 60):
        """发送请求，等待完整响应。返回 (t_header, t_full, status_line)。"""
        self.buf = b""
        t0 = time.time()
        self.sock.sendall(raw)
        th = None
        tf = None
        deadline = t0 + timeout
        cl = None
        while time.time() < deadline:
            if th is None and self._head_end() >= 0:
                th = time.time() - t0
                head = self.buf[:self._head_end()]
                cl = self._parse_cl(head)
            need = 4 + self._head_end() + cl if th is not None and self._head_end() >= 0 else None
            if th is not None and cl is not None and len(self.buf) >= 4 + self._head_end() + cl:
                if tf is None:
                    tf = time.time() - t0
                break
            self._fill(deadline)
        status = self.buf.split(b"\r\n")[0].decode("latin1") if self.buf else "NO DATA"
        return th, tf, status


def main():
    c = Conn()
    out = []

    def do(name, raw):
        try:
            r = c.request(raw)
        except Exception as e:
            print(f"{name}: EXC {e!r}", flush=True)
            print(f"{name}: last buf head: {c.buf[:400]!r}", flush=True)
            raise
        out.append((name, r))
        he = c.buf.find(b"\r\n\r\n")
        print(f"{name}: FULL HEAD={c.buf[:he].decode('latin1')!r}", flush=True)

    do("css", b"GET /assets/Practice-C2KRBsM8.css HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nConnection: keep-alive\r\n\r\n")

    do("wrong", f"GET /api/wrong?status=active HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nAuthorization: Bearer {tok}\r\nConnection: keep-alive\r\n\r\n".encode())

    time.sleep(3)  # 模拟浏览器：页面加载完 → 用户 3 秒后点击开卷

    for i in range(2):
        raw = ("POST /api/quiz/start HTTP/1.1\r\nHost: 127.0.0.1:8010\r\n"
               f"Authorization: Bearer {tok}\r\nContent-Type: application/json\r\n"
               "Content-Length: 2\r\nConnection: keep-alive\r\n\r\n" + "{}")
        r = c.request(raw.encode())
        out.append((f"quiz/start#{i+1}", r))

    for name, (th, tf, status) in out:
        print(f"{name}: t_header={th if th is None else round(th,2)}s t_full={tf if tf is None else round(tf,2)}s  {status[:60]}", flush=True)
    try:
        c.sock.close()
    except Exception as e:
        print("close err:", e, flush=True)


if __name__ == "__main__":
    main()