#!/usr/bin/env python3
"""
Flask Web工具：自动生成作业执行脚本
"""

from flask import Flask, render_template, request, jsonify, send_file, url_for, session, redirect, url_for as flask_url_for
from pathlib import Path
import json
import os
import tempfile
import sys
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import hmac
import time
import bcrypt
from bdnd import BaiduNetdiskClient
import stat

# 尝试导入加密库
try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("Warning: cryptography library not installed. Token encryption will be disabled.")

# 尝试导入 autodl-api 库
try:
    from autodl import AutoDLElasticDeployment
    AUTODL_AVAILABLE = True
except ImportError:
    AUTODL_AVAILABLE = False
    print("Warning: autodl-api library not installed. Task submission features will be limited.")

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-this-secret-key-in-production-' + str(os.urandom(16)))

# 加载配置文件
CONFIG_FILE = Path(__file__).parent / 'repos_config.json'
# 账户配置文件
ACCOUNTS_FILE = Path(__file__).parent / '.accounts.json'
# 全局共享的类别映射组配置文件
CATEGORY_GROUPS_FILE = Path(__file__).parent / '.category_groups.json'
# 加密密钥文件
ENCRYPTION_KEY_FILE = Path(__file__).parent / '.encryption_key'
# 运行脚本模板配置文件
RUN_SCRIPT_TEMPLATES_FILE = Path(__file__).parent / 'run_script_templates.json'

# 数据中心映射（中文名称 -> 英文编号）
DATACENTER_MAPPING = {
    "西北企业区(推荐)": "westDC2",
    "西北B区": "westDC3",
    "北京A区": "beijingDC1",
    "北京B区": "beijingDC2",
    "L20专区(原北京C区)": "beijingDC4",
    "V100专区(原华南A区)": "beijingDC3",
    "内蒙A区": "neimengDC1",
    "佛山区": "foshanDC1",
    "重庆A区": "chongqingDC1",
    "3090专区": "yangzhouDC1",
    "内蒙B区": "neimengDC3"
}

# 脚本存储目录（服务器本地）
SCRIPTS_STORAGE_DIR = Path('/root/autodl_scripts_storage')
SCRIPTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# 配置存储目录（服务器本地）
CONFIGS_STORAGE_DIR = Path('/root/autodl_configs_storage')
CONFIGS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# 临时脚本存储目录（用于运行脚本，1小时后删除）
TEMP_SCRIPTS_DIR = Path('/root/autodl_temp_scripts_storage')
TEMP_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# 任务提交配置存储目录
DEPLOYMENT_CONFIGS_DIR = Path('/root/autodl_deployment_configs_storage')
DEPLOYMENT_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

# 提交记录存储目录
DEPLOYMENT_RECORDS_DIR = Path('/root/autodl_deployment_records_storage')
DEPLOYMENT_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

# 百度网盘脚本目录
BAIDU_NETDISK_SCRIPTS_DIR = '/apps/autodl/scripts'

# 临时下载token存储
download_tokens = {}

# 数据中心映射（中文名称 -> 英文编号）
DATACENTER_MAPPING = {
    "西北企业区": "westDC2",
    "西北B区": "westDC3",
    "北京A区": "beijingDC1",
    "北京B区": "beijingDC2",
    "L20专区": "beijingDC4",
    "V100专区": "beijingDC3",
    "内蒙A区": "neimengDC1",
    "佛山区": "foshanDC1",
    "重庆A区": "chongqingDC1",
    "3090专区": "yangzhouDC1",
    "内蒙B区": "neimengDC3"
}

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 密码哈希函数
def hash_password(password):
    """使用 bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """验证密码是否匹配哈希值"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# 获取所有账户配置
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

# 保存账户配置
def save_accounts(accounts):
    """保存账户配置到 .accounts.json 文件"""
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving accounts: {e}")
        return False

# 验证账户
def verify_account(username, password):
    """验证账户用户名和密码（使用哈希验证）"""
    accounts = get_all_accounts()
    if username not in accounts:
        return False
    hashed_password = accounts[username]
    return verify_password(password, hashed_password)

# 检查是否为 admin 账户
def is_admin(username):
    """检查是否为 admin 账户"""
    return username == 'admin'

# 获取用户存储目录
def get_user_storage_dir(base_dir, username):
    """获取用户的存储目录，admin 使用根目录，其他用户使用子目录"""
    if is_admin(username):
        return base_dir
    else:
        user_dir = base_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

# 获取用户可访问的所有目录（admin 可以访问所有）
def get_accessible_dirs(base_dir, username):
    """获取用户可访问的所有目录列表"""
    if is_admin(username):
        # admin 可以访问所有用户的目录
        dirs = [base_dir]  # 根目录（可能包含旧数据）
        if base_dir.exists():
            for item in base_dir.iterdir():
                if item.is_dir() and item.name != 'admin':
                    dirs.append(item)
        return dirs
    else:
        # 普通用户只能访问自己的目录
        user_dir = base_dir / username
        return [user_dir] if user_dir.exists() else []

# 生成临时下载token
def generate_download_token(filename):
    """生成临时下载token"""
    token = hashlib.sha256(f"{filename}{time.time()}{os.urandom(16)}".encode()).hexdigest()
    # token有效期1小时
    download_tokens[token] = {
        'filename': filename,
        'expires_at': datetime.now() + timedelta(hours=1)
    }
    return token

# 验证下载token
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

def get_user_config_file(username):
    """获取用户的配置文件路径"""
    if is_admin(username):
        # admin 使用全局配置文件
        return CONFIG_FILE
    else:
        # 普通用户使用自己的配置文件
        user_config_dir = CONFIGS_STORAGE_DIR / username
        user_config_dir.mkdir(parents=True, exist_ok=True)
        return user_config_dir / 'user_config.json'

def cleanup_old_temp_scripts():
    """清理超过1小时的临时脚本文件"""
    try:
        import time
        current_time = time.time()
        deleted_count = 0
        
        if not TEMP_SCRIPTS_DIR.exists():
            return
        
        # 遍历所有用户目录
        for user_dir in TEMP_SCRIPTS_DIR.iterdir():
            if user_dir.is_dir():
                # 遍历该用户的所有临时脚本文件
                for script_file in user_dir.glob('run_*'):
                    try:
                        # 检查文件修改时间
                        file_mtime = script_file.stat().st_mtime
                        # 如果文件创建超过1小时（3600秒），删除它
                        if current_time - file_mtime > 3600:
                            script_file.unlink()
                            deleted_count += 1
                            print(f"Deleted old temp script: {script_file}")
                    except Exception as e:
                        print(f"Error deleting temp script {script_file}: {e}")
                        continue
        
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} old temp scripts")
    except Exception as e:
        print(f"Error in cleanup_old_temp_scripts: {e}")

def get_user_deployment_config_dir(username):
    """获取用户的任务提交配置目录"""
    if is_admin(username):
        user_config_dir = DEPLOYMENT_CONFIGS_DIR / 'admin'
    else:
        user_config_dir = DEPLOYMENT_CONFIGS_DIR / username
    user_config_dir.mkdir(parents=True, exist_ok=True)
    return user_config_dir

def get_user_deployment_records_dir(username):
    """获取用户的提交记录目录"""
    if is_admin(username):
        user_records_dir = DEPLOYMENT_RECORDS_DIR / 'admin'
    else:
        user_records_dir = DEPLOYMENT_RECORDS_DIR / username
    user_records_dir.mkdir(parents=True, exist_ok=True)
    return user_records_dir

