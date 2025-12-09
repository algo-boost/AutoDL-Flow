#!/bin/bash
# AutoDL Flow - 生产环境启动脚本

cd "$(dirname "$0")/.."

echo "============================================================"
echo "AutoDL Flow - 生产环境启动"
echo "============================================================"
echo ""

# 加载生产环境配置
if [ -f ".env.production" ]; then
    echo "📋 加载生产环境配置..."
    set -a  # 自动导出所有变量
    source .env.production
    set +a
    echo "✅ 环境配置已加载"
    echo "   环境: ${FLASK_ENV:-未设置}"
    if [ -n "$FLASK_SECRET_KEY" ]; then
        echo "   SECRET_KEY: 已设置（长度: ${#FLASK_SECRET_KEY}）"
    else
        echo "   SECRET_KEY: 未设置"
    fi
else
    echo "❌ 错误：未找到 .env.production 配置文件"
    echo "   请创建 .env.production 文件并设置以下变量："
    echo "   FLASK_ENV=production"
    echo "   FLASK_SECRET_KEY='your-secret-key-at-least-32-chars'"
    echo ""
    echo "   生成密钥：python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    exit 1
fi

# 验证必要的环境变量
if [ -z "$FLASK_SECRET_KEY" ]; then
    echo "❌ 错误：FLASK_SECRET_KEY 未设置！"
    echo "   请在 .env.production 文件中设置 FLASK_SECRET_KEY"
    exit 1
fi

if [ ${#FLASK_SECRET_KEY} -lt 32 ]; then
    echo "❌ 错误：FLASK_SECRET_KEY 长度不足（当前: ${#FLASK_SECRET_KEY}，要求: 至少 32）"
    exit 1
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

echo ""
echo "✅ 正在启动应用（生产环境）..."
echo "   访问地址: http://localhost:6008"
echo "   按 Ctrl+C 停止应用"
echo ""

# 确保环境变量被导出
export FLASK_ENV
export ENVIRONMENT
export FLASK_SECRET_KEY

# 启动应用（生产环境不使用 debug 模式）
python app.py

