#!/usr/bin/env python3
"""
AutoDL Flow - 应用状态检查脚本
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("AutoDL Flow - 应用状态检查")
print("=" * 60)
print()

# 1. 检查应用导入
print("1. 检查应用导入...")
try:
    from app import app
    print("   ✅ 应用导入成功")
except Exception as e:
    print(f"   ❌ 应用导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 检查路由注册
print("\n2. 检查路由注册...")
try:
    routes = list(app.url_map.iter_rules())
    print(f"   ✅ 路由注册成功，共 {len(routes)} 个路由")
    
    # 检查关键路由
    key_routes = {
        '/': 'dashboard',
        '/login': 'login',
        '/task_setup': 'task_setup',
        '/task_submit': 'task_submit',
    }
    
    for path, endpoint in key_routes.items():
        found = False
        for rule in routes:
            if rule.rule == path and rule.endpoint == endpoint:
                found = True
                break
        if found:
            print(f"   ✅ {path} -> {endpoint}")
        else:
            print(f"   ⚠️  {path} -> {endpoint} (未找到)")
except Exception as e:
    print(f"   ❌ 路由检查失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 检查配置文件
print("\n3. 检查配置文件...")
config_files = [
    project_root / 'repos_config.json',
    project_root / '.accounts.json',
]
for config_file in config_files:
    if config_file.exists():
        print(f"   ✅ {config_file.name} 存在")
    else:
        print(f"   ⚠️  {config_file.name} 不存在（可能需要创建）")

# 4. 检查数据目录
print("\n4. 检查数据目录...")
data_dirs = [
    project_root / 'data' / 'scripts',
    project_root / 'data' / 'configs',
    project_root / 'data' / 'uploaded_files',
]
for data_dir in data_dirs:
    if data_dir.exists():
        print(f"   ✅ {data_dir.relative_to(project_root)} 存在")
    else:
        print(f"   ⚠️  {data_dir.relative_to(project_root)} 不存在（将自动创建）")

# 5. 检查端口
print("\n5. 检查端口 6008...")
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 6008))
sock.close()
if result == 0:
    print("   ⚠️  端口 6008 已被占用（应用可能正在运行）")
else:
    print("   ✅ 端口 6008 未被占用（应用未运行）")

# 6. 检查依赖
print("\n6. 检查关键依赖...")
try:
    import flask
    print(f"   ✅ Flask {flask.__version__}")
except ImportError:
    print("   ❌ Flask 未安装")

try:
    from autodl import AutoDLElasticDeployment
    print("   ✅ autodl-api 已安装")
except ImportError:
    print("   ⚠️  autodl-api 未安装（任务提交功能将受限）")

try:
    from cryptography.fernet import Fernet
    print("   ✅ cryptography 已安装")
except ImportError:
    print("   ⚠️  cryptography 未安装（Token 加密将禁用）")

print("\n" + "=" * 60)
print("检查完成！")
print("=" * 60)
print("\n如果应用无法访问，请尝试：")
print("1. 重启应用: python app.py")
print("2. 检查防火墙设置")
print("3. 检查应用日志")
print("4. 确认应用正在运行: ps aux | grep 'python.*app.py'")

