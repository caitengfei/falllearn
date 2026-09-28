# -*- coding: utf-8 -*-
"""测试 1: 单发 css 请求后，观察服务端是否主动 FIN/close。
测试 2: 两个连续 API 请求（keep-alive）是否正常。
测试 3: css + 2s 后 API 请求（模拟浏览器时序）。"""
import socket
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

B = "http://127.0.0.1:8010"
s = requests.post(B + "/api/auth/login", json={"student_no": "S2026003", "password": "123456"}, timeout=10).json()
tok = s["token"]


def read_full(sock, timeout=30):
    """读完整响应（按 content-length），返回 (buf, t_done)。"""
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        i = buf.find(b"\r\n\r\n")
        if i >= 0:
            cl = 0
            for line in buf[:i].decode("latin1").split("\r\n")[1:]:
                if line.lower().startswith("content-length:"):
                    cl = int(line.split(":")[1].strip())
            if len(buf) >= i + 4 + cl:
                return buf, time.time() - t0
        sock.settimeout(1)
        try:
            c = sock.recv(65536)
        except socket.timeout:
            continue
        if not c:
            return buf, time.time() - t0
        buf += c
    return buf, time.time() - t0


def wait_close(sock, wait=4):
    """观察服务端是否主动关闭。返回 'FIN'|'RST'|'open'。"""
    t0 = time.time()
    while time.time() - t0 < wait:
        sock.settimeout(max(0.2, wait - (time.time() - t0)))
        try:
            c = sock.recv(4096)
        except socket.timeout:
            continue
        except ConnectionResetError:
            return "RST"
        if c == b"":
            return "FIN"
        if c:
            return "DATA:" + c[:40].decode("latin1", "replace")
    return "open"


def t1():
    print("=== T1: css only, then watch close ===", flush=True)
    sock = socket.create_connection(("127.0.0.1", 8010), timeout=30)
    sock.sendall(b"GET /assets/Practice-C2KRBsM8.css HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nConnection: keep-alive\r\n\r\n")
    buf, dt = read_full(sock)
    print(f"css resp in {dt:.2f}s, status={buf.split(b' ')[1].decode()}", flush=True)
    print("close-watch:", wait_close(sock), flush=True)
    sock.close()


def t2():
    print("=== T2: two API requests on one conn ===", flush=True)
    sock = socket.create_connection(("127.0.0.1", 8010), timeout=30)
    for i in range(2):
        req = f"GET /api/wrong?status=active HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nAuthorization: Bearer {tok}\r\nConnection: keep-alive\r\n\r\n".encode()
        t0 = time.time()
        try:
            sock.sendall(req)
            buf, dt = read_full(sock)
            print(f"wrong#{i+1}: {dt:.2f}s status={buf.split(b' ')[1].decode() if buf else 'NONE'}", flush=True)
        except Exception as e:
            print(f"wrong#{i+1}: EXC {e!r}", flush=True)
            break
    print("close-watch:", wait_close(sock), flush=True)
    sock.close()


def t3():
    print("=== T3: css, sleep 2s, then API on same conn ===", flush=True)
    sock = socket.create_connection(("127.0.0.1", 8010), timeout=30)
    sock.sendall(b"GET /assets/Practice-C2KRBsM8.css HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nConnection: keep-alive\r\n\r\n")
    buf, dt = read_full(sock)
    print(f"css resp in {dt:.2f}s status={buf.split(b' ')[1].decode()}", flush=True)
    time.sleep(2)
    req = f"GET /api/wrong?status=active HTTP/1.1\r\nHost: 127.0.0.1:8010\r\nAuthorization: Bearer {tok}\r\nConnection: keep-alive\r\n\r\n".encode()
    t0 = time.time()
    try:
        sock.sendall(req)
        buf, dt = read_full(sock)
        print(f"wrong: {dt:.2f}s status={buf.split(b' ')[1].decode() if buf else 'NONE'}", flush=True)
    except Exception as e:
        print(f"wrong: EXC {e!r} (after {time.time()-t0:.1f}s)", flush=True)
    sock.close()


t1()
t2()
t3()
print("DONE", flush=True)