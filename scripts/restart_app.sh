#!/usr/bin/env bash
# 在服务器上拉代码后重启本服务（监听 6008）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env.production ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.production
  set +a
fi

echo "停止占用 6008 的进程…"
if command -v fuser >/dev/null 2>&1; then
  fuser -k 6008/tcp 2>/dev/null || true
fi
pkill -f 'python.*app\.py' 2>/dev/null || true
pkill -f 'gunicorn.*6008' 2>/dev/null || true
sleep 1

if [[ -f "$ROOT/app.py" ]]; then
  ENTRY=app.py
elif [[ -f "$ROOT/old_app.py" ]]; then
  ENTRY=old_app.py
else
  echo "未找到 app.py 或 old_app.py" >&2
  exit 1
fi

mkdir -p "$ROOT/logs"
nohup python "$ENTRY" >>"$ROOT/logs/app.log" 2>&1 &
echo $! >"$ROOT/logs/app.pid"
echo "已后台启动: python $ENTRY (pid $(cat "$ROOT/logs/app.pid"))，日志: $ROOT/logs/app.log"
