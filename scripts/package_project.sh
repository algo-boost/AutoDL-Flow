#!/bin/bash
# AutoDL Flow - 项目打包脚本
# 用于打包整个项目（包括数据和配置），方便迁移到其他服务器

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 打包文件名
PACKAGE_NAME="autodl_flow_$(date +%Y%m%d_%H%M%S)"
PACKAGE_FILE="${PACKAGE_NAME}.tar.gz"

echo "============================================================"
echo "AutoDL Flow - 项目打包脚本"
echo "============================================================"
echo ""
echo "项目目录: $PROJECT_DIR"
echo "打包文件: $PACKAGE_FILE"
echo ""

# 确认打包
read -p "是否继续打包？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "打包已取消"
    exit 1
fi

echo ""
echo "开始打包..."
echo ""

# 切换到项目目录
cd "$PROJECT_DIR"

# 创建临时打包目录
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="$TEMP_DIR/$PACKAGE_NAME"
mkdir -p "$PACKAGE_DIR"

echo "📦 复制项目文件..."

# 复制项目文件（排除不需要的文件）
rsync -av \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='archive' \
    --exclude='*.log' \
    --exclude='.env' \
    --exclude='.env.local' \
    --exclude='.DS_Store' \
    --exclude='Thumbs.db' \
    "$PROJECT_DIR/" "$PACKAGE_DIR/"

echo ""
echo "✅ 文件复制完成"
echo ""

# 创建打包文件
echo "📦 创建压缩包..."
cd "$TEMP_DIR"
tar -czf "$PROJECT_DIR/$PACKAGE_FILE" "$PACKAGE_NAME"

# 清理临时目录
rm -rf "$TEMP_DIR"

# 显示打包结果
PACKAGE_SIZE=$(du -h "$PROJECT_DIR/$PACKAGE_FILE" | cut -f1)

echo ""
echo "============================================================"
echo "打包完成！"
echo "============================================================"
echo ""
echo "打包文件: $PACKAGE_FILE"
echo "文件大小: $PACKAGE_SIZE"
echo "位置: $PROJECT_DIR/$PACKAGE_FILE"
echo ""
echo "📋 打包内容包括："
echo "   ✅ 所有源代码"
echo "   ✅ 所有配置文件"
echo "   ✅ 所有数据文件（scripts, configs, etc.）"
echo "   ✅ 前端模板和静态资源"
echo "   ✅ 依赖列表（requirements.txt）"
echo ""
echo "🚚 迁移到新服务器："
echo "   1. 传输文件: scp $PACKAGE_FILE user@server:/path/"
echo "   2. 解压: tar -xzf $PACKAGE_FILE"
echo "   3. 安装依赖: pip install -r requirements.txt"
echo "   4. 启动: python app.py"
echo ""

