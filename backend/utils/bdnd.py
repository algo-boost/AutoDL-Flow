"""
AutoDL Flow - 百度网盘工具函数
"""
import os
from backend.services.config_service import ConfigService
from backend.utils.encryption import decrypt_token


def get_baidu_netdisk_access_token(username=None):
    """
    获取百度网盘访问令牌
    
    优先级：
    1. 环境变量 baidu_netdisk_access_token
    2. env_key_manager（如果可用）
    3. 用户配置中的加密令牌（bdnd_config）
    
    Args:
        username: 用户名，如果提供则从用户配置中获取
        
    Returns:
        str: 访问令牌，如果不存在则返回 None
    """
    # 1. 优先从环境变量获取
    access_token = os.environ.get('baidu_netdisk_access_token')
    if access_token:
        return access_token
    
    # 2. 尝试从 env_key_manager 获取（如果可用）
    try:
        from env_key_manager import APIKeyManager
        key_manager = APIKeyManager()
        key_manager.setup_api_key(["baidu_netdisk_access_token",])
        access_token = key_manager.get_api_key("baidu_netdisk_access_token")
        if access_token:
            return access_token
    except (ImportError, Exception):
        pass
    
    # 3. 从用户配置中获取（如果提供了用户名）
    if username:
        try:
            config_service = ConfigService()
            _, _, _, _, bdnd_config = config_service.load_user_config(username)
            
            if bdnd_config:
                # 尝试从加密的令牌中获取
                encrypted_token = bdnd_config.get('encrypted_baidu_netdisk_access_token')
                if encrypted_token:
                    # 如果有加密密钥，使用它解密；否则使用默认加密器
                    encryption_key = bdnd_config.get('baidu_netdisk_access_token_encryption_key')
                    if encryption_key:
                        # 使用配置中的加密密钥解密
                        try:
                            from cryptography.fernet import Fernet
                            cipher = Fernet(encryption_key.encode())
                            access_token = cipher.decrypt(encrypted_token.encode()).decode()
                            if access_token:
                                return access_token
                        except Exception as e:
                            print(f"Warning: Failed to decrypt token with config key: {e}")
                    
                    # 如果配置密钥解密失败，尝试使用默认加密器
                    access_token = decrypt_token(encrypted_token)
                    if access_token:
                        return access_token
                
                # 尝试直接获取未加密的令牌（向后兼容）
                access_token = bdnd_config.get('baidu_netdisk_access_token')
                if access_token:
                    return access_token
        except Exception as e:
            print(f"Warning: Failed to get access token from user config: {e}")
    
    return None

