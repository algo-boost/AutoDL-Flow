"""
AutoDL Flow - 配置管理模块
"""
from pathlib import Path
import os

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 配置文件路径
CONFIG_FILE = BASE_DIR / 'repos_config.json'
ACCOUNTS_FILE = BASE_DIR / '.accounts.json'
CATEGORY_GROUPS_FILE = BASE_DIR / '.category_groups.json'
ENCRYPTION_KEY_FILE = BASE_DIR / '.encryption_key'
RUN_SCRIPT_TEMPLATES_FILE = BASE_DIR / 'run_script_templates.json'

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

# 存储目录配置（使用项目目录内的相对路径，方便打包迁移）
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS_STORAGE_DIR = DATA_DIR / 'scripts'
SCRIPTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CONFIGS_STORAGE_DIR = DATA_DIR / 'configs'
CONFIGS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

TEMP_SCRIPTS_DIR = DATA_DIR / 'temp_scripts'
TEMP_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

DEPLOYMENT_CONFIGS_DIR = DATA_DIR / 'deployment_configs'
DEPLOYMENT_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

DEPLOYMENT_RECORDS_DIR = DATA_DIR / 'deployment_records'
DEPLOYMENT_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

# 文件上传存储目录
UPLOADED_FILES_DIR = DATA_DIR / 'uploaded_files'
UPLOADED_FILES_DIR.mkdir(parents=True, exist_ok=True)

# 百度网盘脚本目录
BAIDU_NETDISK_SCRIPTS_DIR = '/apps/autodl/scripts'

# Flask 配置 - 密钥管理
def get_secret_key():
    """
    获取 Flask SECRET_KEY
    
    安全策略：
    - 生产环境：必须从环境变量 FLASK_SECRET_KEY 读取，不允许默认值
    - 开发环境：允许使用临时生成的密钥（仅用于开发测试）
    - 密钥长度：至少 32 字符
    
    环境检测：
    - 只有当 FLASK_ENV=production 或 ENVIRONMENT=production 时，才认为是生产环境
    - 其他情况（包括未设置）都视为开发环境
    """
    # 检测是否为生产环境
    # 只有明确设置为 production 时才认为是生产环境
    flask_env_raw = os.environ.get('FLASK_ENV', '')
    environment_raw = os.environ.get('ENVIRONMENT', '')
    flask_env = flask_env_raw.strip().lower() if flask_env_raw else ''
    environment = environment_raw.strip().lower() if environment_raw else ''
    
    # 只有明确设置为 'production' 时才认为是生产环境
    # 空字符串、None、'development'、'dev' 等都视为开发环境
    is_production = (flask_env == 'production' or environment == 'production')
    
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    
    # 生产环境强制要求环境变量
    if is_production:
        if not secret_key:
            # 提供详细的诊断信息
            env_info = f"FLASK_ENV={repr(flask_env_raw)}, ENVIRONMENT={repr(environment_raw)}"
            raise ValueError(
                f"SECRET_KEY 未设置！检测到生产环境（{env_info}）\n"
                "生产环境必须通过环境变量 FLASK_SECRET_KEY 设置密钥。\n\n"
                "解决方案：\n"
                "1. 设置密钥：export FLASK_SECRET_KEY='your-secret-key-here'\n"
                "   建议使用强随机密钥，长度至少 32 字符。\n"
                "   生成密钥：python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"\n\n"
                "2. 如果是开发环境，请取消生产环境设置：\n"
                "   unset FLASK_ENV\n"
                "   unset ENVIRONMENT\n"
                "   或者设置：export FLASK_ENV=development"
            )
        if len(secret_key) < 32:
            raise ValueError(
                f"SECRET_KEY 长度不足！当前长度：{len(secret_key)}，要求至少 32 字符。\n"
                "请设置一个更长的密钥：export FLASK_SECRET_KEY='your-longer-secret-key-here'"
            )
        return secret_key
    
    # 开发环境：如果没有设置，生成临时密钥并警告
    if not secret_key:
        import secrets
        temp_key = secrets.token_urlsafe(32)
        print("=" * 70)
        print("⚠️  警告：未设置 FLASK_SECRET_KEY 环境变量")
        print("   当前使用临时生成的密钥（仅用于开发测试）")
        print("   生产环境必须设置：export FLASK_SECRET_KEY='your-secret-key'")
        print("=" * 70)
        return temp_key
    
    # 开发环境也建议使用足够长的密钥
    if len(secret_key) < 16:
        print(f"⚠️  警告：SECRET_KEY 长度较短（{len(secret_key)} 字符），建议至少 32 字符")
    
    return secret_key

SECRET_KEY = get_secret_key()

# 尝试导入可选依赖
try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("Warning: cryptography library not installed. Token encryption will be disabled.")

try:
    from autodl import AutoDLElasticDeployment
    AUTODL_AVAILABLE = True
except ImportError:
    AUTODL_AVAILABLE = False
    print("Warning: autodl-api library not installed. Task submission features will be limited.")

