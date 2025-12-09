"""
AutoDL Flow - 文件查找工具
提供统一的文件查找逻辑，减少代码重复
"""
from pathlib import Path
from typing import Optional, List
from flask import session
from backend.config import (
    UPLOADED_FILES_DIR,
    SCRIPTS_STORAGE_DIR,
    TEMP_SCRIPTS_DIR,
    CONFIGS_STORAGE_DIR,
    DEPLOYMENT_CONFIGS_DIR,
    DEPLOYMENT_RECORDS_DIR
)
from backend.utils.storage import get_accessible_dirs, get_user_storage_dir
from backend.utils.errors import NotFoundError


def get_username() -> str:
    """从 session 获取用户名，默认返回 'admin'"""
    return session.get('username', 'admin')


def find_file_in_user_dirs(
    filename: str,
    file_type: str = 'script',
    username: Optional[str] = None,
    search_all_users: bool = False
) -> Optional[Path]:
    """
    在用户目录中查找文件
    
    Args:
        filename: 文件名
        file_type: 文件类型 ('script', 'upload', 'config', 'deployment', 'record')
        username: 用户名，如果为 None 则从 session 获取
        search_all_users: 是否搜索所有用户目录（仅 admin 可用）
    
    Returns:
        找到的文件路径，如果未找到返回 None
    """
    if username is None:
        username = get_username()
    
    # 根据文件类型确定搜索目录
    search_dirs = []
    if file_type == 'script':
        search_dirs = [SCRIPTS_STORAGE_DIR]
    elif file_type == 'upload':
        search_dirs = [UPLOADED_FILES_DIR]
    elif file_type == 'config':
        search_dirs = [CONFIGS_STORAGE_DIR]
    elif file_type == 'deployment':
        search_dirs = [DEPLOYMENT_CONFIGS_DIR]
    elif file_type == 'record':
        search_dirs = [DEPLOYMENT_RECORDS_DIR]
    elif file_type == 'temp':
        search_dirs = [TEMP_SCRIPTS_DIR]
    else:
        # 默认搜索所有目录
        search_dirs = [
            UPLOADED_FILES_DIR,
            SCRIPTS_STORAGE_DIR,
            TEMP_SCRIPTS_DIR,
            CONFIGS_STORAGE_DIR
        ]
    
    # 如果文件名包含路径分隔符，可能是相对路径（如 username/filename）
    actual_filename = filename
    if '/' in filename or '\\' in filename:
        # 处理相对路径格式（如 username/filename）
        parts = filename.replace('\\', '/').split('/')
        if len(parts) == 2:
            # 格式：username/filename
            user_dir_name, actual_filename = parts
            # 先尝试在指定用户目录查找
            for base_dir in search_dirs:
                if not base_dir.exists():
                    continue
                potential_path = base_dir / user_dir_name / actual_filename
                if potential_path.exists() and potential_path.is_file():
                    return potential_path
        else:
            # 多级路径，尝试在临时目录查找
            for base_dir in [TEMP_SCRIPTS_DIR]:
                if not base_dir.exists():
                    continue
                potential_path = base_dir / filename
                if potential_path.exists() and potential_path.is_file():
                    return potential_path
    
    # 搜索用户目录（使用实际文件名，不包含路径）
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        
        # 先检查用户自己的目录
        user_dir = get_user_storage_dir(base_dir, username)
        potential_path = user_dir / actual_filename
        if potential_path.exists() and potential_path.is_file():
            return potential_path
        
        # 如果允许搜索所有用户，检查其他用户目录
        if search_all_users:
            try:
                for item in base_dir.iterdir():
                    if item.is_dir() and item != user_dir:
                        potential_path = item / actual_filename
                        if potential_path.exists() and potential_path.is_file():
                            return potential_path
            except (PermissionError, OSError) as e:
                # 忽略权限错误，继续搜索
                pass
        
        # 检查根目录（admin 的旧文件可能在这里）
        if base_dir == SCRIPTS_STORAGE_DIR:
            potential_path = base_dir / actual_filename
            if potential_path.exists() and potential_path.is_file():
                return potential_path
    
    return None


def find_file_in_accessible_dirs(
    filename: str,
    file_type: str = 'config',
    username: Optional[str] = None
) -> Optional[Path]:
    """
    在用户可访问的目录中查找文件（使用 get_accessible_dirs）
    
    Args:
        filename: 文件名
        file_type: 文件类型
        username: 用户名，如果为 None 则从 session 获取
    
    Returns:
        找到的文件路径，如果未找到返回 None
    """
    if username is None:
        username = get_username()
    
    # 根据文件类型确定基础目录
    base_dir_map = {
        'config': CONFIGS_STORAGE_DIR,
        'deployment': DEPLOYMENT_CONFIGS_DIR,
        'record': DEPLOYMENT_RECORDS_DIR,
    }
    
    base_dir = base_dir_map.get(file_type, CONFIGS_STORAGE_DIR)
    accessible_dirs = get_accessible_dirs(base_dir, username)
    
    for dir_path in accessible_dirs:
        if not dir_path.exists():
            continue
        potential_path = dir_path / filename
        if potential_path.exists() and potential_path.is_file():
            return potential_path
    
    return None


def get_user_file_path(
    filename: str,
    file_type: str = 'script',
    username: Optional[str] = None,
    create_dir: bool = False
) -> Path:
    """
    获取用户文件的完整路径（不检查文件是否存在）
    
    Args:
        filename: 文件名
        file_type: 文件类型
        username: 用户名，如果为 None 则从 session 获取
        create_dir: 是否创建目录（如果不存在）
    
    Returns:
        文件路径
    """
    if username is None:
        username = get_username()
    
    # 根据文件类型确定基础目录
    base_dir_map = {
        'script': SCRIPTS_STORAGE_DIR,
        'upload': UPLOADED_FILES_DIR,
        'config': CONFIGS_STORAGE_DIR,
        'deployment': DEPLOYMENT_CONFIGS_DIR,
        'record': DEPLOYMENT_RECORDS_DIR,
        'temp': TEMP_SCRIPTS_DIR,
    }
    
    base_dir = base_dir_map.get(file_type, SCRIPTS_STORAGE_DIR)
    user_dir = get_user_storage_dir(base_dir, username)
    
    if create_dir:
        user_dir.mkdir(parents=True, exist_ok=True)
    
    return user_dir / filename

