"""
AutoDL Flow - 日志配置模块
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_dir=None, log_level=logging.INFO, enable_file_logging=True):
    """
    配置应用程序日志
    
    Args:
        log_dir: 日志文件目录，默认为项目根目录下的 logs 文件夹
        log_level: 日志级别，默认为 INFO
        enable_file_logging: 是否启用文件日志，默认为 True
    """
    # 创建日志目录
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / 'logs'
    else:
        log_dir = Path(log_dir)
    
    if enable_file_logging:
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 创建格式化器
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(pathname)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（如果启用）
    if enable_file_logging:
        # 应用日志文件
        app_log_file = log_dir / 'app.log'
        app_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        app_handler.setLevel(log_level)
        app_handler.setFormatter(file_formatter)
        root_logger.addHandler(app_handler)
        
        # 错误日志文件
        error_log_file = log_dir / 'error.log'
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name):
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，通常是模块名
        
    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)

