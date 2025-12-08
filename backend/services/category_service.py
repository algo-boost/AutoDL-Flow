"""
AutoDL Flow - 类别映射组服务
"""
import json
from backend.config import CATEGORY_GROUPS_FILE
from backend.utils.storage import get_user_config_file


class CategoryService:
    """类别映射组管理服务"""
    
    def load_category_groups(self):
        """加载全局共享的类别映射组"""
        if CATEGORY_GROUPS_FILE.exists():
            try:
                with open(CATEGORY_GROUPS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load category groups file: {e}")
        
        # 如果文件不存在，返回空列表
        return []
    
    def save_category_groups(self, category_groups):
        """保存全局共享的类别映射组"""
        try:
            with open(CATEGORY_GROUPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(category_groups, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving category groups: {e}")
            return False
    
    def load_user_category_groups(self, username):
        """加载用户自己的类别映射组"""
        user_config_file = get_user_config_file(username)
        
        if user_config_file.exists():
            try:
                with open(user_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('user_category_groups', [])
            except Exception as e:
                print(f"Warning: Failed to load user category groups: {e}")
        
        return []
    
    def save_user_category_groups(self, username, category_groups):
        """保存用户自己的类别映射组"""
        user_config_file = get_user_config_file(username)
        
        # 加载现有配置
        if user_config_file.exists():
            try:
                with open(user_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        else:
            config = {}
        
        # 更新用户类别映射组
        config['user_category_groups'] = category_groups
        
        # 保存配置
        try:
            with open(user_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving user category groups: {e}")
            return False

