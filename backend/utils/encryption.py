"""
AutoDL Flow - 加密工具函数
"""
import os
import stat
from pathlib import Path
from backend.config import (
    CRYPTOGRAPHY_AVAILABLE,
    ENCRYPTION_KEY_FILE,
    CONFIGS_STORAGE_DIR
)
from backend.utils.storage import get_user_storage_dir


def get_encryption_key():
    """获取加密密钥，如果不存在则生成"""
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
    
    try:
        if ENCRYPTION_KEY_FILE.exists():
            with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                key = f.read()
        else:
            from cryptography.fernet import Fernet
            # 生成新密钥
            key = Fernet.generate_key()
            # 确保目录存在
            ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            # 写入密钥文件
            with open(ENCRYPTION_KEY_FILE, 'wb') as f:
                f.write(key)
            # 设置文件权限为仅所有者可读写 (0o600)
            os.chmod(ENCRYPTION_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
        return key
    except Exception as e:
        print(f"Error getting encryption key: {e}")
        return None


def get_cipher():
    """获取加密器实例"""
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
    key = get_encryption_key()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key)
    except Exception as e:
        print(f"Error creating cipher: {e}")
        return None


def encrypt_token(token):
    """加密 Token"""
    if not token:
        return None
    cipher = get_cipher()
    if not cipher:
        # 如果没有加密库，返回原始 token（不推荐，但为了兼容性）
        return token
    try:
        return cipher.encrypt(token.encode()).decode()
    except Exception as e:
        print(f"Error encrypting token: {e}")
        return None


def decrypt_token(encrypted_token):
    """解密 Token"""
    if not encrypted_token:
        return None
    cipher = get_cipher()
    if not cipher:
        # 如果没有加密库，返回原始 token
        return encrypted_token
    try:
        return cipher.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        print(f"Error decrypting token: {e}")
        return None


def get_user_autodl_token_file(username):
    """获取用户的 AutoDL Token 文件路径"""
    user_config_dir = get_user_storage_dir(CONFIGS_STORAGE_DIR, username)
    token_file = user_config_dir / '.autodl_token'
    return token_file


def save_user_autodl_token(username, token):
    """保存用户的 AutoDL Token（加密存储）"""
    if not token or not token.strip():
        return False
    try:
        token_file = get_user_autodl_token_file(username)
        encrypted_token = encrypt_token(token.strip())
        if not encrypted_token:
            return False
        
        # 确保目录存在
        token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入加密后的 token
        with open(token_file, 'w') as f:
            f.write(encrypted_token)
        
        # 设置文件权限为仅所有者可读写 (0o600)
        os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)
        
        # 确保目录权限也安全 (0o700)
        os.chmod(token_file.parent, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        
        return True
    except Exception as e:
        print(f"Error saving autodl token: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_user_autodl_token(username):
    """加载用户的 AutoDL Token（解密）"""
    try:
        token_file = get_user_autodl_token_file(username)
        if not token_file.exists():
            return None
        
        with open(token_file, 'r') as f:
            encrypted_token = f.read().strip()
        
        if not encrypted_token:
            return None
        
        return decrypt_token(encrypted_token)
    except Exception as e:
        print(f"Error loading autodl token: {e}")
        return None


def delete_user_autodl_token(username):
    """删除用户的 AutoDL Token"""
    try:
        token_file = get_user_autodl_token_file(username)
        if token_file.exists():
            token_file.unlink()
        return True
    except Exception as e:
        print(f"Error deleting autodl token: {e}")
        return False