def save_deployment_record(username, record_data):
    """保存提交记录"""
    try:
        records_dir = get_user_deployment_records_dir(username)
        
        # 生成记录文件名（使用时间戳）
        now = datetime.now()
        record_name = f"deployment_record_{now.strftime('%Y%m%d_%H%M%S')}.json"
        record_file = records_dir / record_name
        
        # 保存记录
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(record_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Deployment record saved: {record_file}")
        return True
    except Exception as e:
        print(f"Error saving deployment record: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_deployment_config(username, config_data, group=None):
    """保存任务提交配置"""
    try:
        config_dir = get_user_deployment_config_dir(username)
        
        # 如果指定了分组，在分组目录下保存
        if group and group.strip():
            group_dir = config_dir / group.strip()
            group_dir.mkdir(parents=True, exist_ok=True)
            config_dir = group_dir
        
        # 生成配置文件名（使用时间戳）
        now = datetime.now()
        config_name = f"deployment_config_{now.strftime('%Y%m%d_%H%M%S')}.json"
        config_file = config_dir / config_name
        
        # 在配置数据中添加分组信息
        if group and group.strip():
            config_data['group'] = group.strip()
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Deployment config saved: {config_file}")
        return True
    except Exception as e:
        print(f"Error saving deployment config: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_user_env_config_file(username):
    """获取用户的 .env_config.json 文件路径"""
    user_config_dir = get_user_storage_dir(CONFIGS_STORAGE_DIR, username)
    return user_config_dir / '.env_config.json'

# ==================== Token 加密存储功能 ====================

def get_encryption_key():
    """获取加密密钥，如果不存在则生成"""
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
    
    try:
        if ENCRYPTION_KEY_FILE.exists():
            with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                key = f.read()
        else:
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

def load_category_groups():
    """加载全局共享的类别映射组"""
    if CATEGORY_GROUPS_FILE.exists():
        try:
            with open(CATEGORY_GROUPS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load category groups file: {e}")
    
    # 如果文件不存在，返回空列表
    return []

def save_category_groups(category_groups):
    """保存全局共享的类别映射组"""
    try:
        with open(CATEGORY_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(category_groups, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving category groups: {e}")
        return False

def load_user_category_groups(username):
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

def save_user_category_groups(username, category_groups):
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

def load_user_config(username):
    """从用户配置文件加载配置"""
    user_config_file = get_user_config_file(username)
    
    # 合并全局和用户自己的类别映射组
    global_category_groups = load_category_groups()
    user_category_groups = load_user_category_groups(username)
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

def save_user_config(username, repos=None, data_download=None, category_groups=None, models=None, bdnd_config=None):
    """保存用户配置到文件"""
    user_config_file = get_user_config_file(username)
    
    # 加载现有配置
    existing_repos, existing_data_download, existing_category_groups, existing_models, existing_bdnd_config = load_user_config(username)
    
    # 如果传入了 category_groups，保存到全局配置文件（仅管理员可修改全局的）
    if category_groups is not None:
        if not is_admin(username):
            return False  # 只有管理员可以修改全局类别映射组
        if not save_category_groups(category_groups):
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
    user_category_groups = load_user_category_groups(username)
    if user_category_groups:
        config['user_category_groups'] = user_category_groups
    
    try:
        with open(user_config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving user config: {e}")
        return False

# 全局配置变量（将在 index 路由中按用户加载）
REPOS, DATA_DOWNLOAD_CONFIG, CATEGORY_GROUPS, MODELS, BDND_CONFIG = {}, {}, [], {}, {}


def generate_script(selected_repos, snapshots, output_dir, dataset_name, split_ratio=None, split_seed=42, data_only=False, 
                   enable_repos=True, enable_snapshots=True, enable_merge=True, category_group=None, 
                   selected_models=None, username='admin'):
    """生成执行脚本"""
    script = """#!/usr/bin/env bash

set -e         
set -u         
set -o pipefail 

# 颜色输出
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
RED='\\033[0;31m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# 输出函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\\n${YELLOW}==>${NC} $1"
}

error_exit() {
    log_error "脚本执行失败于第 $1 行"
    exit 1
}

pip install --upgrade pip
pip install bdnd -i https://pypi.org/simple

trap 'error_exit $LINENO' ERR

# 配置 bdnd
log_info "配置 bdnd..."
OUTFILE="$HOME/.env_config.json"
mkdir -p "$(dirname "$OUTFILE")"
rm -f "$OUTFILE"

cat > "$OUTFILE" << 'EOF'
{env_config_json}
EOF

log_success "bdnd 配置完成"

"""
    
    # 如果选择了仓库，需要配置 git
    if enable_repos and not data_only and selected_repos:
        # 获取Git SSH路径配置
        git_ssh_path = DATA_DOWNLOAD_CONFIG.get('git_ssh_path', '')
        script += f"""
# 配置 Git SSH
log_info "配置 Git SSH..."
cd $HOME
rm -rf .ssh .gitconfig
# 优先从 autodl-fs 读取 Git SSH 配置
GIT_SSH_PATH="{git_ssh_path}"
if [ -n "$GIT_SSH_PATH" ] && [ -d "/root/autodl-fs/$GIT_SSH_PATH" ]; then
    log_info "从 autodl-fs 复制 Git SSH 配置: $GIT_SSH_PATH"
    cp -r "/root/autodl-fs/$GIT_SSH_PATH/.ssh" "$HOME/" 2>/dev/null || true
    cp "/root/autodl-fs/$GIT_SSH_PATH/.gitconfig" "$HOME/" 2>/dev/null || true
    if [ -d "$HOME/.ssh" ] && [ -f "$HOME/.ssh/id_rsa" ]; then
        log_success "从 autodl-fs 复制 Git SSH 配置完成"
    else
        log_info "autodl-fs 中未找到完整的 Git SSH 配置，从百度网盘下载..."
        bdnd /apps/autodl/git_ssh_backup .
    fi
else
    log_info "从百度网盘下载 Git SSH 配置..."
    bdnd /apps/autodl/git_ssh_backup .
fi
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/id_rsa
chmod 600 $HOME/.ssh/id_*
log_success "Git SSH 配置完成"

log_info "开始安装包..."
echo "========================================"

cd /root
log_success "当前目录: $(pwd)"

"""
        
        # 克隆和安装代码仓库
        for repo_data in selected_repos:
            repo_name = repo_data['name']
            should_install = repo_data.get('install', False)
            repo = REPOS.get(repo_name, {})
            
            if not repo:
                continue
            
            script += f"""
# 克隆 {repo_name}
log_step "克隆 {repo_name} 仓库"
if [ -d "{repo_name}" ]; then
    log_info "{repo_name} 目录已存在，删除旧目录"
    rm -rf {repo_name}
fi
git clone {repo.get('url', '')}
log_success "{repo_name} 克隆完成"
"""
            if should_install and repo.get('install_cmds'):
                script += f"""
# 安装 {repo_name}
log_step "安装 {repo_name}"
cd /root/{repo_name}
log_info "当前目录: $(pwd)"
"""
                for cmd in repo['install_cmds']:
                    script += f"{cmd}\n"
                script += f"""
log_success "{repo_name} 安装完成"
cd /root
"""
        
        script += """
echo "========================================"
log_success "所有包安装完成！"
"""
    
    # 如果启用了快照下载，需要先下载数据下载脚本
    if enable_snapshots:
        script += """
# 下载数据下载脚本
log_step "下载数据下载脚本..."
"""
        script += f"bdnd --mode download {DATA_DOWNLOAD_CONFIG.get('script_remote_path', '/apps/autodl/dataset_down/')} {DATA_DOWNLOAD_CONFIG.get('script_local_path', '/root/dataset_down/')}\n"
        script += f"cd {DATA_DOWNLOAD_CONFIG.get('script_local_path', '/root/dataset_down/').rstrip('/')}\n"
    
    if enable_snapshots:
        script += """
# 下载数据集快照
log_step "下载数据集快照..."
"""
        
        # 下载数据快照
        for snapshot_data in snapshots:
            if isinstance(snapshot_data, tuple):
                snapshot_id, snapshot_name = snapshot_data
                snapshot_url = ''
                enable_cache = True  # 默认启用缓存
            else:
                snapshot_id = snapshot_data.get('id', '')
                snapshot_url = snapshot_data.get('url', '')
                snapshot_bdnd_path = snapshot_data.get('bdnd_path', '')
                snapshot_name = snapshot_data.get('name', '')
                enable_cache = snapshot_data.get('cache', True)  # 默认启用缓存
            
            # 确定下载方式：优先级：快照ID > 百度网盘 > URL
            use_id = bool(snapshot_id and snapshot_id.strip())
            use_bdnd = bool(snapshot_bdnd_path and snapshot_bdnd_path.strip()) and not use_id
            use_url = bool(snapshot_url and snapshot_url.strip()) and not use_id and not use_bdnd
            
            # 确定快照名称
            if snapshot_name:
                name = snapshot_name
            elif use_id:
                name = f"snapshot_{snapshot_id}"
            elif use_bdnd:
                # 从百度网盘路径中提取文件名作为默认名称
                bdnd_path = snapshot_bdnd_path.rstrip('/')
                bdnd_filename = os.path.basename(bdnd_path)
                if bdnd_filename:
                    # 如果是压缩包，去掉扩展名
                    if bdnd_filename.endswith('.zip'):
                        name = os.path.splitext(bdnd_filename)[0]
                    else:
                        name = bdnd_filename
                else:
                    name = f"snapshot_bdnd_{hash(snapshot_bdnd_path) % 10000}"
            elif use_url:
                # 从URL中提取文件名作为默认名称
                from urllib.parse import urlparse
                parsed_url = urlparse(snapshot_url)
                url_filename = os.path.basename(parsed_url.path)
                if url_filename and '.' in url_filename:
                    name = os.path.splitext(url_filename)[0]
                else:
                    name = f"snapshot_url_{hash(snapshot_url) % 10000}"
            else:
                # 默认情况（理论上不应该到达这里）
                name = f"snapshot_unknown"
            
            # 使用配置的缓存路径，默认为 cache/datasets
            cache_path = DATA_DOWNLOAD_CONFIG.get('dataset_cache_path', 'cache/datasets')
            fs_snapshot_path = f"/root/autodl-fs/{cache_path}/{name}"
            tmp_snapshot_path = f"/root/autodl-tmp/{name}"
            
            script += f"""
log_info "处理快照 {name}"
# 先检查 autodl-fs 缓存目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -d "{fs_snapshot_path}" ]; then
    log_info "在 autodl-fs 缓存中找到快照 {name}，直接复制..."
    mkdir -p "$(dirname "{tmp_snapshot_path}")"
    # 如果目标目录已存在，先删除
    if [ -d "{tmp_snapshot_path}" ]; then
        log_info "目标目录已存在，删除旧目录"
        rm -rf "{tmp_snapshot_path}"
    fi
    cp -r "{fs_snapshot_path}" "{tmp_snapshot_path}"
    log_success "快照 {name} 复制完成"
else
    log_info "autodl-fs 缓存中未找到快照 {name}，开始下载..."
"""
            if use_id:
                # 使用ID下载（优先级最高）
                cmd = f"python moli_dataset_export.py {snapshot_id} --output-dir /root/autodl-tmp/ --dir-name {name}"
                if category_group:
                    cmd += f' --category-group "{category_group}"'
                
                script += f"""    {cmd}
    log_success "快照 {name} 下载完成"
"""
            elif use_bdnd:
                # 使用百度网盘下载（优先级第二）
                bdnd_path = snapshot_bdnd_path.rstrip('/')
                is_zip = bdnd_path.endswith('.zip')
                
                script += f"""    mkdir -p "{tmp_snapshot_path}"
    cd "{tmp_snapshot_path}"
    
    log_info "从百度网盘下载: {bdnd_path}"
    bdnd --mode download {bdnd_path} .
    
    if [ $? -ne 0 ]; then
        log_error "从百度网盘下载失败"
        exit 1
    fi
    
"""
                if is_zip:
                    # 如果是压缩包，需要解压
                    zip_filename = os.path.basename(bdnd_path)
                    script += f"""    log_info "下载完成，开始解压: {zip_filename}"
    # 查找下载的zip文件（可能文件名不完全匹配）
    ZIP_FILE=$(find . -name "*.zip" -type f | head -n 1)
    if [ -z "$ZIP_FILE" ]; then
        # 如果没找到zip文件，尝试使用原始文件名
        if [ -f "{zip_filename}" ]; then
            ZIP_FILE="{zip_filename}"
        else
            log_error "未找到zip文件"
            exit 1
        fi
    fi
    
    log_info "解压文件: $ZIP_FILE"
    unzip -q "$ZIP_FILE" || {{
        log_error "解压 zip 文件失败"
        exit 1
    }}
    
    # 删除下载的压缩文件
    rm -f "$ZIP_FILE"
    log_success "快照 {name} 下载并解压完成"
"""
                else:
                    # 如果是目录，直接使用
                    script += f"""    log_success "快照 {name} 下载完成"
"""
            elif use_url:
                # 使用URL下载（优先级最低）
                script += f"""    mkdir -p "{tmp_snapshot_path}"
    cd "{tmp_snapshot_path}"
    # 从URL中提取文件名
    DOWNLOAD_URL="{snapshot_url}"
    FILENAME=$(basename "$DOWNLOAD_URL" | cut -d'?' -f1)
    if [ -z "$FILENAME" ] || [ "$FILENAME" = "/" ]; then
        FILENAME="dataset.zip"
    fi
    
    log_info "从URL下载: $DOWNLOAD_URL"
    # 使用 wget 下载
    wget -q --show-progress -O "$FILENAME" "$DOWNLOAD_URL" || {{
        log_error "wget 下载失败，尝试使用 curl..."
        curl -L -o "$FILENAME" "$DOWNLOAD_URL" || {{
            log_error "快照 {name} 下载失败"
            exit 1
        }}
    }}
    
    log_info "下载完成，开始解压: $FILENAME"
    # 根据文件扩展名选择解压方式
    if [[ "$FILENAME" == *.zip ]]; then
        unzip -q "$FILENAME" || {{
            log_error "解压 zip 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar.gz ]] || [[ "$FILENAME" == *.tgz ]]; then
        tar -xzf "$FILENAME" || {{
            log_error "解压 tar.gz 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar ]]; then
        tar -xf "$FILENAME" || {{
            log_error "解压 tar 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar.bz2 ]]; then
        tar -xjf "$FILENAME" || {{
            log_error "解压 tar.bz2 文件失败"
            exit 1
        }}
    else
        log_info "文件不是压缩格式，保持原样"
    fi
    
    # 删除下载的压缩文件
    rm -f "$FILENAME"
    log_success "快照 {name} 下载并解压完成"
"""
            else:
                # 默认情况（理论上不应该到达这里，因为至少应该有一个下载方式）
                script += f"""    log_error "未指定有效的下载方式（ID、百度网盘路径或URL）"
    exit 1
"""
            
            # 只有启用缓存时，才保存到 autodl-fs
            if enable_cache:
                script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs 缓存目录
    if [ ! -d "{fs_snapshot_path}" ] && [ -d "{tmp_snapshot_path}" ]; then
        log_info "缓存快照 {name} 到 autodl-fs 缓存目录..."
        mkdir -p "$(dirname "{fs_snapshot_path}")"
        cp -r "{tmp_snapshot_path}" "{fs_snapshot_path}"
        log_success "快照 {name} 已缓存到 autodl-fs 缓存目录"
    fi
"""
            else:
                script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
            script += "fi\n"
    
    # 如果选择了模型，下载模型文件
    if selected_models:
        script += """
# 下载模型
log_step "下载模型..."
mkdir -p /root/autodl-tmp/model
"""
        for model_item in selected_models:
            # 支持两种格式：字符串（模型名称）或字典（包含名称和选项）
            if isinstance(model_item, dict):
                model_name = model_item.get('name', '')
                enable_cache = model_item.get('cache', True)  # 默认启用缓存
            else:
                model_name = model_item
                enable_cache = True  # 默认启用缓存
            
            model_config = MODELS.get(model_name, {})
            if model_config:
                # 检查是否有 URL 配置（优先使用 URL 下载）
                download_url = model_config.get('url', '')
                local_path = model_config.get('local_path', '')
                
                # 准备 autodl-fs 路径（统一缓存到 cache 目录）
                fs_model_path = f"/root/autodl-fs/cache/models/{model_name}"
                
                if download_url and local_path:
                    # 使用 URL 下载
                    filename = model_config.get('filename', '')
                    if not filename:
                        # 从 URL 中提取文件名
                        from urllib.parse import urlparse
                        parsed_url = urlparse(download_url)
                        filename = os.path.basename(parsed_url.path)
                        if not filename or '.' not in filename:
                            # 如果无法从 URL 提取，使用默认名称
                            filename = f"{model_name}.pth"
                    
                    fs_model_file = f"{fs_model_path}/{filename}"
                    
                    script += f"""
log_info "处理模型 {model_name}..."
mkdir -p {local_path}
# 先检查 autodl-fs 目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -f "{fs_model_file}" ]; then
    log_info "在 autodl-fs 中找到模型文件，直接复制..."
    cp "{fs_model_file}" "{local_path}/{filename}"
    log_success "{model_name} 模型复制完成: {filename}"
elif [ -d "{fs_model_path}" ] && [ "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
    log_info "在 autodl-fs 中找到模型目录，复制所有文件..."
    cp -r {fs_model_path}/* {local_path}/
    log_success "{model_name} 模型复制完成"
else
    log_info "autodl-fs 中未找到模型 {model_name}，从 URL 下载..."
    cd {local_path}
    # 如果文件已存在，先删除
    if [ -f "{filename}" ]; then
        log_info "文件 {filename} 已存在，删除旧文件"
        rm -f "{filename}"
    fi
    # 使用 wget 下载
    wget -q --show-progress -O "{filename}" "{download_url}" || {{
        log_error "下载失败，尝试使用 curl..."
        curl -L -o "{filename}" "{download_url}" || {{
            log_error "模型 {model_name} 下载失败"
            exit 1
        }}
    }}
    log_success "{model_name} 模型下载完成: {filename}"
"""
                    # 只有启用缓存时，才保存到 autodl-fs
                    if enable_cache:
                        script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs
    if [ ! -f "{fs_model_file}" ] && [ -f "{local_path}/{filename}" ]; then
        log_info "缓存模型 {model_name} 到 autodl-fs..."
        mkdir -p "{fs_model_path}"
        cp "{local_path}/{filename}" "{fs_model_file}"
        log_success "模型 {model_name} 已缓存到 autodl-fs"
    fi
"""
                    else:
                        script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
                    script += "fi\n"
                else:
                    # 使用百度网盘下载（原有方式）
                    remote_path = model_config.get('remote_path', '')
                    if remote_path and local_path:
                        script += f"""
log_info "处理模型 {model_name}..."
mkdir -p {local_path}
# 先检查 autodl-fs 目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -d "{fs_model_path}" ] && [ "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
    log_info "在 autodl-fs 中找到模型目录，直接复制..."
    # 如果目标目录已存在，先删除
    if [ -d "{local_path}" ] && [ "$(ls -A {local_path} 2>/dev/null)" ]; then
        log_info "目标目录已有文件，删除旧文件"
        rm -rf {local_path}/*
    fi
    cp -r {fs_model_path}/* {local_path}/
    log_success "{model_name} 模型复制完成"
else
    log_info "autodl-fs 中未找到模型 {model_name}，从百度网盘下载..."
    cd {local_path}
    bdnd --mode download {remote_path} .
    log_success "{model_name} 模型下载完成"
"""
                        # 只有启用缓存时，才保存到 autodl-fs
                        if enable_cache:
                            script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs
    if [ ! -d "{fs_model_path}" ] || [ -z "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
        if [ -d "{local_path}" ] && [ "$(ls -A {local_path} 2>/dev/null)" ]; then
            log_info "缓存模型 {model_name} 到 autodl-fs..."
            mkdir -p "{fs_model_path}"
            cp -r {local_path}/* {fs_model_path}/
            log_success "模型 {model_name} 已缓存到 autodl-fs"
        fi
    fi
"""
                        else:
                            script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
                        script += "fi\n"
        script += """
log_success "所有模型下载完成！"
"""
    
    if enable_merge:
        # 检查是否已经选择了 cv_scripts 仓库，如果没有则需要克隆
        has_cv_scripts = False
        if enable_repos and not data_only and selected_repos:
            for repo_data in selected_repos:
                if repo_data['name'] == 'cv_scripts':
                    has_cv_scripts = True
                    break
        
        if not has_cv_scripts:
            # 需要先克隆 cv-scripts 仓库
            cv_scripts_repo = REPOS.get('cv-scripts', {})
            if cv_scripts_repo:
                # 如果没有配置 Git SSH，需要先配置
                needs_git_config = not (enable_repos and not data_only and selected_repos)
                if needs_git_config:
                    # 获取Git SSH路径配置
                    git_ssh_path = DATA_DOWNLOAD_CONFIG.get('git_ssh_path', '')
                    script += f"""
# 配置 Git SSH（数据集生成需要克隆 cv-scripts）
log_info "配置 Git SSH..."
cd $HOME
rm -rf .ssh .gitconfig
# 优先从 autodl-fs 读取 Git SSH 配置
GIT_SSH_PATH="{git_ssh_path}"
if [ -n "$GIT_SSH_PATH" ] && [ -d "/root/autodl-fs/$GIT_SSH_PATH" ]; then
    log_info "从 autodl-fs 复制 Git SSH 配置: $GIT_SSH_PATH"
    cp -r "/root/autodl-fs/$GIT_SSH_PATH/.ssh" "$HOME/" 2>/dev/null || true
    cp "/root/autodl-fs/$GIT_SSH_PATH/.gitconfig" "$HOME/" 2>/dev/null || true
    if [ -d "$HOME/.ssh" ] && [ -f "$HOME/.ssh/id_rsa" ]; then
        log_success "从 autodl-fs 复制 Git SSH 配置完成"
    else
        log_info "autodl-fs 中未找到完整的 Git SSH 配置，从百度网盘下载..."
        bdnd /apps/autodl/git_ssh_backup .
    fi
else
    log_info "从百度网盘下载 Git SSH 配置..."
    bdnd /apps/autodl/git_ssh_backup .
fi
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/id_rsa
chmod 600 $HOME/.ssh/id_*
log_success "Git SSH 配置完成"

cd /root
"""
                script += f"""
# 克隆 cv-scripts 仓库（数据集生成需要）
log_step "克隆 cv-scripts 仓库..."
if [ ! -d "/root/cv-scripts" ]; then
    git clone {cv_scripts_repo.get('url', '')}
    log_success "cv-scripts 克隆完成"
else
    log_info "cv-scripts 仓库已存在"
fi
"""
        
        script += f"""
cd /root/autodl-tmp

# 汇总数据集
log_step "汇总数据集..."
OUTPUT_DIR="{output_dir}"
DATASET_NAME="{dataset_name}"

# 检查 cv-scripts 仓库是否存在
if [ ! -d "/root/cv-scripts" ]; then
    log_error "cv-scripts 仓库不存在，请确保已克隆该仓库"
    exit 1
fi

MERGED_COCO_SCRIPT="/root/cv-scripts/dataset/merged_coco.py"
SPLIT_COCO_SCRIPT="/root/cv-scripts/dataset/split_coco.py"

if [ ! -f "$MERGED_COCO_SCRIPT" ]; then
    log_error "合并脚本不存在: $MERGED_COCO_SCRIPT"
    exit 1
fi

if [ ! -f "$SPLIT_COCO_SCRIPT" ]; then
    log_error "划分脚本不存在: $SPLIT_COCO_SCRIPT"
    exit 1
fi

# 安装必要的 Python 依赖
log_info "安装数据集处理所需的依赖..."
pip install tqdm -q
log_success "依赖安装完成"
"""
        
        # 收集所有快照目录名
        snapshot_names = []
        for snapshot_data in snapshots:
            if isinstance(snapshot_data, tuple):
                snapshot_id, snapshot_name = snapshot_data
            else:
                snapshot_id = snapshot_data.get('id', '')
                snapshot_name = snapshot_data.get('name', '')
            name = snapshot_name if snapshot_name else f"snapshot_{snapshot_id}"
            snapshot_names.append(name)
        
        if split_ratio:
            # 随机划分模式：先合并所有快照，然后随机划分
            script += f"""
# 随机划分模式
log_info "使用随机划分模式 (比例: {split_ratio})"

# 创建临时合并目录
TEMP_MERGED_DIR="/root/autodl-tmp/_temp_merged"
mkdir -p "$TEMP_MERGED_DIR"

# 收集所有需要合并的目录
INPUT_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}" ]; then
    # 如果有train目录，优先使用train目录
    if [ -d "/root/autodl-tmp/{name}/train" ] && [ -f "/root/autodl-tmp/{name}/train/_annotations.coco.json" ]; then
        INPUT_DIRS="$INPUT_DIRS /root/autodl-tmp/{name}/train"
    elif [ -f "/root/autodl-tmp/{name}/_annotations.coco.json" ]; then
        INPUT_DIRS="$INPUT_DIRS /root/autodl-tmp/{name}"
    fi
fi
"""
            script += f"""
if [ -z "$INPUT_DIRS" ]; then
    log_error "没有找到有效的快照目录"
    exit 1
fi

# 先合并所有数据集
log_info "合并所有数据集..."
python3 "$MERGED_COCO_SCRIPT" --input-dirs $INPUT_DIRS --output-dir "$TEMP_MERGED_DIR"
if [ $? -ne 0 ]; then
    log_error "合并数据集失败"
    exit 1
fi

# 然后随机划分
log_info "随机划分数据集 (随机种子: {split_seed})..."
mkdir -p "$OUTPUT_DIR/$DATASET_NAME"
python3 "$SPLIT_COCO_SCRIPT" "$TEMP_MERGED_DIR" "$OUTPUT_DIR/$DATASET_NAME" --ratio {split_ratio} --seed {split_seed}
if [ $? -ne 0 ]; then
    log_error "划分数据集失败"
    exit 1
fi

# 清理临时目录
rm -rf "$TEMP_MERGED_DIR"
log_success "数据集生成完成: $OUTPUT_DIR/$DATASET_NAME"
"""
        else:
            # 按目录汇总（train/valid）
            script += f"""
# 按目录汇总模式（train/valid）
log_info "使用目录汇总模式"

# 汇总训练集
TRAIN_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}/train" ] && [ -f "/root/autodl-tmp/{name}/train/_annotations.coco.json" ]; then
    TRAIN_DIRS="$TRAIN_DIRS /root/autodl-tmp/{name}/train"
fi
"""
            script += f"""
if [ -n "$TRAIN_DIRS" ]; then
    log_info "合并训练集..."
    mkdir -p "$OUTPUT_DIR/$DATASET_NAME/train"
    python3 "$MERGED_COCO_SCRIPT" --input-dirs $TRAIN_DIRS --output-dir "$OUTPUT_DIR/$DATASET_NAME/train"
    if [ $? -ne 0 ]; then
        log_error "合并训练集失败"
        exit 1
    fi
else
    log_info "未找到训练集目录"
fi

# 汇总验证集
VALID_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}/valid" ] && [ -f "/root/autodl-tmp/{name}/valid/_annotations.coco.json" ]; then
    VALID_DIRS="$VALID_DIRS /root/autodl-tmp/{name}/valid"
fi
"""
            script += f"""
if [ -n "$VALID_DIRS" ]; then
    log_info "合并验证集..."
    mkdir -p "$OUTPUT_DIR/$DATASET_NAME/valid"
    python3 "$MERGED_COCO_SCRIPT" --input-dirs $VALID_DIRS --output-dir "$OUTPUT_DIR/$DATASET_NAME/valid"
    if [ $? -ne 0 ]; then
        log_error "合并验证集失败"
        exit 1
    fi
else
    log_info "未找到验证集目录"
fi

log_success "数据集生成完成: $OUTPUT_DIR/$DATASET_NAME"
"""
    
    script += '\nlog_success "END"\n'
    
    # 读取用户自己的 .env_config.json 文件内容并嵌入到脚本中
    env_config_content = '{}'  # 默认空JSON
    env_config_file = get_user_env_config_file(username)
    if env_config_file.exists():
        try:
            with open(env_config_file, 'r', encoding='utf-8') as f:
                env_config_content = f.read().strip()
                # 验证JSON格式
                json.loads(env_config_content)
        except Exception as e:
            print(f"Warning: Failed to read or parse .env_config.json: {e}")
            env_config_content = '{}'
    
    # 将 JSON 内容压缩为单行（去除换行和多余空格）
    try:
        env_config_obj = json.loads(env_config_content)
        env_config_json = json.dumps(env_config_obj, separators=(',', ':'))
    except Exception:
        env_config_json = env_config_content
    
    # 替换占位符
    script = script.replace('{env_config_json}', env_config_json)
    
    return script


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if verify_account(username, password):
            session['logged_in'] = True
            session['username'] = username
            session['is_admin'] = is_admin(username)
            return redirect(flask_url_for('dashboard'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    # 如果已登录，重定向到主菜单
    if session.get('logged_in'):
        return redirect(flask_url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    """登出"""
    session.clear()
    return jsonify({'success': True})

@app.route('/')
def dashboard():
    """主菜单页面"""
    # 检查是否已登录
    if not session.get('logged_in'):
        return redirect(flask_url_for('login'))
    
    # 获取用户信息
    username = session.get('username', 'admin')
    
    return render_template('dashboard.html', username=username)

@app.route('/task_setup')
def task_setup():
    """任务设置页面（原 index 页面）"""
    # 检查是否已登录
    if not session.get('logged_in'):
        return redirect(flask_url_for('login'))
    
    # 获取用户信息
    username = session.get('username', 'admin')
    is_admin_user = session.get('is_admin', False)
    
    # 按用户加载配置（支持热更新）
    global REPOS, DATA_DOWNLOAD_CONFIG, CATEGORY_GROUPS, MODELS, BDND_CONFIG
    REPOS, DATA_DOWNLOAD_CONFIG, CATEGORY_GROUPS, MODELS, BDND_CONFIG = load_user_config(username)
    
    # category_groups 现在从 API 加载（全局共享），不再从模板传递
    return render_template('index.html', 
                         repos=REPOS, 
                         models=MODELS,
                         username=username,
                         is_admin=is_admin_user)

@app.route('/task_submit')
def task_submit():
    """任务提交页面"""
    # 检查是否已登录
    if not session.get('logged_in'):
        return redirect(flask_url_for('login'))
    
    username = session.get('username', 'admin')
    return render_template('task_submit.html', username=username, autodl_available=AUTODL_AVAILABLE)

@app.route('/experiment_manage')
def experiment_manage():
    """实验管理页面"""
    # 检查是否已登录
    if not session.get('logged_in'):
        return redirect(flask_url_for('login'))
    
    username = session.get('username', 'admin')
    return render_template('experiment_manage.html', username=username)


@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    try:
        data = request.json
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        print(f"Received generate request: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        selected_repos = data.get('repos', [])
        snapshots = [s for s in data.get('snapshots', []) if s.get('id') or s.get('url') or s.get('bdnd_path')]
        output_dir = data.get('output_dir', '/root/autodl-tmp')
        dataset_name = data.get('dataset_name', 'merged_dataset')
        split_ratio = data.get('split_ratio')
        # 只有在使用随机划分时才需要 split_seed，否则使用默认值
        split_seed = data.get('split_seed', 42) if split_ratio else 42
        data_only = data.get('data_only', False)
        enable_repos = data.get('enable_repos', True)
        enable_snapshots = data.get('enable_snapshots', True)
        enable_merge = data.get('enable_merge', True)
        category_group = data.get('category_group', '')
        selected_models = data.get('models', [])
        
        print(f"Processing: repos={len(selected_repos)}, snapshots={len(snapshots)}, enable_repos={enable_repos}, enable_snapshots={enable_snapshots}, enable_merge={enable_merge}")
        
        if enable_merge and not enable_snapshots:
            return jsonify({'error': '数据集生成需要先启用数据快照下载'}), 400
        
        if enable_snapshots and not snapshots:
            return jsonify({'error': '请至少添加一个数据快照'}), 400
        
        print("Generating script...")
        username = session.get('username', 'admin')
        script = generate_script(selected_repos, snapshots, output_dir, dataset_name, split_ratio, split_seed, data_only,
                                enable_repos, enable_snapshots, enable_merge, category_group, selected_models, username)
        
        print(f"Script generated successfully, length: {len(script)}")
        return jsonify({'script': script})
    except Exception as e:
        print(f"Error in generate: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_access_token():
    """从环境变量或配置文件获取 access_token"""
    # 优先从环境变量获取
    access_token = os.environ.get('baidu_netdisk_access_token')
    if access_token:
        return access_token
    
    # 尝试从 env_key_manager 获取（如果可用）
    try:
        from env_key_manager import APIKeyManager
        key_manager = APIKeyManager()
        key_manager.setup_api_key(["baidu_netdisk_access_token",])
        access_token = key_manager.get_api_key("baidu_netdisk_access_token")
        if access_token:
            return access_token
    except Exception:
        pass
    
    return None

@app.route('/api/save', methods=['POST'])
@login_required
def save():
    """保存脚本到百度网盘（不下载）"""
    try:
        data = request.json
        selected_repos = data.get('repos', [])
        snapshots = [s for s in data.get('snapshots', []) if s.get('id') or s.get('url') or s.get('bdnd_path')]
        output_dir = data.get('output_dir', '/root/autodl-tmp')
        dataset_name = data.get('dataset_name', 'merged_dataset')
        split_ratio = data.get('split_ratio')
        # 只有在使用随机划分时才需要 split_seed，否则使用默认值
        split_seed = data.get('split_seed', 42) if split_ratio else 42
        data_only = data.get('data_only', False)
        enable_repos = data.get('enable_repos', True)
        enable_snapshots = data.get('enable_snapshots', True)
        enable_merge = data.get('enable_merge', True)
        category_group = data.get('category_group', '')
        selected_models = data.get('models', [])
        filename = data.get('filename', 'auto_job.sh')
        backup_to_netdisk = data.get('backup_to_netdisk', False)
        script_content = data.get('script_content')  # 如果用户编辑了脚本，直接使用编辑后的内容
        
        # 获取当前用户
        username = session.get('username', 'admin')
        
        # 如果传入了编辑后的脚本内容，直接使用；否则重新生成
        if script_content:
            script = script_content
        else:
            script = generate_script(selected_repos, snapshots, output_dir, dataset_name, split_ratio, split_seed, data_only,
                                    enable_repos, enable_snapshots, enable_merge, category_group, selected_models, username)
        
        # 保存到服务器本地（无论是否备份到网盘都保存）
        user_scripts_dir = get_user_storage_dir(SCRIPTS_STORAGE_DIR, username)
        local_file_path = user_scripts_dir / filename
        try:
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(script)
            print(f"✓ Script saved to server: {local_file_path}")
        except Exception as e:
            print(f"Warning: Failed to save script to server: {e}")
        
        # 如果选择备份到网盘，立即在服务器端执行备份
        backup_success = False
        backup_error = None
        if backup_to_netdisk:
            try:
                access_token = get_access_token()
                if not access_token:
                    backup_error = "Access token not available"
                    print(f"Warning: {backup_error}, skipping backup")
                else:
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(script)
                        tmp_path = tmp_file.name
                    
                    try:
                        # 上传到百度网盘（文件已经在上面保存到本地了）
                        client = BaiduNetdiskClient(access_token)
                        
                        # 确保目标目录存在
                        remote_dir = BAIDU_NETDISK_SCRIPTS_DIR
                        if not client.create_directory(remote_dir):
                            # 如果创建失败，尝试继续（可能目录已存在）
                            print(f"Warning: Failed to create directory {remote_dir}, continuing...")
                        
                        # 上传文件
                        remote_path = f"{remote_dir}/{filename}"
                        print(f"Uploading script to Baidu Netdisk: {remote_path}")
                        result = client.upload_file_auto(str(local_file_path), remote_path, show_progress=False)
                        
                        if result and isinstance(result, dict) and result.get("errno") == 0:
                            backup_success = True
                            print(f"✓ Script successfully backed up to Baidu Netdisk: {remote_path}")
                        elif result is None:
                            backup_error = "Upload returned None (upload failed)"
                            print(f"✗ Failed to backup script: {backup_error}")
                        else:
                            errno = result.get("errno", "unknown")
                            errmsg = result.get("errmsg", "Unknown error")
                            backup_error = f"Upload failed (errno={errno}): {errmsg}"
                            print(f"✗ Failed to backup script: {backup_error}")
                    except Exception as e:
                        backup_error = str(e)
                        print(f"✗ Exception during backup: {backup_error}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        # 清理临时文件（但保留服务器本地文件）
                        try:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                        except Exception as e:
                            print(f"Warning: Failed to delete temp file: {e}")
            except Exception as e:
                backup_error = str(e)
                print(f"✗ Backup to Baidu Netdisk failed: {backup_error}")
                import traceback
                traceback.print_exc()
        
        # 只备份到网盘，不下载文件
        if backup_to_netdisk:
            if backup_success:
                return jsonify({
                    'success': True,
                    'message': f'Script backed up to /apps/autodl/scripts/{filename}',
                    'filename': filename
                })
            else:
                return jsonify({
                    'success': False,
                    'error': backup_error or 'Unknown error'
                }), 500
        else:
            return jsonify({
                'success': True,
                'message': 'Script saved to server',
                'filename': filename
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scripts', methods=['GET'])
@login_required
def list_scripts():
    """列出服务器上已保存的脚本文件"""
    try:
        username = session.get('username', 'admin')
        files = []
        
        # 获取用户可访问的目录列表
        accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
        
        # 从所有可访问的目录获取文件列表
        for scripts_dir in accessible_dirs:
            if scripts_dir.exists():
                # 只显示历史脚本，排除运行脚本（run.sh, run.py）
                for file_path in scripts_dir.glob('*.sh'):
                    # 排除运行脚本
                    if file_path.name in ['run.sh', 'run.py']:
                        continue
                    try:
                        stat = file_path.stat()
                        # 获取文件所属用户（从路径判断）
                        if scripts_dir == SCRIPTS_STORAGE_DIR:
                            owner = 'admin'  # 根目录的文件属于 admin
                        else:
                            owner = scripts_dir.name
                        
                        files.append({
                            'filename': file_path.name,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'local': True,
                            'owner': owner  # 添加所有者信息
                        })
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")
                        continue
        
        # 按修改时间倒序排列（最新的在前）
        files = sorted(files, key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'files': files})
    except Exception as e:
        print(f"Error listing scripts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/scripts/<filename>/download', methods=['GET'])
@login_required
def download_script(filename):
    """提供脚本文件的下载链接（使用临时token，生成完整URL）"""
    try:
        username = session.get('username', 'admin')
        
        # URL 解码文件名
        from urllib.parse import unquote
        filename = unquote(filename)
        
        # 安全检查：防止路径遍历攻击
        filename = os.path.basename(filename)
        if not filename.endswith('.sh'):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # 查找文件（先检查用户目录，admin 可以检查所有目录）
        file_path = None
        accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
        
        for scripts_dir in accessible_dirs:
            potential_path = scripts_dir / filename
            if potential_path.exists() and potential_path.is_file():
                file_path = potential_path
                break
        
        if not file_path or not file_path.exists():
            print(f"File not found: {filename}")
            return jsonify({'error': f'File not found: {filename}'}), 404
        
        if not file_path.is_file():
            return jsonify({'error': 'Not a file'}), 400
        
        # 生成临时下载token
        token = generate_download_token(filename)
        
        # 从请求中获取正确的 host 和 scheme，生成完整URL
        # 支持通过 Nginx 反向代理的情况
        scheme = request.headers.get('X-Forwarded-Proto', 'http')
        if scheme == 'http' and request.is_secure:
            scheme = 'https'
        
        host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
        if not host:
            host = request.host or 'localhost:6008'
        
        # 生成完整的下载URL（使用token，不暴露文件名和服务器路径）
        download_url = f"{scheme}://{host}/api/download/{token}"
        
        print(f"Generated download URL with token for {filename}: {download_url}")
        
        return jsonify({
            'filename': filename,
            'download_url': download_url,
            'size': file_path.stat().st_size
        })
    except Exception as e:
        print(f"Error generating download URL: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<token>', methods=['GET'])
def serve_script(token):
    """通过token提供脚本文件下载服务（不暴露服务器信息）"""
    try:
        # 验证token
        filename = verify_download_token(token)
        if not filename:
            return jsonify({'error': 'Invalid or expired token'}), 403
        
        file_path = None
        
        # 先检查临时脚本目录（运行脚本）
        if '/' in filename or '\\' in filename:  # 如果包含路径分隔符，说明是临时文件
            potential_path = TEMP_SCRIPTS_DIR / filename
            if potential_path.exists() and potential_path.is_file():
                file_path = potential_path
        else:
            # 查找文件（在所有用户目录中查找）
            # 先检查根目录（admin 的旧文件）
            potential_path = SCRIPTS_STORAGE_DIR / filename
            if potential_path.exists() and potential_path.is_file():
                file_path = potential_path
            else:
                # 检查所有用户目录
                if SCRIPTS_STORAGE_DIR.exists():
                    for item in SCRIPTS_STORAGE_DIR.iterdir():
                        if item.is_dir():
                            potential_path = item / filename
                            if potential_path.exists() and potential_path.is_file():
                                file_path = potential_path
                                break
                # 如果还没找到，检查临时目录
                if not file_path:
                    for item in TEMP_SCRIPTS_DIR.iterdir():
                        if item.is_dir():
                            potential_path = item / filename
                            if potential_path.exists() and potential_path.is_file():
                                file_path = potential_path
                                break
        
        if not file_path or not file_path.exists():
            print(f"File not found when serving: {filename}")
            return jsonify({'error': f'File not found: {filename}'}), 404
        
        if not file_path.is_file():
            return jsonify({'error': 'Not a file'}), 400
        
        print(f"Serving file via token: {file_path}")
        
        # 提取原始文件名（如果是临时文件，可能需要提取）
        download_name = filename
        if file_path.parent.parent == TEMP_SCRIPTS_DIR:
            # 临时文件，提取原始文件名（run.sh 或 run.py）
            if filename.endswith('.py'):
                download_name = 'run.py'
            elif filename.endswith('.sh'):
                download_name = 'run.sh'
        
        return send_file(
            str(file_path),
            mimetype='text/plain',
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        print(f"Error serving file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/configs', methods=['GET'])
@login_required
def list_configs():
    """列出保存的配置"""
    try:
        username = session.get('username', 'admin')
        configs = []
        
        # 获取用户可访问的目录列表
        accessible_dirs = get_accessible_dirs(CONFIGS_STORAGE_DIR, username)
        
        # 从所有可访问的目录获取配置列表
        for configs_dir in accessible_dirs:
            if configs_dir.exists():
                for file_path in configs_dir.glob('*.json'):
                    try:
                        stat = file_path.stat()
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        
                        # 获取配置所属用户（从路径判断）
                        if configs_dir == CONFIGS_STORAGE_DIR:
                            owner = 'admin'  # 根目录的配置属于 admin
                        else:
                            owner = configs_dir.name
                        
                        configs.append({
                            'filename': file_path.stem,
                            'config': config_data,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'owner': owner  # 添加所有者信息
                        })
                    except Exception as e:
                        print(f"Error reading config {file_path}: {e}")
                        continue
        
        configs = sorted(configs, key=lambda x: x['modified'], reverse=True)
        return jsonify({'configs': configs})
    except Exception as e:
        print(f"Error listing configs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/configs', methods=['POST'])
@login_required
def save_config():
    """保存配置"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        config_name = data.get('name', '')
        config_data = data.get('config', {})
        
        if not config_name:
            # 生成默认名称
            now = datetime.now()
            config_name = f"config_{now.strftime('%Y%m%d_%H%M%S')}"
        
        # 保存到用户目录
        user_configs_dir = get_user_storage_dir(CONFIGS_STORAGE_DIR, username)
        config_file = user_configs_dir / f"{config_name}.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'name': config_name})
    except Exception as e:
        print(f"Error saving config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/configs/<config_name>', methods=['DELETE'])
@login_required
def delete_config(config_name):
    """删除配置"""
    try:
        username = session.get('username', 'admin')
        from urllib.parse import unquote
        config_name = unquote(config_name)
        config_name = os.path.basename(config_name)
        
        # 查找配置文件（检查用户可访问的目录）
        config_file = None
        accessible_dirs = get_accessible_dirs(CONFIGS_STORAGE_DIR, username)
        
        for configs_dir in accessible_dirs:
            potential_path = configs_dir / f"{config_name}.json"
            if potential_path.exists() and potential_path.is_file():
                config_file = potential_path
                break
        
        if not config_file or not config_file.exists():
            return jsonify({'error': 'Config not found'}), 404
        
        config_file.unlink()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/scripts/<filename>', methods=['DELETE'])
@login_required
def delete_script(filename):
    """删除脚本文件"""
    try:
        username = session.get('username', 'admin')
        # URL 解码文件名
        from urllib.parse import unquote
        filename = unquote(filename)
        
        # 安全检查：防止路径遍历攻击
        filename = os.path.basename(filename)
        if not filename.endswith('.sh'):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # 查找文件（检查用户可访问的目录）
        file_path = None
        accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
        
        for scripts_dir in accessible_dirs:
            potential_path = scripts_dir / filename
            if potential_path.exists() and potential_path.is_file():
                file_path = potential_path
                break
        
        if not file_path or not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        if not file_path.is_file():
            return jsonify({'error': 'Not a file'}), 400
        
        # 删除文件
        file_path.unlink()
        print(f"Deleted script file: {file_path}")
        
        return jsonify({'success': True, 'message': f'Script {filename} deleted successfully'})
    except Exception as e:
        print(f"Error deleting file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 用户配置管理 API ====================

@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """修改当前用户密码"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return jsonify({'error': '旧密码和新密码不能为空'}), 400
        
        # 验证旧密码
        if not verify_account(username, old_password):
            return jsonify({'error': '旧密码错误'}), 400
        
        # 读取账户配置
        accounts = get_all_accounts()
        
        # 更新密码（使用哈希）
        accounts[username] = hash_password(new_password)
        
        # 保存配置
        if save_accounts(accounts):
            return jsonify({'success': True, 'message': '密码修改成功'})
        else:
            return jsonify({'error': '保存密码失败'}), 500
    except Exception as e:
        print(f"Error changing password: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/models', methods=['GET'])
@login_required
def get_user_models():
    """获取当前用户的模型配置"""
    try:
        username = session.get('username', 'admin')
        _, _, _, models, _ = load_user_config(username)
        return jsonify({'models': models})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/models', methods=['POST'])
@login_required
def add_user_model():
    """添加或更新模型配置"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        model_name = data.get('name', '')
        model_config = data.get('config', {})
        
        if not model_name:
            return jsonify({'error': '模型名称不能为空'}), 400
        
        # 加载当前配置
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        # 更新模型配置
        models[model_name] = model_config
        
        # 保存配置
        if save_user_config(username, models=models):
            return jsonify({'success': True, 'message': f'模型 {model_name} 配置已保存'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error adding model: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/models/<model_name>', methods=['DELETE'])
@login_required
def delete_user_model(model_name):
    """删除模型配置"""
    try:
        username = session.get('username', 'admin')
        from urllib.parse import unquote
        model_name = unquote(model_name)
        
        # 加载当前配置
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        if model_name not in models:
            return jsonify({'error': '模型不存在'}), 404
        
        # 删除模型
        del models[model_name]
        
        # 保存配置
        if save_user_config(username, models=models):
            return jsonify({'success': True, 'message': f'模型 {model_name} 已删除'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error deleting model: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/repos', methods=['GET'])
@login_required
def get_user_repos():
    """获取当前用户的代码仓库配置"""
    try:
        username = session.get('username', 'admin')
        repos, _, _, _, _ = load_user_config(username)
        return jsonify({'repos': repos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/repos', methods=['POST'])
@login_required
def add_user_repo():
    """添加或更新代码仓库配置"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        repo_name = data.get('name', '')
        repo_config = data.get('config', {})
        
        if not repo_name:
            return jsonify({'error': '仓库名称不能为空'}), 400
        
        if 'url' not in repo_config:
            return jsonify({'error': '仓库 URL 不能为空'}), 400
        
        # 加载当前配置
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        # 确保 install_cmds 存在
        if 'install_cmds' not in repo_config:
            repo_config['install_cmds'] = []
        
        # 更新仓库配置
        repos[repo_name] = repo_config
        
        # 保存配置
        if save_user_config(username, repos=repos):
            return jsonify({'success': True, 'message': f'仓库 {repo_name} 配置已保存'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error adding repo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/repos/<repo_name>', methods=['DELETE'])
@login_required
def delete_user_repo(repo_name):
    """删除代码仓库配置"""
    try:
        username = session.get('username', 'admin')
        from urllib.parse import unquote
        repo_name = unquote(repo_name)
        
        # 加载当前配置
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        if repo_name not in repos:
            return jsonify({'error': '仓库不存在'}), 404
        
        # 删除仓库
        del repos[repo_name]
        
        # 保存配置
        if save_user_config(username, repos=repos):
            return jsonify({'success': True, 'message': f'仓库 {repo_name} 已删除'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error deleting repo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 管理员账户管理 API ====================

@app.route('/api/admin/accounts', methods=['GET'])
@login_required
def list_accounts():
    """获取所有账户列表（仅管理员）"""
    try:
        username = session.get('username', 'admin')
        if not is_admin(username):
            return jsonify({'error': '权限不足'}), 403
        
        accounts = get_all_accounts()
        # 只返回用户名列表，不返回密码哈希
        account_list = [{'username': name, 'is_admin': name == 'admin'} for name in accounts.keys()]
        return jsonify({'accounts': account_list})
    except Exception as e:
        print(f"Error listing accounts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/accounts', methods=['POST'])
@login_required
def add_account():
    """添加新账户（仅管理员）"""
    try:
        username = session.get('username', 'admin')
        if not is_admin(username):
            return jsonify({'error': '权限不足'}), 403
        
        data = request.json
        new_username = data.get('username', '').strip()
        new_password = data.get('password', '').strip()
        
        if not new_username or not new_password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        
        # 检查用户名是否已存在
        accounts = get_all_accounts()
        if new_username in accounts:
            return jsonify({'error': '用户名已存在'}), 400
        
        # 添加新账户（密码使用哈希）
        accounts[new_username] = hash_password(new_password)
        
        # 保存配置
        if save_accounts(accounts):
            return jsonify({'success': True, 'message': f'账户 {new_username} 创建成功'})
        else:
            return jsonify({'error': '保存账户失败'}), 500
    except Exception as e:
        print(f"Error adding account: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/accounts/<account_name>', methods=['DELETE'])
@login_required
def delete_account(account_name):
    """删除账户（仅管理员，不能删除admin）"""
    try:
        username = session.get('username', 'admin')
        if not is_admin(username):
            return jsonify({'error': '权限不足'}), 403
        
        from urllib.parse import unquote
        account_name = unquote(account_name)
        
        # 不能删除 admin 账户
        if account_name == 'admin':
            return jsonify({'error': '不能删除管理员账户'}), 400
        
        # 检查账户是否存在
        accounts = get_all_accounts()
        if account_name not in accounts:
            return jsonify({'error': '账户不存在'}), 404
        
        # 删除账户
        del accounts[account_name]
        
        # 保存配置
        if save_accounts(accounts):
            return jsonify({'success': True, 'message': f'账户 {account_name} 已删除'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error deleting account: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/accounts/<account_name>/reset-password', methods=['POST'])
@login_required
def reset_account_password():
    """重置账户密码（仅管理员）"""
    try:
        username = session.get('username', 'admin')
        if not is_admin(username):
            return jsonify({'error': '权限不足'}), 403
        
        from urllib.parse import unquote
        account_name = unquote(request.view_args['account_name'])
        data = request.json
        new_password = data.get('password', '').strip()
        
        if not new_password:
            return jsonify({'error': '新密码不能为空'}), 400
        
        # 检查账户是否存在
        accounts = get_all_accounts()
        if account_name not in accounts:
            return jsonify({'error': '账户不存在'}), 404
        
        # 更新密码（使用哈希）
        accounts[account_name] = hash_password(new_password)
        
        # 保存配置
        if save_accounts(accounts):
            return jsonify({'success': True, 'message': f'账户 {account_name} 密码已重置'})
        else:
            return jsonify({'error': '保存密码失败'}), 500
    except Exception as e:
        print(f"Error resetting password: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 类别映射组管理 API（全局共享）====================

@app.route('/api/category-groups', methods=['GET'])
@login_required
def get_category_groups():
    """获取类别映射组列表（所有用户共享）"""
    try:
        category_groups = load_category_groups()
        return jsonify({'category_groups': category_groups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/category-groups', methods=['POST'])
@login_required
def save_category_groups_api():
    """保存类别映射组列表（所有用户共享，仅管理员可修改）"""
    try:
        username = session.get('username', 'admin')
        # 只有管理员可以修改类别映射组
        if not is_admin(username):
            return jsonify({'error': '权限不足，只有管理员可以修改类别映射组'}), 403
        
        data = request.json
        category_groups = data.get('category_groups', [])
        
        if not isinstance(category_groups, list):
            return jsonify({'error': '类别映射组必须是数组'}), 400
        
        if save_category_groups(category_groups):
            return jsonify({'success': True, 'message': '类别映射组保存成功'})
        else:
            return jsonify({'error': '保存失败'}), 500
    except Exception as e:
        print(f"Error saving category groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 用户类别映射组管理 API ====================

@app.route('/api/user/category-groups', methods=['GET'])
@login_required
def get_user_category_groups():
    """获取当前用户自己的类别映射组"""
    try:
        username = session.get('username', 'admin')
        user_category_groups = load_user_category_groups(username)
        return jsonify({'category_groups': user_category_groups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/category-groups', methods=['POST'])
@login_required
def save_user_category_groups_api():
    """保存当前用户自己的类别映射组"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        category_groups = data.get('category_groups', [])
        
        if not isinstance(category_groups, list):
            return jsonify({'error': '类别映射组必须是数组'}), 400
        
        if save_user_category_groups(username, category_groups):
            return jsonify({'success': True, 'message': '类别映射组保存成功'})
        else:
            return jsonify({'error': '保存失败'}), 500
    except Exception as e:
        print(f"Error saving user category groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 系统配置管理 API ====================

@app.route('/api/user/system-config', methods=['GET'])
@login_required
def get_system_config():
    """获取当前用户的系统配置（百度网盘、Git SSH等）"""
    try:
        username = session.get('username', 'admin')
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        # 读取用户自己的 .env_config.json 文件内容
        env_config_content = ''
        env_config_file = get_user_env_config_file(username)
        if env_config_file.exists():
            try:
                with open(env_config_file, 'r', encoding='utf-8') as f:
                    env_config_content = f.read()
            except Exception as e:
                print(f"Warning: Failed to read .env_config.json: {e}")
        
        return jsonify({
            'env_config_content': env_config_content,
            'git_ssh_path': data_download.get('git_ssh_path', ''),
            'dataset_cache_path': data_download.get('dataset_cache_path', 'cache/datasets')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/system-config', methods=['POST'])
@login_required
def save_system_config():
    """保存当前用户的系统配置"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        env_config_content = data.get('env_config_content', '').strip()
        git_ssh_path = data.get('git_ssh_path', '').strip()
        dataset_cache_path = data.get('dataset_cache_path', 'cache/datasets').strip()
        
        # 保存用户自己的 .env_config.json 文件
        if env_config_content:
            try:
                # 验证JSON格式
                json.loads(env_config_content)
                # 保存到用户特定的文件
                env_config_file = get_user_env_config_file(username)
                env_config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(env_config_file, 'w', encoding='utf-8') as f:
                    f.write(env_config_content)
            except json.JSONDecodeError as e:
                return jsonify({'error': f'JSON格式错误: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'error': f'保存文件失败: {str(e)}'}), 500
        
        # 加载现有配置
        repos, data_download, category_groups, models, bdnd_config = load_user_config(username)
        
        updated_data_download = data_download.copy()
        if git_ssh_path:
            updated_data_download['git_ssh_path'] = git_ssh_path
        if dataset_cache_path:
            updated_data_download['dataset_cache_path'] = dataset_cache_path
        
        # 保存配置
        if save_user_config(username, 
                          data_download=updated_data_download):
            return jsonify({'success': True, 'message': '系统配置保存成功'})
        else:
            return jsonify({'error': '保存配置失败'}), 500
    except Exception as e:
        print(f"Error saving system config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== AutoDL Token 管理 API ====================

@app.route('/api/user/autodl-token', methods=['GET'])
@login_required
def get_user_autodl_token_status():
    """获取当前用户的 AutoDL Token 状态（不返回实际值）"""
    try:
        username = session.get('username', 'admin')
        token = load_user_autodl_token(username)
        return jsonify({
            'has_token': token is not None,
            'token_set': bool(token)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/autodl-token', methods=['POST'])
@login_required
def save_user_autodl_token_api():
    """保存当前用户的 AutoDL Token"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'error': 'Token 不能为空'}), 400
        
        if save_user_autodl_token(username, token):
            return jsonify({'success': True, 'message': 'Token 保存成功'})
        else:
            return jsonify({'error': '保存失败'}), 500
    except Exception as e:
        print(f"Error saving autodl token: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/autodl-token', methods=['DELETE'])
@login_required
def delete_user_autodl_token_api():
    """删除当前用户的 AutoDL Token"""
    try:
        username = session.get('username', 'admin')
        if delete_user_autodl_token(username):
            return jsonify({'success': True, 'message': 'Token 已删除'})
        else:
            return jsonify({'error': '删除失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== AutoDL API 路由 ====================

@app.route('/api/autodl/test', methods=['POST'])
@login_required
def test_autodl_connection():
    """测试 AutoDL API 连接"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
        token = data.get('token', '').strip() if data else ''
        if not token:
            token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        # 创建客户端并测试连接
        client = AutoDLElasticDeployment(token)
        # 尝试获取部署列表来测试连接
        deployments = client.get_deployments()
        
        return jsonify({'success': True, 'message': '连接成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/images', methods=['POST'])
@login_required
def get_autodl_images():
    """获取 AutoDL 镜像列表"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
        token = data.get('token', '').strip() if data else ''
        if not token:
            token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        images = client.get_images()
        
        # 处理镜像列表，确保每个镜像都有清晰的名称和UUID
        processed_images = []
        for img in images:
            if isinstance(img, dict):
                # 优先获取UUID（用于API调用）- 尝试多个可能的字段名
                image_uuid = (img.get('uuid') or img.get('image_uuid') or 
                             img.get('id') or img.get('image_id') or 
                             img.get('uid') or img.get('image_uid'))
                
                # 尝试从不同字段获取名称（用于显示）
                image_name = (img.get('name') or img.get('image_name') or 
                             img.get('title') or img.get('repository') or 
                             img.get('display_name') or img.get('image') or
                             img.get('repo_name'))
                
                # 如果UUID不存在，使用名称作为UUID（向后兼容）
                if not image_uuid:
                    image_uuid = image_name
                
                # 如果名称不存在，使用UUID作为名称
                if not image_name:
                    image_name = image_uuid
                
                # 构建处理后的镜像对象
                processed_img = {
                    'id': image_uuid,  # 使用UUID作为ID
                    'uuid': image_uuid,  # 明确标记UUID字段
                    'name': image_name,  # 显示名称
                    **img  # 保留原始数据
                }
                processed_images.append(processed_img)
            elif isinstance(img, str):
                # 如果返回的是字符串列表（假设是UUID）
                processed_images.append({
                    'id': img,
                    'uuid': img,
                    'name': img
                })
            else:
                # 其他格式，直接添加
                processed_images.append(img)
        
        return jsonify({'images': processed_images})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployments', methods=['POST'])
@login_required
def get_autodl_deployments():
    """获取 AutoDL 部署列表"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
        token = data.get('token', '').strip() if data else ''
        if not token:
            token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        deployments = client.get_deployments()
        
        return jsonify({'deployments': deployments})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment/<deployment_uuid>/stop', methods=['POST'])
@login_required
def stop_autodl_deployment(deployment_uuid):
    """停止 AutoDL 部署"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        
        # 调用 stop_deployment 方法
        success = client.stop_deployment(deployment_uuid)
        
        if success:
            return jsonify({'success': True, 'message': '部署已停止'})
        else:
            return jsonify({'error': '停止部署失败'}), 500
    except Exception as e:
        print(f"Error stopping deployment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment/<deployment_uuid>/delete', methods=['DELETE'])
@login_required
def delete_autodl_deployment(deployment_uuid):
    """删除 AutoDL 部署"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        
        # 调用 delete_deployment 方法
        success = client.delete_deployment(deployment_uuid)
        
        if success:
            return jsonify({'success': True, 'message': '部署已删除'})
        else:
            return jsonify({'error': '删除部署失败'}), 500
    except Exception as e:
        print(f"Error deleting deployment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/gpu-stock', methods=['GET'])
@login_required
def get_autodl_gpu_stock():
    """获取 AutoDL GPU 库存"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        
        # 获取所有分区的 GPU 库存
        # 根据 autodl-api 文档，get_gpu_stock 需要数据中心和 GPU ID
        gpu_stock = {}
        
        # 使用全局数据中心映射
        datacenter_mapping = DATACENTER_MAPPING
        
        # 所有GPU类型及其可能的名称格式（API返回的是"RTX 4090"格式，带空格）
        # 前端使用的是"RTX-4090"格式（带连字符）
        gpu_types = [
            "RTX 5090", "RTX 4090", "RTX 4080", "RTX 3090", "RTX 3080", "RTX 3070",
            "V100", "A100", "H100", "L20", "L40", "RTX 4090D"
        ]
        
        # GPU名称映射：前端格式 -> API返回格式
        gpu_name_mapping = {
            'RTX-5090': 'RTX 5090',
            'RTX-4090': 'RTX 4090',
            'RTX-4090D': 'RTX 4090D',
            'RTX-4080': 'RTX 4080',
            'RTX-3090': 'RTX 3090',
            'RTX-3080': 'RTX 3080',
            'RTX-3070': 'RTX 3070',
            'V100': 'V100',
            'A100': 'A100',
            'H100': 'H100',
            'L20': 'L20',
            'L40': 'L40'
        }
        
        # 遍历所有数据中心
        for dc_name_cn, dc_code in datacenter_mapping.items():
            gpu_stock[dc_name_cn] = {
                '_code': dc_code,  # 保存英文编号，用于API调用
                '_name': dc_name_cn  # 保存中文名称，用于显示
            }
            
            # 初始化所有GPU类型为0
            for frontend_name in gpu_name_mapping.keys():
                gpu_stock[dc_name_cn][frontend_name] = {
                    'available': 0,
                    'idle_gpu_num': 0,
                    'total_gpu_num': 0,
                    'count': 0
                }
            
            # 尝试使用通用方法获取该数据中心的所有GPU库存
            # 使用一个通用的GPU ID（比如118，通常能返回所有GPU类型）
            common_gpu_ids = [118, 117, 119, 120, 121, 122, 123, 124, 125, 126, 127]
            
            for gpu_id in common_gpu_ids:
                try:
                    stock = client.get_gpu_stock(dc_code, gpu_id)
                    
                    if isinstance(stock, list):
                        # 遍历返回的GPU列表，匹配所有我们需要的GPU类型
                        for gpu_item in stock:
                            if isinstance(gpu_item, dict):
                                gpu_type = gpu_item.get('gpu_type', '').strip()
                                
                                # 尝试匹配每个我们需要的GPU类型
                                for frontend_name, api_name in gpu_name_mapping.items():
                                    matched = False
                                    
                                    # 精确匹配（API返回的是"RTX 4090"格式）
                                    if gpu_type == api_name:
                                        matched = True
                                    else:
                                        # 模糊匹配：去除空格和连字符，统一比较
                                        gpu_type_normalized = gpu_type.replace(' ', '').replace('-', '').upper()
                                        api_name_normalized = api_name.replace(' ', '').replace('-', '').upper()
                                        
                                        # 特殊处理：RTX-4090D 需要精确匹配（不能匹配到 RTX 4090）
                                        if frontend_name == 'RTX-4090D':
                                            if '4090D' in gpu_type_normalized:
                                                matched = True
                                        # RTX-4090 不能匹配到 RTX 4090D
                                        elif frontend_name == 'RTX-4090':
                                            if api_name_normalized in gpu_type_normalized and '4090D' not in gpu_type_normalized:
                                                matched = True
                                        # 其他GPU类型：包含匹配
                                        else:
                                            if api_name_normalized in gpu_type_normalized or gpu_type_normalized in api_name_normalized:
                                                matched = True
                                    
                                    if matched:
                                        # 累加空闲GPU数量
                                        idle_num = gpu_item.get('idle_gpu_num', 0)
                                        total_num = gpu_item.get('total_gpu_num', 0)
                                        
                                        # 累加到对应的GPU类型
                                        current_idle = gpu_stock[dc_name_cn][frontend_name].get('idle_gpu_num', 0)
                                        current_total = gpu_stock[dc_name_cn][frontend_name].get('total_gpu_num', 0)
                                        
                                        gpu_stock[dc_name_cn][frontend_name] = {
                                            'available': current_idle + idle_num,
                                            'idle_gpu_num': current_idle + idle_num,
                                            'total_gpu_num': current_total + total_num,
                                            'count': current_idle + idle_num
                                        }
                                        
                                        print(f"DEBUG: Matched {gpu_type} -> {frontend_name} in {dc_name_cn}: idle={idle_num}, total={total_num}")
                                        break  # 匹配成功后跳出内层循环
                        
                except Exception as e:
                    # 某些GPU ID可能不存在，继续尝试下一个
                    continue
        
        # 打印汇总信息以便调试
        print(f"DEBUG: GPU Stock Summary - Total datacenters: {len(gpu_stock)}")
        for dc_name, dc_data in gpu_stock.items():
            print(f"DEBUG: {dc_name}: {len([k for k in dc_data.keys() if not k.startswith('_')])} GPU types")
        
        return jsonify({
            'gpu_stock': gpu_stock,
            'datacenter_mapping': datacenter_mapping,  # 同时返回映射关系，方便前端使用
            'debug_info': {
                'total_datacenters': len(gpu_stock),
                'gpu_types': list(gpu_name_mapping.keys())
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment/<deployment_uuid>/ssh', methods=['GET'])
@login_required
def get_deployment_ssh(deployment_uuid):
    """获取部署的SSH连接信息"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        token = load_user_autodl_token(username)
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        client = AutoDLElasticDeployment(token)
        
        try:
            # 使用 query_containers 方法查询容器信息
            containers_list = client.query_containers(deployment_uuid)['list']
            print(f"DEBUG: Containers info for deployment {deployment_uuid}: {containers_list}")
            
            if len(containers_list) == 0:
                return jsonify({'info': '容器尚未分配，正在排队中'}), 202
            container_info = containers_list[0]['info']
            ssh_info = {
                'ssh_command': container_info.get('ssh_command', ''),
                'root_password': container_info.get('root_password', ''),
                'service_6006_port_url': container_info.get('service_6006_port_url', ''),
                'service_6008_port_url': container_info.get('service_6008_port_url', ''),
                'command': container_info.get('ssh_command', '')  
            }
                        
            return jsonify({
                'deployment_uuid': deployment_uuid,
                'ssh_info': ssh_info,
                'container_info': container_info  # 返回完整容器信息以便调试
            })
        except AttributeError as e:
            return jsonify({
                'error': f'获取SSH信息失败。请检查 autodl-api 库的版本。错误：{str(e)}'
            }), 501
        except Exception as e:
            # 如果 query_containers 方法不存在或调用失败，尝试使用旧方法
            try:
                deployments = client.get_deployments()
                deployment = None
                for dep in deployments:
                    if isinstance(dep, dict):
                        if dep.get('uuid') == deployment_uuid or dep.get('id') == deployment_uuid:
                            deployment = dep
                            break
                
                if not deployment:
                    return jsonify({'error': '部署不存在'}), 404
                
                ssh_info = {
                    'host': deployment.get('ssh_host') or deployment.get('host') or deployment.get('ip'),
                    'port': deployment.get('ssh_port') or deployment.get('port') or 22,
                    'user': deployment.get('ssh_user') or deployment.get('user') or 'root',
                    'password': deployment.get('ssh_password') or deployment.get('password'),
                    'command': None,
                    'ssh_command': None,
                    'root_password': None,
                    'service_6006_port_url': None,
                    'service_6008_port_url': None
                }
                
                # 如果有密码，构建SSH命令
                if ssh_info['host']:
                    if ssh_info['password']:
                        ssh_command = f"sshpass -p '{ssh_info['password']}' ssh -p {ssh_info['port']} {ssh_info['user']}@{ssh_info['host']}"
                    else:
                        ssh_command = f"ssh -p {ssh_info['port']} {ssh_info['user']}@{ssh_info['host']}"
                    ssh_info['command'] = ssh_command
                    ssh_info['ssh_command'] = ssh_command
                    ssh_info['root_password'] = ssh_info['password']
                
                return jsonify({
                    'deployment_uuid': deployment_uuid,
                    'ssh_info': ssh_info,
                    'deployment': deployment
                })
            except Exception as fallback_error:
                return jsonify({
                    'error': f'获取SSH信息失败: {str(e)}。回退方法也失败: {str(fallback_error)}'
                }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/run-script-templates', methods=['GET'])
@login_required
def get_run_script_templates():
    """获取运行脚本模板"""
    try:
        if RUN_SCRIPT_TEMPLATES_FILE.exists():
            with open(RUN_SCRIPT_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            return jsonify({
                'success': True,
                'templates': templates
            })
        else:
            # 如果文件不存在，返回默认模板
            default_templates = {
                'run_sh_template': '#!/bin/bash\ncd /root\n\nnohup bash build.sh > $OUTPUT/build.log 2>&1',
                'run_py_template': '#!/usr/bin/env python3\nimport subprocess\nimport os\nimport sys\nfrom pathlib import Path\n\n# 切换到 /root 目录\nos.chdir(\'/root\')\n\n# 获取 OUTPUT 环境变量\noutput_dir = os.environ.get(\'OUTPUT\', \'/root/output\')\nlog_file = os.path.join(output_dir, \'build.log\')\n\n# 确保日志目录存在\nPath(output_dir).mkdir(parents=True, exist_ok=True)\n\n# 执行 build.sh，将输出重定向到日志文件\nprint(f\'Starting build.sh, logs will be saved to {log_file}...\')\ntry:\n    with open(log_file, \'w\', encoding=\'utf-8\') as log:\n        log.write(f\'=== Starting build.sh ===\\n\')\n        log.flush()\n        \n        result = subprocess.run(\n            [\'bash\', \'build.sh\'],\n            cwd=\'/root\',\n            stdout=log,\n            stderr=subprocess.STDOUT,\n            check=True\n        )\n        \n        log.write(f\'\\n=== build.sh completed successfully ===\\n\')\n        log.flush()\n    \n    print(f\'build.sh completed successfully, logs saved to {log_file}\')\n    sys.exit(0)\nexcept subprocess.CalledProcessError as e:\n    error_msg = f\'build.sh failed with error code {e.returncode}\'\n    print(error_msg)\n    with open(log_file, \'a\', encoding=\'utf-8\') as log:\n        log.write(f\'\\n=== ERROR: {error_msg} ===\\n\')\n    sys.exit(1)\nexcept Exception as e:\n    error_msg = f\'Error running build.sh: {e}\'\n    print(error_msg)\n    with open(log_file, \'a\', encoding=\'utf-8\') as log:\n        log.write(f\'\\n=== ERROR: {error_msg} ===\\n\')\n    sys.exit(1)'
            }
            return jsonify({
                'success': True,
                'templates': default_templates
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/cleanup-temp-scripts', methods=['POST'])
@login_required
def cleanup_temp_scripts_api():
    """手动触发清理过期临时脚本"""
    try:
        cleanup_old_temp_scripts()
        return jsonify({'success': True, 'message': '清理完成'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/save-env-script', methods=['POST'])
@login_required
def save_env_script():
    """保存环境变量脚本文件（env.sh）并返回下载URL"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        env_vars = data.get('env_vars', {})  # 环境变量字典
        
        if not env_vars or not isinstance(env_vars, dict):
            return jsonify({'error': '环境变量不能为空'}), 400
        
        # 生成 env.sh 脚本内容
        script_lines = ['#!/bin/bash']
        script_lines.append('# 环境变量配置文件')
        script_lines.append('# 自动生成，请勿手动修改')
        script_lines.append('')
        
        for key, value in env_vars.items():
            # 转义特殊字符，确保值被正确引用
            # 替换单引号为 '\'' 以正确处理包含单引号的值
            escaped_value = str(value).replace("'", "'\\''")
            script_lines.append(f"export {key}='{escaped_value}'")
        
        script_content = '\n'.join(script_lines) + '\n'
        
        # 生成唯一的文件名（使用时间戳和随机数，避免冲突）
        import time
        import random
        timestamp = int(time.time() * 1000)  # 毫秒时间戳
        random_id = random.randint(1000, 9999)
        filename = f'env_{timestamp}_{random_id}.sh'
        
        # 保存到临时目录（每个用户有自己的子目录，1小时后自动删除）
        user_temp_dir = TEMP_SCRIPTS_DIR / username
        user_temp_dir.mkdir(parents=True, exist_ok=True)
        script_file_path = user_temp_dir / filename
        
        try:
            # 确保目录存在
            script_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存脚本内容
            with open(script_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            print(f"✓ Env script saved to temp directory: {script_file_path} (will be deleted after 1 hour)")
            print(f"Env script content:\n{script_content}")
            
            # 在保存时触发清理（异步清理旧文件）
            cleanup_old_temp_scripts()
        except Exception as e:
            print(f"Error saving env script: {e}")
            return jsonify({'error': f'保存环境变量脚本失败: {str(e)}'}), 500
        
        # 生成下载URL（保存临时文件路径到token中，用于后续下载）
        # 使用相对路径，格式：username/filename
        relative_path = str(script_file_path.relative_to(TEMP_SCRIPTS_DIR))
        token = generate_download_token(relative_path)
        
        # 从请求中获取正确的 host 和 scheme
        scheme = request.headers.get('X-Forwarded-Proto', 'http')
        if scheme == 'http' and request.is_secure:
            scheme = 'https'
        
        host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
        if not host:
            host = request.host or 'localhost:6008'
        
        download_url = f"{scheme}://{host}/api/download/{token}"
        
        return jsonify({
            'success': True,
            'filename': 'env.sh',
            'temp_filename': filename,
            'download_url': download_url
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/save-run-script', methods=['POST'])
@login_required
def save_run_script():
    """保存run脚本文件并返回下载URL"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        script_content = data.get('script_content', '').strip()
        script_type = data.get('script_type', 'shell')  # 'shell' or 'python'
        
        if not script_content:
            return jsonify({'error': '脚本内容不能为空'}), 400
        
        # 确定文件扩展名
        extension = '.py' if script_type == 'python' else '.sh'
        
        # 生成唯一的文件名（使用时间戳和随机数，避免冲突）
        import time
        import random
        timestamp = int(time.time() * 1000)  # 毫秒时间戳
        random_id = random.randint(1000, 9999)
        filename = f'run_{timestamp}_{random_id}{extension}'
        
        # 保存到临时目录（每个用户有自己的子目录，1小时后自动删除）
        user_temp_dir = TEMP_SCRIPTS_DIR / username
        user_temp_dir.mkdir(parents=True, exist_ok=True)
        script_file_path = user_temp_dir / filename
        
        try:
            # 确保目录存在
            script_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存脚本内容
            with open(script_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # 运行脚本保存到临时目录，1小时后自动删除
            # 注意：文件创建时间会用于判断是否过期，不需要手动设置修改时间
            print(f"✓ Run script saved to temp directory: {script_file_path} (will be deleted after 1 hour)")
            
            # 在保存时触发清理（异步清理旧文件）
            cleanup_old_temp_scripts()
        except Exception as e:
            print(f"Error saving run script: {e}")
            return jsonify({'error': f'保存脚本失败: {str(e)}'}), 500
        
        # 生成下载URL（保存临时文件路径到token中，用于后续下载）
        # 使用相对路径，格式：username/filename
        relative_path = str(script_file_path.relative_to(TEMP_SCRIPTS_DIR))
        token = generate_download_token(relative_path)
        
        # 从请求中获取正确的 host 和 scheme
        scheme = request.headers.get('X-Forwarded-Proto', 'http')
        if scheme == 'http' and request.is_secure:
            scheme = 'https'
        
        host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
        if not host:
            host = request.host or 'localhost:6008'
        
        download_url = f"{scheme}://{host}/api/download/{token}"
        
        # 返回文件名，用于命令行下载（run.sh 或 run.py）
        display_filename = 'run.py' if script_type == 'python' else 'run.sh'
        
        return jsonify({
            'success': True,
            'filename': display_filename,  # 返回显示用的文件名（run.sh 或 run.py）
            'temp_filename': filename,  # 临时文件名
            'download_url': download_url
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/create-deployment', methods=['POST'])
@login_required
def create_autodl_deployment():
    """创建 AutoDL 部署"""
    if not AUTODL_AVAILABLE:
        return jsonify({'error': 'autodl-api 库未安装'}), 500
    
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
        token = data.get('token', '').strip() if data else ''
        if not token:
            token = load_user_autodl_token(username)
        
        # 获取参数
        name = data.get('name', '').strip()
        image_uuid = data.get('image_uuid', '').strip()  # 镜像UUID
        deployment_type = data.get('deployment_type', 'Job')  # 默认Job，首字母大写
        dc_list = data.get('dc_list', [])  # 数据中心列表（中文名称）
        gpu_num = data.get('gpu_num', 1)
        gpu_name_set = data.get('gpu_name_set', [])  # GPU类型列表
        # 注意：不再通过 API 传递 env_vars，而是通过 env.sh 脚本文件
        # 但保存配置时仍需要 env_vars 数据
        env_vars_for_config = data.get('env_vars', {})  # 仅用于保存配置，不传递给 API
        
        # 可选参数
        replica_num = data.get('replica_num', 1)
        parallelism_num = data.get('parallelism_num', None)
        cmd = data.get('cmd', 'sleep 100')
        
        if not token:
            return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
        
        if not name:
            return jsonify({'error': '部署名称不能为空'}), 400
        
        if not image_uuid:
            return jsonify({'error': '请选择镜像'}), 400
        
        client = AutoDLElasticDeployment(token)
        
        # 将中文数据中心名称转换为英文编号
        dc_codes = []
        for dc_name_cn in dc_list:
            if dc_name_cn in DATACENTER_MAPPING:
                dc_codes.append(DATACENTER_MAPPING[dc_name_cn])
        
        # 如果没有指定数据中心，使用空列表（让API自动选择）
        if not dc_codes:
            dc_codes = None
        
        # 转换GPU名称格式（从"RTX-4090"转换为"RTX 4090"）
        gpu_names = [gpu.replace('-', ' ') for gpu in gpu_name_set] if gpu_name_set else None
        
        # ========== 完整打印所有部署参数 ==========
        print("\n" + "="*80)
        print("【创建部署 - 完整参数打印】")
        print("="*80)
        print(f"部署名称 (name): {name}")
        print(f"镜像UUID (image_uuid): {image_uuid}")
        print(f"部署类型 (deployment_type): {deployment_type}")
        print(f"副本数量 (replica_num): {replica_num}")
        print(f"并行数量 (parallelism_num): {parallelism_num}")
        print(f"GPU数量 (gpu_num): {gpu_num}")
        print(f"GPU类型列表 (gpu_name_set): {gpu_names}")
        print(f"数据中心列表 (dc_list): {dc_codes}")
        print(f"启动命令 (cmd): {cmd}")
        print(f"\n注意: 环境变量已通过 env.sh 脚本文件传递，不再通过 API 参数传递")
        print("="*80 + "\n")
        
        try:
            # 调用 create_deployment 方法
            print(f"\n>>> 正在调用 client.create_deployment()...")
            print(f"调用参数明细:")
            print(f"  name = '{name}'")
            print(f"  image_uuid = '{image_uuid}'")
            print(f"  deployment_type = '{deployment_type}'")
            print(f"  replica_num = {replica_num}")
            print(f"  parallelism_num = {parallelism_num}")
            print(f"  gpu_name_set = {gpu_names}")
            print(f"  gpu_num = {gpu_num}")
            print(f"  dc_list = {dc_codes}")
            print(f"  cmd = '{cmd}'")
            print(f"<<<\n")
            
            deployment_uuid = client.create_deployment(
                name=name,
                image_uuid=image_uuid,
                deployment_type=deployment_type,
                replica_num=replica_num,
                parallelism_num=parallelism_num,
                gpu_name_set=gpu_names,
                gpu_num=gpu_num,
                dc_list=dc_codes,
                cmd=cmd
            )
            print(f"\n✓✓✓ 部署创建成功！部署UUID: {deployment_uuid}\n")
            
            # 保存任务提交配置（自动保存当前界面所有设置）
            try:
                # 获取前端传递的完整配置信息（包括运行脚本内容等）
                run_script_type = data.get('run_script_type', 'shell')
                run_script_content = data.get('run_script_content', '')
                history_script = data.get('history_script', '')
                
                config_data = {
                    'name': name,
                    'deployment_type': deployment_type,
                    'image_uuid': image_uuid,
                    'dc_list': dc_list,  # 中文名称列表
                    'gpu_num': gpu_num,
                    'gpu_name_set': gpu_name_set,  # GPU类型列表
                    'env_vars': env_vars_for_config,  # 从请求数据获取，用于保存配置
                    'replica_num': replica_num,
                    'parallelism_num': parallelism_num,
                    'cmd': cmd,
                    'run_script_type': run_script_type,
                    'run_script_content': run_script_content,
                    'history_script': history_script if history_script else None,
                    'deployment_uuid': deployment_uuid,
                    'created_at': datetime.now().isoformat()
                }
                # 保存到提交记录，不保存到历史配置
                save_deployment_record(username, config_data)
            except Exception as e:
                print(f"Warning: Failed to save deployment record: {e}")
                import traceback
                traceback.print_exc()
                # 不影响部署创建，只记录警告
            
            return jsonify({
                'success': True,
                'deployment_uuid': deployment_uuid,
                'message': f'部署创建成功！部署UUID: {deployment_uuid}'
            })
        except AttributeError as e:
            return jsonify({
                'error': f'create_deployment 方法不存在。请检查 autodl-api 库的版本。错误：{str(e)}'
            }), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== 任务提交配置管理 API ====================

@app.route('/api/autodl/deployment-configs', methods=['GET'])
@login_required
def list_deployment_configs():
    """列出所有任务提交配置（支持分组过滤和分页）"""
    try:
        username = session.get('username', 'admin')
        config_dir = get_user_deployment_config_dir(username)
        configs = []
        
        # 获取查询参数
        group = request.args.get('group', '').strip()  # 分组过滤
        page = int(request.args.get('page', 1))  # 页码，从1开始
        per_page = int(request.args.get('per_page', 10))  # 每页数量
        
        # 确定搜索目录
        if group:
            search_dir = config_dir / group
        else:
            search_dir = config_dir
        
        if search_dir.exists():
            # 搜索所有配置文件（包括子目录）
            for file_path in search_dir.rglob('deployment_config_*.json'):
                try:
                    stat = file_path.stat()
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    # 获取相对路径，用于确定分组
                    relative_path = file_path.relative_to(config_dir)
                    file_group = None
                    if len(relative_path.parts) > 1:
                        file_group = relative_path.parts[0]  # 第一级目录名作为分组
                    
                    configs.append({
                        'filename': file_path.stem,  # 不含扩展名
                        'full_filename': file_path.name,  # 完整文件名
                        'relative_path': str(relative_path),  # 相对路径，用于删除
                        'config': config_data,
                        'group': file_group or config_data.get('group', ''),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception as e:
                    print(f"Error reading config {file_path}: {e}")
                    continue
        
        # 按修改时间倒序排列（最新的在前）
        configs = sorted(configs, key=lambda x: x['modified'], reverse=True)
        
        # 分页处理
        total = len(configs)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_configs = configs[start:end]
        
        return jsonify({
            'configs': paginated_configs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page  # 总页数
            }
        })
    except Exception as e:
        print(f"Error listing deployment configs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-configs/<path:relative_path>', methods=['GET'])
@login_required
def get_deployment_config(relative_path):
    """获取特定的任务提交配置（支持分组路径）"""
    try:
        username = session.get('username', 'admin')
        config_dir = get_user_deployment_config_dir(username)
        
        # 确保是JSON文件
        if not relative_path.endswith('.json'):
            relative_path += '.json'
        
        config_file = config_dir / relative_path
        
        if not config_file.exists():
            return jsonify({'error': '配置不存在'}), 404
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return jsonify({
            'success': True,
            'config': config_data,
            'filename': config_file.stem,
            'relative_path': relative_path
        })
    except Exception as e:
        print(f"Error getting deployment config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-configs/<path:relative_path>', methods=['DELETE'])
@login_required
def delete_deployment_config(relative_path):
    """删除任务提交配置（支持分组路径）"""
    try:
        username = session.get('username', 'admin')
        config_dir = get_user_deployment_config_dir(username)
        
        # 确保是JSON文件
        if not relative_path.endswith('.json'):
            relative_path += '.json'
        
        config_file = config_dir / relative_path
        
        if not config_file.exists():
            return jsonify({'error': '配置不存在'}), 404
        
        # 删除配置文件
        config_file.unlink()
        
        print(f"✓ Deployment config deleted: {config_file}")
        return jsonify({'success': True, 'message': '配置删除成功'})
    except Exception as e:
        print(f"Error deleting deployment config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-configs', methods=['POST'])
@login_required
def save_deployment_config_api():
    """手动保存任务提交配置（不创建部署）"""
    try:
        username = session.get('username', 'admin')
        data = request.json
        
        # 获取分组信息
        group = data.get('group', '').strip() or None
        
        # 收集所有配置信息
        config_data = {
            'name': data.get('name', '').strip() or '未命名配置',
            'deployment_type': data.get('deployment_type', 'Job'),
            'image_uuid': data.get('image_uuid', ''),
            'dc_list': data.get('dc_list', []),
            'gpu_num': data.get('gpu_num', 1),
            'gpu_name_set': data.get('gpu_name_set', []),
            'env_vars': data.get('env_vars', {}),
            'replica_num': data.get('replica_num', 1),
            'parallelism_num': data.get('parallelism_num', None),
            'cmd': data.get('cmd', ''),
            'run_script_type': data.get('run_script_type', 'shell'),
            'run_script_content': data.get('run_script_content', ''),
            'history_script': data.get('history_script', None),
            'created_at': datetime.now().isoformat()
        }
        
        save_deployment_config(username, config_data, group=group)
        
        return jsonify({
            'success': True,
            'message': '配置保存成功'
        })
    except Exception as e:
        print(f"Error saving deployment config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-configs/groups', methods=['GET'])
@login_required
def list_deployment_config_groups():
    """获取所有配置分组列表"""
    try:
        username = session.get('username', 'admin')
        config_dir = get_user_deployment_config_dir(username)
        groups = set()
        
        if config_dir.exists():
            # 遍历所有子目录作为分组
            for item in config_dir.iterdir():
                if item.is_dir():
                    groups.add(item.name)
        
        return jsonify({
            'groups': sorted(list(groups))
        })
    except Exception as e:
        print(f"Error listing deployment config groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-configs/move', methods=['POST'])
@login_required
def move_deployment_config():
    """移动配置到指定分组"""
    try:
        username = session.get('username', 'admin')
        config_dir = get_user_deployment_config_dir(username)
        data = request.json
        
        relative_path = data.get('relative_path', '')
        target_group = data.get('group', '').strip() or None
        
        if not relative_path:
            return jsonify({'error': '缺少配置路径'}), 400
        
        # 确保是JSON文件
        if not relative_path.endswith('.json'):
            relative_path += '.json'
        
        source_file = config_dir / relative_path
        
        if not source_file.exists():
            return jsonify({'error': '配置不存在'}), 404
        
        # 读取配置数据
        with open(source_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 更新分组信息
        if target_group:
            config_data['group'] = target_group
        
        # 确定目标目录和文件
        if target_group:
            target_dir = config_dir / target_group
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / source_file.name
        else:
            target_file = config_dir / source_file.name
        
        # 如果目标文件与源文件不同，移动文件
        if target_file != source_file:
            # 保存到新位置
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            # 删除原文件
            source_file.unlink()
        
        print(f"✓ Deployment config moved: {source_file} -> {target_file}")
        return jsonify({
            'success': True,
            'message': '配置移动成功',
            'relative_path': str(target_file.relative_to(config_dir))
        })
    except Exception as e:
        print(f"Error moving deployment config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== 提交记录管理 API ====================

@app.route('/api/autodl/deployment-records', methods=['GET'])
@login_required
def list_deployment_records():
    """列出所有提交记录（支持分页）"""
    try:
        username = session.get('username', 'admin')
        records_dir = get_user_deployment_records_dir(username)
        records = []
        
        # 获取查询参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        if records_dir.exists():
            for file_path in records_dir.glob('deployment_record_*.json'):
                try:
                    stat = file_path.stat()
                    with open(file_path, 'r', encoding='utf-8') as f:
                        record_data = json.load(f)
                    
                    records.append({
                        'filename': file_path.stem,
                        'full_filename': file_path.name,
                        'relative_path': file_path.name,
                        'record': record_data,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception as e:
                    print(f"Error reading record {file_path}: {e}")
                    continue
        
        # 按修改时间倒序排列
        records = sorted(records, key=lambda x: x['modified'], reverse=True)
        
        # 分页处理
        total = len(records)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_records = records[start:end]
        
        return jsonify({
            'records': paginated_records,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        print(f"Error listing deployment records: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-records/<record_filename>', methods=['GET'])
@login_required
def get_deployment_record(record_filename):
    """获取特定的提交记录"""
    try:
        username = session.get('username', 'admin')
        records_dir = get_user_deployment_records_dir(username)
        
        if not record_filename.endswith('.json'):
            record_filename += '.json'
        
        record_file = records_dir / record_filename
        
        if not record_file.exists():
            return jsonify({'error': '记录不存在'}), 404
        
        with open(record_file, 'r', encoding='utf-8') as f:
            record_data = json.load(f)
        
        return jsonify({
            'success': True,
            'record': record_data,
            'filename': record_file.stem
        })
    except Exception as e:
        print(f"Error getting deployment record: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-records/<record_filename>', methods=['DELETE'])
@login_required
def delete_deployment_record(record_filename):
    """删除提交记录"""
    try:
        username = session.get('username', 'admin')
        records_dir = get_user_deployment_records_dir(username)
        
        if not record_filename.endswith('.json'):
            record_filename += '.json'
        
        record_file = records_dir / record_filename
        
        if not record_file.exists():
            return jsonify({'error': '记录不存在'}), 404
        
        record_file.unlink()
        
        print(f"✓ Deployment record deleted: {record_file}")
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        print(f"Error deleting deployment record: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/autodl/deployment-records/<record_filename>/save-to-config', methods=['POST'])
@login_required
def save_record_to_config(record_filename):
    """将提交记录保存到历史配置"""
    try:
        username = session.get('username', 'admin')
        records_dir = get_user_deployment_records_dir(username)
        data = request.json
        
        if not record_filename.endswith('.json'):
            record_filename += '.json'
        
        record_file = records_dir / record_filename
        
        if not record_file.exists():
            return jsonify({'error': '记录不存在'}), 404
        
        with open(record_file, 'r', encoding='utf-8') as f:
            record_data = json.load(f)
        
        group = data.get('group', '').strip() or None
        
        # 移除记录标记
        if 'is_record' in record_data:
            del record_data['is_record']
        
        # 保存到历史配置
        save_deployment_config(username, record_data, group=group)
        
        return jsonify({
            'success': True,
            'message': '记录已保存到历史配置' + (f'（分组: {group}）' if group else '')
        })
    except Exception as e:
        print(f"Error saving record to config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== 实验管理 API 路由 ====================

@app.route('/api/experiments/list', methods=['GET'])
@login_required
def list_experiments():
    """获取实验列表（占位功能）"""
    try:
        # 这里是占位实现，后续可以根据实际需求完善
        experiments = []
        return jsonify({'experiments': experiments})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6008)

