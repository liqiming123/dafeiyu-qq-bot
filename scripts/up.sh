#!/usr/bin/env bash
# 启动 QQ 机器人（AstrBot + SnowLuma）
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if ! colima status >/dev/null 2>&1; then
  echo "[QQ机器人] Colima 未运行，正在启动虚拟机（约需 10-30 秒）..."
  colima start --cpu 4 --memory 8 --disk 100
fi

docker compose up -d
echo
docker compose ps
echo
echo "  AstrBot   WebUI : http://127.0.0.1:6185"
echo "  SnowLuma  WebUI : http://127.0.0.1:5099"
echo "  QQ 扫码   noVNC : http://127.0.0.1:6081/vnc.html"
