#!/bin/bash
# 双击即可启动 QQ 机器人（AstrBot + SnowLuma）
cd "$(dirname "$0")" || exit 1

echo "=== 启动 QQ 机器人 ==="
./scripts/up.sh

echo
echo "浏览器入口："
echo "  AstrBot  : http://127.0.0.1:6185"
echo "  SnowLuma : http://127.0.0.1:5099"
echo "  QQ 扫码  : http://127.0.0.1:6081/vnc.html"
echo
echo "可以关闭此窗口，容器会在后台继续运行。"
echo "按回车键关闭..."
read -r _
