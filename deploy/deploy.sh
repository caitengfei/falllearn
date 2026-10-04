#!/usr/bin/env bash
# 康养智行 · Linux 服务器一键部署（Ubuntu 20.04+ / Debian 11+ / CentOS 7+）
# 用法：把 FallLearn 目录放到服务器任意位置，然后：
#   cd FallLearn && bash deploy/deploy.sh [端口，默认 8010]
# 完成后浏览器访问 http://服务器公网IP:端口
# 说明：直接用 IP:端口 访问，无需域名、无需 ICP 备案。
set -e
PORT="${1:-8010}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY=python3

echo "==> [1/5] 检查 Python 3.10+ 及 venv/pip（Ubuntu 云镜像默认缺 python3-venv，统一补齐）..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y >/dev/null 2>&1 || true
  apt-get install -y python3 python3-pip python3-venv git curl >/dev/null 2>&1 || apt-get install -y python3 python3-pip python3-venv git curl
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3 python3-pip git curl
fi
$PY --version

echo "==> [2/5] 创建虚拟环境并安装依赖 ..."
cd "$ROOT/backend"
$PY -m venv venv 2>/dev/null || $PY -m pip install --user virtualenv && $PY -m virtualenv venv
./venv/bin/pip install -q -i "${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}" -r requirements.txt

echo "==> [3/5] 初始化数据库（首次自动建库：题库 + 演示账号）..."
# 若已有库则保留，不覆盖

echo "==> [4/5] 写入 systemd 服务（开机自启 + 崩溃自动拉起）..."
cat > /etc/systemd/system/falllearn.service <<EOF
[Unit]
Description=FallLearn - 康养智行平台
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT/backend
ExecStart=$ROOT/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable falllearn
systemctl restart falllearn

echo "==> [5/5] 健康检查 ..."
sleep 3
curl -sf "http://127.0.0.1:$PORT/api/health" && echo ""
echo ""
echo "✅ 部署完成！"
echo "   本机访问:   http://127.0.0.1:$PORT"
echo "   公网访问:   http://<服务器公网IP>:$PORT   （云控制台/安全组请放行 $PORT 端口）"
echo "   常用命令:   systemctl status falllearn | journalctl -u falllearn -f"