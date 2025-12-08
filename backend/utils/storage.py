"""
AutoDL Flow - 存储工具函数
"""
import json
import time
from datetime import datetime
from pathlib import Path
from backend.config import (
    CONFIG_FILE,
    CONFIGS_STORAGE_DIR,
    TEMP_SCRIPTS_DIR,
    DEPLOYMENT_CONFIGS_DIR,
    DEPLOYMENT_RECORDS_DIR
)
from backend.auth.utils import is_admin


def get_user_storage_dir(base_dir, username):
    """获取用户的存储目录，admin 使用根目录，其他用户使用子目录"""
    if is_admin(username):
        return base_dir
    else:
        user_dir = base_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir


def get_accessible_dirs(base_dir, username):
    """获取用户可访问的所有目录列表"""
    if is_admin(username):
        # admin 可以访问所有用户的目录
        dirs = [base_dir]  # 根目录（可能包含旧数据）
        if base_dir.exists():
            for item in base_dir.iterdir():
                if item.is_dir() and item.name != 'admin':
                    dirs.append(item)
        return dirs
    else:
        # 普通用户只能访问自己的目录
        user_dir = base_dir / username
        return [user_dir] if user_dir.exists() else []


def get_user_config_file(username):
    """获取用户的配置文件路径"""
    if is_admin(username):
        # admin 使用全局配置文件
        return CONFIG_FILE
    else:
        # 普通用户使用自己的配置文件
        user_config_dir = CONFIGS_STORAGE_DIR / username
        user_config_dir.mkdir(parents=True, exist_ok=True)
        return user_config_dir / 'user_config.json'


def cleanup_old_temp_scripts():
    """清理超过1小时的临时脚本文件"""
    try:
        current_time = time.time()
        deleted_count = 0
        
        if not TEMP_SCRIPTS_DIR.exists():
            return
        
        # 遍历所有用户目录
        for user_dir in TEMP_SCRIPTS_DIR.iterdir():
            if user_dir.is_dir():
                # 遍历该用户的所有临时脚本文件
                for script_file in user_dir.glob('run_*'):
                    try:
                        # 检查文件修改时间
                        file_mtime = script_file.stat().st_mtime
                        # 如果文件创建超过1小时（3600秒），删除它
                        if current_time - file_mtime > 3600:
                            script_file.unlink()
                            deleted_count += 1
                            print(f"Deleted old temp script: {script_file}")
                    except Exception as e:
                        print(f"Error deleting temp script {script_file}: {e}")
                        continue
        
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} old temp scripts")
    except Exception as e:
        print(f"Error in cleanup_old_temp_scripts: {e}")


def get_user_deployment_config_dir(username):
    """获取用户的任务提交配置目录"""
    if is_admin(username):
        user_config_dir = DEPLOYMENT_CONFIGS_DIR / 'admin'
    else:
        user_config_dir = DEPLOYMENT_CONFIGS_DIR / username
    user_config_dir.mkdir(parents=True, exist_ok=True)
    return user_config_dir


def get_user_deployment_records_dir(username):
    """获取用户的提交记录目录"""
    if is_admin(username):
        user_records_dir = DEPLOYMENT_RECORDS_DIR / 'admin'
    else:
        user_records_dir = DEPLOYMENT_RECORDS_DIR / username
    user_records_dir.mkdir(parents=True, exist_ok=True)
    return user_records_dir


def save_deployment_record(username, record_data):
    """保存提交记录"""
    try:
        records_dir = get_user_deployment_records_dir(username)
        
        # 生成记录文件名（使用时间戳）
        now = datetime.now()
        record_name = f"deployment_record_{now.strftime('%Y%m%d_%H%M%S')}.json"
        record_file = records_dir / record_name
        
        # 保存记录
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(record_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Deployment record saved: {record_file}")
        return True
    except Exception as e:
        print(f"Error saving deployment record: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_deployment_config(username, config_data, group=None):
    """保存任务提交配置"""
    try:
        config_dir = get_user_deployment_config_dir(username)
        
        # 如果指定了分组，在分组目录下保存
        if group and group.strip():
            group_dir = config_dir / group.strip()
            group_dir.mkdir(parents=True, exist_ok=True)
            config_dir = group_dir
        
        # 生成配置文件名（使用时间戳）
        now = datetime.now()
        config_name = f"deployment_config_{now.strftime('%Y%m%d_%H%M%S')}.json"
        config_file = config_dir / config_name
        
        # 在配置数据中添加分组信息
        if group and group.strip():
            config_data['group'] = group.strip()
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Deployment config saved: {config_file}")
        return True
    except Exception as e:
        print(f"Error saving deployment config: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_user_env_config_file(username):
    """获取用户的 .env_config.json 文件路径"""
    user_config_dir = get_user_storage_dir(CONFIGS_STORAGE_DIR, username)
    return user_config_dir / '.env_config.json'

