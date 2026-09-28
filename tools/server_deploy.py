# -*- coding: utf-8 -*-
"""FallLearn 一键部署到阿里云试用服务器（paramiko）。

流程：本地打代码包(zip) → 密码登录(仅首次) → 装本地公钥(后续 ssh/scp 免密)
      → SFTP 传代码包+数据库 → python3 -m zipfile 解包 → bash deploy/deploy.sh。
密码从环境变量 FALLLEARN_SSH_PASS 读取，绝不写入本文件（本脚本随仓库发布）。

用法：
  $env:FALLLEARN_SSH_PASS = '...'
  python tools/server_deploy.py
"""
import os
import shutil
import sys
import tempfile
import time
import zipfile

import paramiko

SERVER = os.environ.get("FALLLEARN_SERVER", "121.199.161.117")
SSH_PORT = int(os.environ.get("FALLLEARN_SSH_PORT", "22"))
APP_PORT = int(os.environ.get("FALLLEARN_APP_PORT", "8010"))
PASSWORD = os.environ.get("FALLLEARN_SSH_PASS", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # E:\lilei\platform
LOCAL_DB = os.path.join(ROOT, "backend", "falllearn.db")
PUBKEY = os.path.join(os.path.expanduser("~"), ".ssh", "falllearn_deploy.pub")
REMOTE = "/opt/falllearn"
CODE_ZIP = os.path.join(tempfile.gettempdir(), "falllearn_code.zip")

# 代码包内容（不含 .git / venv / __pycache__ / node_modules / db）
INCLUDE_DIRS = ["backend/app", "backend/seed", "frontend/dist", "deploy", "knowledge"]
INCLUDE_FILES = ["backend/requirements.txt"]


def build_zip():
    if os.path.exists(CODE_ZIP):
        os.remove(CODE_ZIP)
    n = 0
    with zipfile.ZipFile(CODE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for rel_dir in INCLUDE_DIRS:
            base = os.path.join(ROOT, rel_dir)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules", "venv")]
                for f in filenames:
                    if f.endswith(".pyc"):
                        continue
                    full = os.path.join(dirpath, f)
                    arc = os.path.relpath(full, ROOT)
                    z.write(full, arc)
                    n += 1
        for rel_f in INCLUDE_FILES:
            full = os.path.join(ROOT, rel_f)
            z.write(full, rel_f)
            n += 1
    print(f"代码包: {CODE_ZIP} ({n} 文件, {os.path.getsize(CODE_ZIP)//1024} KB)")
    return CODE_ZIP


def run(client, cmd, timeout=900, label=""):
    print(f"\n===== {label or cmd[:80]} =====", flush=True)
    t0 = time.time()
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    print(f"[{time.time() - t0:.1f}s exit={code}]", flush=True)
    if out.strip():
        print(out[-4000:] if len(out) > 4000 else out, flush=True)
    if err.strip() and code != 0:
        print("STDERR:", err[-2000:], flush=True)
    return code, out, err


def main():
    if not PASSWORD:
        print("缺少环境变量 FALLLEARN_SSH_PASS")
        sys.exit(2)
    if not os.path.isfile(PUBKEY):
        print("找不到本地公钥:", PUBKEY)
        sys.exit(2)
    pub = open(PUBKEY, encoding="utf-8").read().strip()

    build_zip()
    print(f"连接 {SERVER}:{SSH_PORT} ...", flush=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=SSH_PORT, username="root", password=PASSWORD,
              timeout=60, banner_timeout=180, auth_timeout=180)
    print("已连接", flush=True)

    run(c, "head -2 /etc/os-release; uname -m; python3 --version 2>&1; nproc; free -m | head -2; df -h / | tail -1",
        timeout=60, label="[1] 环境检查")

    code, _, _ = run(c,
                     f"mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
                     f"(grep -qxF '{pub}' /root/.ssh/authorized_keys 2>/dev/null || echo '{pub}' >> /root/.ssh/authorized_keys) && "
                     f"chmod 600 /root/.ssh/authorized_keys && echo KEY_OK",
                     timeout=60, label="[2] 安装本地公钥（后续 ssh/scp 免密）")
    if code != 0:
        print("!! 公钥安装失败"); sys.exit(1)

    sftp = c.open_sftp()
    print("SFTP 上传代码包 ...", flush=True)
    sftp.put(CODE_ZIP, "/root/falllearn_code.zip")
    print(f"SFTP 上传数据库 ({os.path.getsize(LOCAL_DB)//1024} KB) ...", flush=True)
    sftp.put(LOCAL_DB, "/root/falllearn.db.bak")
    sftp.close()

    code, out, _ = run(c,
                       f"rm -rf {REMOTE} && mkdir -p {REMOTE} && "
                       f"python3 -m zipfile -e /root/falllearn_code.zip {REMOTE}/ && rm -f /root/falllearn_code.zip && "
                       f"mv /root/falllearn.db.bak {REMOTE}/backend/falllearn.db && "
                       f"test -f {REMOTE}/backend/app/main.py -a -f {REMOTE}/frontend/dist/index.html "
                       f"-a -f {REMOTE}/backend/falllearn.db && echo UNPACK_OK",
                       timeout=300, label="[3] 解包代码 + 落位数据库")
    if code != 0 or "UNPACK_OK" not in out:
        print("!! 解包失败"); sys.exit(1)
    run(c, f"find {REMOTE}/knowledge -name '*.md' | wc -l; ls {REMOTE}/backend/app/ | head -20",
        timeout=60, label="[4] 内容核对（知识库 26 篇 / 后端模块）")

    code, out, _ = run(c, f"cd {REMOTE} && bash deploy/deploy.sh {APP_PORT}",
                       timeout=1500, label="[5] 一键部署（apt+venv+pip+systemd+健康检查）")
    if "部署完成" not in out and code != 0:
        print("!! 部署脚本失败"); sys.exit(1)

    code, out, _ = run(c,
                       f"systemctl is-active falllearn; curl -sf http://127.0.0.1:{APP_PORT}/api/health; echo; "
                       f"curl -sf -o /dev/null -w 'SPA index: HTTP %{{http_code}}\\n' http://127.0.0.1:{APP_PORT}/",
                       timeout=60, label="[6] 服务状态 + 本机健康检查")

    print("\n===== 部署结束 =====")
    print(f"服务器公网入口（需安全组放行 TCP {APP_PORT}）: http://{SERVER}:{APP_PORT}")
    c.close()


if __name__ == "__main__":
    main()