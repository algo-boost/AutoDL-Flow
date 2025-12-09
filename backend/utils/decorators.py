"""
AutoDL Flow - 装饰器工具
提供常用的装饰器来减少代码重复
"""
from functools import wraps
from flask import session, request
from typing import Optional, Callable, Any
from pathlib import Path
from backend.utils.file_finder import (
    get_username,
    find_file_in_user_dirs,
    find_file_in_accessible_dirs,
    get_user_file_path
)
from backend.utils.errors import NotFoundError, APIError


def get_current_user(func: Callable) -> Callable:
    """
    装饰器：自动注入当前用户名到函数参数
    
    使用方式：
    @get_current_user
    def my_function(username, ...):
        # username 已自动从 session 获取
        pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'username' not in kwargs:
            kwargs['username'] = get_username()
        return func(*args, **kwargs)
    return wrapper


def find_user_file(
    file_type: str = 'script',
    filename_param: str = 'filename',
    file_path_param: str = 'file_path',
    search_all_users: bool = False,
    required: bool = True
):
    """
    装饰器：自动查找用户文件并注入到函数参数
    
    Args:
        file_type: 文件类型 ('script', 'upload', 'config', 'deployment', 'record')
        filename_param: 文件名参数名（从 kwargs 或 URL 参数获取）
        file_path_param: 文件路径参数名（注入到 kwargs）
        search_all_users: 是否搜索所有用户目录
        required: 文件是否必须存在，如果为 True 且未找到则抛出 NotFoundError
    
    使用方式：
    @find_user_file(file_type='script', filename_param='filename')
    def download_script(file_path, ...):
        # file_path 已自动查找并注入
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取文件名
            filename = kwargs.get(filename_param)
            if not filename:
                # 尝试从 URL 参数获取
                filename = request.view_args.get(filename_param) if request.view_args else None
            
            if not filename:
                if required:
                    raise APIError(f'{filename_param} 参数缺失', status_code=400, error_code='MISSING_PARAM')
                kwargs[file_path_param] = None
                return func(*args, **kwargs)
            
            # 查找文件
            username = get_username()
            file_path = find_file_in_user_dirs(
                filename=filename,
                file_type=file_type,
                username=username,
                search_all_users=search_all_users
            )
            
            if not file_path and required:
                raise NotFoundError(f'文件未找到: {filename}')
            
            kwargs[file_path_param] = file_path
            return func(*args, **kwargs)
        return wrapper
    return decorator


def find_user_file_in_accessible_dirs(
    file_type: str = 'config',
    filename_param: str = 'filename',
    file_path_param: str = 'file_path',
    required: bool = True
):
    """
    装饰器：在用户可访问的目录中查找文件
    
    使用方式：
    @find_user_file_in_accessible_dirs(file_type='config')
    def load_config(file_path, ...):
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            filename = kwargs.get(filename_param)
            if not filename:
                filename = request.view_args.get(filename_param) if request.view_args else None
            
            if not filename:
                if required:
                    raise APIError(f'{filename_param} 参数缺失', status_code=400, error_code='MISSING_PARAM')
                kwargs[file_path_param] = None
                return func(*args, **kwargs)
            
            username = get_username()
            file_path = find_file_in_accessible_dirs(
                filename=filename,
                file_type=file_type,
                username=username
            )
            
            if not file_path and required:
                raise NotFoundError(f'文件未找到: {filename}')
            
            kwargs[file_path_param] = file_path
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ensure_user_file_path(
    file_type: str = 'script',
    filename_param: str = 'filename',
    file_path_param: str = 'file_path',
    create_dir: bool = True
):
    """
    装饰器：确保用户文件路径存在（不检查文件是否存在，用于创建新文件）
    
    使用方式：
    @ensure_user_file_path(file_type='script', create_dir=True)
    def save_script(file_path, ...):
        # file_path 已准备好，可以直接使用
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            filename = kwargs.get(filename_param)
            if not filename:
                filename = request.view_args.get(filename_param) if request.view_args else None
            
            if not filename:
                raise APIError(f'{filename_param} 参数缺失', status_code=400, error_code='MISSING_PARAM')
            
            username = get_username()
            file_path = get_user_file_path(
                filename=filename,
                file_type=file_type,
                username=username,
                create_dir=create_dir
            )
            
            kwargs[file_path_param] = file_path
            return func(*args, **kwargs)
        return wrapper
    return decorator

