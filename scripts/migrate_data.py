#!/usr/bin/env python3
"""
AutoDL Flow - 数据迁移脚本

将数据从旧的 /root/autodl_*_storage 目录迁移到项目目录内的 data/ 目录
"""
import shutil
import sys
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 旧目录路径
OLD_SCRIPTS_STORAGE = Path('/root/autodl_scripts_storage')
OLD_CONFIGS_STORAGE = Path('/root/autodl_configs_storage')
OLD_TEMP_SCRIPTS_STORAGE = Path('/root/autodl_temp_scripts_storage')
OLD_DEPLOYMENT_CONFIGS_STORAGE = Path('/root/autodl_deployment_configs_storage')
OLD_DEPLOYMENT_RECORDS_STORAGE = Path('/root/autodl_deployment_records_storage')

# 新目录路径
NEW_DATA_DIR = BASE_DIR / 'data'
NEW_SCRIPTS_STORAGE = NEW_DATA_DIR / 'scripts'
NEW_CONFIGS_STORAGE = NEW_DATA_DIR / 'configs'
NEW_TEMP_SCRIPTS_STORAGE = NEW_DATA_DIR / 'temp_scripts'
NEW_DEPLOYMENT_CONFIGS_STORAGE = NEW_DATA_DIR / 'deployment_configs'
NEW_DEPLOYMENT_RECORDS_STORAGE = NEW_DATA_DIR / 'deployment_records'


def migrate_directory(old_path, new_path, name):
    """迁移目录"""
    if not old_path.exists():
        print(f"⚠️  {name}: 旧目录不存在，跳过: {old_path}")
        return True
    
    if not old_path.is_dir():
        print(f"⚠️  {name}: 旧路径不是目录，跳过: {old_path}")
        return True
    
    # 检查新目录是否已有数据
    if new_path.exists() and any(new_path.iterdir()):
        print(f"⚠️  {name}: 新目录已存在数据，跳过迁移: {new_path}")
        print(f"   如需强制迁移，请先清空新目录")
        return True
    
    try:
        # 确保新目录存在
        new_path.mkdir(parents=True, exist_ok=True)
        
        # 复制所有内容
        print(f"📦 迁移 {name}...")
        print(f"   从: {old_path}")
        print(f"   到: {new_path}")
        
        # 复制目录内容
        for item in old_path.iterdir():
            dest = new_path / item.name
            if item.is_dir():
                if dest.exists():
                    print(f"   ⚠️  目标目录已存在，跳过: {dest}")
                else:
                    shutil.copytree(item, dest)
                    print(f"   ✅ 已复制目录: {item.name}")
            else:
                shutil.copy2(item, dest)
                print(f"   ✅ 已复制文件: {item.name}")
        
        print(f"✅ {name} 迁移完成")
        return True
    except Exception as e:
        print(f"❌ {name} 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("AutoDL Flow - 数据迁移脚本")
    print("=" * 60)
    print()
    print("此脚本将数据从 /root/autodl_*_storage 目录迁移到项目目录内的 data/ 目录")
    print()
    
    # 确认迁移
    response = input("是否继续迁移？(y/N): ").strip().lower()
    if response != 'y':
        print("迁移已取消")
        return
    
    print()
    print("开始迁移...")
    print()
    
    # 迁移各个目录
    results = []
    
    results.append((
        "脚本存储",
        migrate_directory(OLD_SCRIPTS_STORAGE, NEW_SCRIPTS_STORAGE, "脚本存储")
    ))
    
    results.append((
        "配置存储",
        migrate_directory(OLD_CONFIGS_STORAGE, NEW_CONFIGS_STORAGE, "配置存储")
    ))
    
    results.append((
        "临时脚本存储",
        migrate_directory(OLD_TEMP_SCRIPTS_STORAGE, NEW_TEMP_SCRIPTS_STORAGE, "临时脚本存储")
    ))
    
    results.append((
        "部署配置存储",
        migrate_directory(OLD_DEPLOYMENT_CONFIGS_STORAGE, NEW_DEPLOYMENT_CONFIGS_STORAGE, "部署配置存储")
    ))
    
    results.append((
        "部署记录存储",
        migrate_directory(OLD_DEPLOYMENT_RECORDS_STORAGE, NEW_DEPLOYMENT_RECORDS_STORAGE, "部署记录存储")
    ))
    
    print()
    print("=" * 60)
    print("迁移结果汇总")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status} - {name}")
    
    print()
    if success_count == total_count:
        print(f"✅ 所有数据迁移完成 ({success_count}/{total_count})")
        print()
        print("⚠️  注意：")
        print("   1. 旧目录数据已复制到新目录，但未删除")
        print("   2. 请验证新目录中的数据是否正确")
        print("   3. 确认无误后，可以手动删除旧目录:")
        print("      rm -rf /root/autodl_scripts_storage")
        print("      rm -rf /root/autodl_configs_storage")
        print("      rm -rf /root/autodl_temp_scripts_storage")
        print("      rm -rf /root/autodl_deployment_configs_storage")
        print("      rm -rf /root/autodl_deployment_records_storage")
    else:
        print(f"⚠️  部分迁移失败 ({success_count}/{total_count})")
        print("   请检查错误信息并手动处理")
    
    print()


if __name__ == '__main__':
    main()

