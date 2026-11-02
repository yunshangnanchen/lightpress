#!/bin/sh
# 轻压 · Linux 启动脚本
# 解包后直接运行本脚本即可（会自动补执行权限）。
set -e

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ ! -x "$DIR/LightPress" ]; then
    chmod +x "$DIR/LightPress" 2>/dev/null || true
fi

exec "$DIR/LightPress" "$@"
