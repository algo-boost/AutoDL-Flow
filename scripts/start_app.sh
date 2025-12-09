#!/bin/bash
# AutoDL Flow - 应用启动脚本

cd "$(dirname "$0")/.."

echo "============================================================"
echo "AutoDL Flow - 启动应用"
echo "============================================================"
echo ""

# 加载环境变量配置（如果存在）
if [ -f ".env.production" ]; then
    echo "📋 加载生产环境配置..."
    set -a  # 自动导出所有变量
    source .env.production
    set +a
    echo "✅ 环境配置已加载"
elif [ -f ".env" ]; then
    echo "📋 加载环境配置..."
    set -a
    source .env
    set +a
    echo "✅ 环境配置已加载"
fi

# 检查必要的环境变量
if [ -z "$FLASK_SECRET_KEY" ]; then
    echo "⚠️  警告：FLASK_SECRET_KEY 未设置"
    if [ "$FLASK_ENV" = "production" ] || [ "$ENVIRONMENT" = "production" ]; then
        echo "❌ 生产环境必须设置 FLASK_SECRET_KEY！"
        echo "   请运行: ./fix_secret_key.sh"
        exit 1
    else
        echo "   将使用临时生成的密钥（仅用于开发）"
    fi
fi

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
echo "   环境: ${FLASK_ENV:-development}"
echo "   访问地址: http://localhost:6008"
echo "   按 Ctrl+C 停止应用"
echo ""

# 启动应用
python app.py

