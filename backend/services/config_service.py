"""
AutoDL Flow - 配置管理服务
"""
import json
from pathlib import Path
from backend.config import CONFIG_FILE, CATEGORY_GROUPS_FILE
from backend.utils.storage import get_user_config_file
from backend.auth.utils import is_admin
from .category_service import CategoryService


class ConfigService:
    """配置管理服务"""
    
    def __init__(self):
        self.category_service = CategoryService()
    
    def load_user_config(self, username):
        """从用户配置文件加载配置"""
        user_config_file = get_user_config_file(username)
        
        # 合并全局和用户自己的类别映射组
        global_category_groups = self.category_service.load_category_groups()
        user_category_groups = self.category_service.load_user_category_groups(username)
        # 合并并去重
        all_category_groups = list(dict.fromkeys(global_category_groups + user_category_groups))
        
        if user_config_file.exists():
            try:
                with open(user_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return (config.get('repos', {}), 
                           config.get('data_download', {}),
                           all_category_groups,  # 合并后的类别映射组
                           config.get('models', {}),
                           config.get('bdnd_config', {}))
            except Exception as e:
                print(f"Warning: Failed to load user config file: {e}")
        
        # 如果是 admin，尝试加载全局配置
        if is_admin(username) and CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return (config.get('repos', {}), 
                           config.get('data_download', {}),
                           all_category_groups,  # 合并后的类别映射组
                           config.get('models', {}),
                           config.get('bdnd_config', {}))
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
        
        # 返回空配置（不使用默认值）
        return {}, {}, all_category_groups, {}, {}
    
    def save_user_config(self, username, repos=None, data_download=None, 
                         category_groups=None, models=None, bdnd_config=None):
        """保存用户配置到文件"""
        user_config_file = get_user_config_file(username)
        
        # 加载现有配置
        existing_repos, existing_data_download, existing_category_groups, existing_models, existing_bdnd_config = self.load_user_config(username)
        
        # 如果传入了 category_groups，保存到全局配置文件（仅管理员可修改全局的）
        if category_groups is not None:
            if not is_admin(username):
                return False  # 只有管理员可以修改全局类别映射组
            if not self.category_service.save_category_groups(category_groups):
                return False
        
        # 完全替换配置（而不是更新），这样可以正确删除项目
        if repos is not None:
            existing_repos = repos  # 完全替换
        if data_download is not None:
            existing_data_download = data_download  # 完全替换
        if models is not None:
            existing_models = models  # 完全替换
        if bdnd_config is not None:
            existing_bdnd_config = bdnd_config  # 完全替换
        
        # 保存用户配置（保留用户自己的类别映射组）
        config = {
            'repos': existing_repos,
            'data_download': existing_data_download,
            'models': existing_models,
            'bdnd_config': existing_bdnd_config
        }
        
        # 保留用户自己的类别映射组
        user_category_groups = self.category_service.load_user_category_groups(username)
        if user_category_groups:
            config['user_category_groups'] = user_category_groups
        
        try:
            with open(user_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving user config: {e}")
            return False

