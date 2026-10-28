#!/usr/bin/env bash
# 查看状态；默认显示容器 + 两个 WebUI，附加参数时实时跟日志：
#   ./scripts/logs.sh            -> 最近 60 行日志
#   ./scripts/logs.sh -f         -> 实时跟日志
#   ./scripts/logs.sh astrbot -f -> 只看 AstrBot
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker compose ps
echo
echo "  AstrBot   WebUI : http://127.0.0.1:6185"
echo "  SnowLuma  WebUI : http://127.0.0.1:5099"
echo "  QQ 扫码   noVNC : http://127.0.0.1:6081/vnc.html"
echo
if [[ "${1:-}" == "-f" ]]; then
  docker compose logs -f --tail=60
else
  docker compose logs --tail="${1:-60}"
fi
