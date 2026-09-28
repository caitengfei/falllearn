# -*- coding: utf-8 -*-
"""把验收套件整体指向远程服务器执行（BASE 替换法）。
用法: REMOTE_BASE=http://IP:8010 python tools/remote_suite.py [只跑某几个: api_check_admin drill_check e2e_admin smoke_platform]
"""
import os
import sys
import time

SERVER = os.environ.get("REMOTE_BASE", "http://121.199.161.117:8010")
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ALL = ["api_check_admin.py", "drill_check.py", "e2e_admin.py", "smoke_platform.py"]
sel = sys.argv[1:] or ALL
sel = [s if s.endswith(".py") else s + ".py" for s in sel]
for s in sel:
    if s not in ALL:
        print("未知脚本:", s, "可选:", ALL)
        sys.exit(2)

results = []
for fname in sel:
    path = os.path.join(TOOLS_DIR, fname)
    src = open(path, encoding="utf-8").read()
    assert "http://127.0.0.1:8010" in src, f"{fname} 里没有预期的 BASE 行"
    src = src.replace("http://127.0.0.1:8010", SERVER)
    print(f"\n########## 开始 {fname} → {SERVER} ##########", flush=True)
    t0 = time.time()
    code = 0
    try:
        exec(compile(src, path, "exec"), {"__name__": "__main__", "__file__": path})
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        code = 1
        print(f"!! {fname} 抛出异常: {e!r}", flush=True)
    print(f"########## {fname} exit={code} 用时{time.time()-t0:.0f}s ##########", flush=True)
    results.append((fname, code))

bad = [f for f, c in results if c]
print("\n==== 远程验收套件:", "ALL PASS" if not bad else f"FAILED: {bad}", f"→ {SERVER} ====")
sys.exit(1 if bad else 0)