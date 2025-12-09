#!/bin/bash
# AutoDL Flow - 应用启动脚本

cd "$(dirname "$0")/.."

echo "============================================================"
echo "AutoDL Flow - 启动应用"
echo "============================================================"
echo ""

# 检查应用是否已在运行
if pgrep -f "python.*app.py" > /dev/null; then
    echo "⚠️  应用已在运行中"
    echo "   如需重启，请先停止现有进程: pkill -f 'python.*app.py'"
    exit 1
fi

# 检查端口是否被占用
if lsof -Pi :6008 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 6008 已被占用"
    echo "   请检查是否有其他应用在使用该端口"
    exit 1
fi

echo "✅ 正在启动应用..."
echo "   访问地址: http://localhost:6008"
echo "   按 Ctrl+C 停止应用"
echo ""

# 启动应用
python app.py

