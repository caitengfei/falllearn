# -*- coding: utf-8 -*-
"""审计后端所有写语句：INSERT/UPDATE/DELETE 之后、close() 之前是否有 commit()。"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "app")
bad = []
for f in sorted(os.listdir(APP)):
    if not f.endswith(".py"):
        continue
    lines = open(os.path.join(APP, f), encoding="utf-8").readlines()
    for i, ln in enumerate(lines):
        if re.search(r'execute\(\s*[f"\'"]\s*(INSERT|UPDATE|DELETE)\b', ln):
            has_commit = False
            for j in range(i, min(i + 10, len(lines))):
                if "commit()" in lines[j]:
                    has_commit = True
                if "close()" in lines[j]:
                    break
            if not has_commit:
                bad.append(f"{f}:{i+1}: {ln.strip()[:90]}")
print("\n".join(bad) if bad else "全部写语句均有 commit")
print(f"共 {len(bad)} 处可疑")