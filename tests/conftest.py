"""
pytest 配置文件 - 提供测试用的 fixtures
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_repos():
    """示例仓库配置"""
    return {
        'cv-scripts': {
            'url': 'https://github.com/example/cv-scripts.git',
            'install_cmds': ['pip install -e .']
        },
        'test-repo': {
            'url': 'https://github.com/example/test-repo.git',
            'install_cmds': []
        }
    }


@pytest.fixture
def sample_data_download_config():
    """示例数据下载配置"""
    return {
        'script_remote_path': '/apps/autodl/dataset_down/',
        'script_local_path': '/root/dataset_down/',
        'dataset_cache_path': 'cache/datasets',
        'git_ssh_path': 'git_ssh_backup'
    }


@pytest.fixture
def sample_models():
    """示例模型配置"""
    return {
        'model1': {
            'url': 'https://example.com/model1.pth',
            'local_path': '/root/autodl-tmp/model',
            'filename': 'model1.pth'
        },
        'model2': {
            'remote_path': '/apps/autodl/models/model2',
            'local_path': '/root/autodl-tmp/model'
        }
    }


@pytest.fixture
def sample_category_groups():
    """示例类别映射组"""
    return [
        {
            'name': 'test_group',
            'mappings': {
                '1': 'person',
                '2': 'car'
            }
        }
    ]


@pytest.fixture
def sample_user_config(temp_dir):
    """创建示例用户配置文件"""
    config_file = temp_dir / 'user_config.json'
    config = {
        'repos': {
            'test-repo': {
                'url': 'https://github.com/example/test.git',
                'install_cmds': []
            }
        },
        'data_download': {
            'script_remote_path': '/apps/autodl/dataset_down/',
            'script_local_path': '/root/dataset_down/'
        },
        'models': {
            'test_model': {
                'url': 'https://example.com/model.pth',
                'local_path': '/root/autodl-tmp/model'
            }
        },
        'bdnd_config': {}
    }
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return config_file, config


@pytest.fixture
def mock_env_config_file(temp_dir):
    """创建模拟的 .env_config.json 文件"""
    env_config_file = temp_dir / '.env_config.json'
    env_config = {
        'test_key': 'test_value'
    }
    with open(env_config_file, 'w', encoding='utf-8') as f:
        json.dump(env_config, f, ensure_ascii=False, indent=2)
    return env_config_file, env_config


@pytest.fixture
def mock_accounts():
    """模拟账户数据"""
    return {
        'admin': 'hashed_password_admin',
        'test_user': 'hashed_password_test'
    }

