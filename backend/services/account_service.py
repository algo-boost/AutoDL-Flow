"""
AutoDL Flow - 账户管理服务
"""
from backend.auth.utils import (
    get_all_accounts,
    save_accounts,
    hash_password,
    verify_password
)


class AccountService:
    """账户管理服务"""
    
    def get_all_accounts(self):
        """获取所有账户"""
        return get_all_accounts()
    
    def save_accounts(self, accounts):
        """保存账户配置"""
        return save_accounts(accounts)
    
    def add_account(self, username, password):
        """添加新账户"""
        accounts = self.get_all_accounts()
        if username in accounts:
            return False, "账户已存在"
        
        accounts[username] = hash_password(password)
        if self.save_accounts(accounts):
            return True, "账户添加成功"
        return False, "保存账户失败"
    
    def delete_account(self, username):
        """删除账户"""
        if username == 'admin':
            return False, "不能删除 admin 账户"
        
        accounts = self.get_all_accounts()
        if username not in accounts:
            return False, "账户不存在"
        
        del accounts[username]
        if self.save_accounts(accounts):
            return True, "账户删除成功"
        return False, "保存账户失败"
    
    def reset_password(self, username, new_password):
        """重置账户密码"""
        accounts = self.get_all_accounts()
        if username not in accounts:
            return False, "账户不存在"
        
        accounts[username] = hash_password(new_password)
        if self.save_accounts(accounts):
            return True, "密码重置成功"
        return False, "保存账户失败"

