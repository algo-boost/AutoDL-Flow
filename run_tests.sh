#!/bin/bash
# 运行单元测试脚本

set -e

echo "=========================================="
echo "运行单元测试"
echo "=========================================="

# 检查是否安装了 pytest
if ! command -v pytest &> /dev/null; then
    echo "pytest 未安装，正在安装测试依赖..."
    pip install -r requirements.txt
fi

# 运行测试
echo ""
echo "运行所有测试..."
pytest tests/ -v

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="

