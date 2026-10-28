#!/usr/bin/env bash
# 停止 QQ 机器人；加 --vm 参数时连同 Colima 虚拟机一起停掉
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker compose down

if [[ "${1:-}" == "--vm" ]]; then
  colima stop
  echo "[QQ机器人] 容器与 Colima 虚拟机均已停止。"
else
  echo "[QQ机器人] 容器已停止（Colima 虚拟机仍在运行，下次启动更快）。"
fi
