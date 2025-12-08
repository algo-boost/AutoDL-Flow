"""
AutoDL Flow - Token 管理工具函数
"""
import hashlib
import os
import time
from datetime import datetime, timedelta

# 临时下载token存储（应该使用 Redis 或数据库，这里简化处理）
download_tokens = {}


def generate_download_token(filename):
    """生成临时下载token"""
    token = hashlib.sha256(f"{filename}{time.time()}{os.urandom(16)}".encode()).hexdigest()
    # token有效期1小时
    download_tokens[token] = {
        'filename': filename,
        'expires_at': datetime.now() + timedelta(hours=1)
    }
    return token


def verify_download_token(token):
    """验证下载token是否有效"""
    if token not in download_tokens:
        return None
    
    token_data = download_tokens[token]
    if datetime.now() > token_data['expires_at']:
        # token已过期，删除
        del download_tokens[token]
        return None
    
    return token_data['filename']

