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

# 百度网盘脚本目录
BAIDU_NETDISK_SCRIPTS_DIR = '/apps/autodl/scripts'

# Flask 配置
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'change-this-secret-key-in-production-' + str(os.urandom(16)))

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

