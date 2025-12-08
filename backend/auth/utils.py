"""
AutoDL Flow - 认证工具函数
"""
import json
import bcrypt
from backend.config import ACCOUNTS_FILE


def hash_password(password):
    """使用 bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, hashed):
    """验证密码是否匹配哈希值"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def get_all_accounts():
    """从 .accounts.json 文件获取所有账户信息（密码为哈希值）"""
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
                return accounts
        except Exception:
            pass
    
    # 如果文件不存在，创建默认账户
    default_accounts = {
        'admin': hash_password('admin12345')
    }
    save_accounts(default_accounts)
    return default_accounts


def save_accounts(accounts):
    """保存账户配置到 .accounts.json 文件"""
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving accounts: {e}")
        return False


def verify_account(username, password):
    """验证账户用户名和密码（使用哈希验证）"""
    accounts = get_all_accounts()
    if username not in accounts:
        return False
    hashed_password = accounts[username]
    return verify_password(password, hashed_password)


def is_admin(username):
    """检查是否为 admin 账户"""
    return username == 'admin'

