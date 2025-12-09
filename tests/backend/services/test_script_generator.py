"""
ScriptGenerator 单元测试
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from backend.services.script_generator import ScriptGenerator


class TestScriptGenerator:
    """ScriptGenerator 测试类"""
    
    def test_init(self, sample_repos, sample_data_download_config, sample_models):
        """测试初始化"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        assert generator.repos == sample_repos
        assert generator.data_download_config == sample_data_download_config
        assert generator.models == sample_models
    
    def test_generate_script_basic(self, sample_repos, sample_data_download_config, sample_models):
        """测试基本脚本生成"""
        generator = ScriptGenerator({}, {}, {})
        script = generator.generate_script(
            selected_repos=[],
            snapshots=[],
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user'
        )
        assert '#!/usr/bin/env bash' in script
        assert 'test_dataset' in script
        assert 'set -e' in script
        assert 'set -u' in script
        assert 'set -o pipefail' in script
    
    def test_generate_script_with_repos(self, sample_repos, sample_data_download_config, sample_models):
        """测试包含仓库的脚本生成"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        selected_repos = [
            {'name': 'cv-scripts', 'install': True}
        ]
        script = generator.generate_script(
            selected_repos=selected_repos,
            snapshots=[],
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            enable_repos=True
        )
        assert 'git clone' in script
        assert 'cv-scripts' in script
        assert 'pip install -e .' in script
    
    def test_generate_script_with_snapshots(self, sample_repos, sample_data_download_config, sample_models):
        """测试包含快照的脚本生成"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        snapshots = [
            {
                'id': '12345',
                'name': 'test_snapshot',
                'cache': True
            }
        ]
        script = generator.generate_script(
            selected_repos=[],
            snapshots=snapshots,
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            enable_snapshots=True
        )
        assert 'test_snapshot' in script
        assert 'moli_dataset_export.py' in script or 'bdnd' in script
    
    def test_generate_script_with_models(self, sample_repos, sample_data_download_config, sample_models):
        """测试包含模型的脚本生成"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        selected_models = [
            {'name': 'model1', 'cache': True}
        ]
        script = generator.generate_script(
            selected_repos=[],
            snapshots=[],
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            selected_models=selected_models
        )
        assert 'model1' in script
        assert '/root/autodl-tmp/model' in script
    
    def test_generate_script_with_category_group(self, sample_repos, sample_data_download_config, sample_models):
        """测试包含类别映射组的脚本生成"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        snapshots = [
            {
                'id': '12345',
                'name': 'test_snapshot',
                'cache': True
            }
        ]
        script = generator.generate_script(
            selected_repos=[],
            snapshots=snapshots,
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            enable_snapshots=True,
            category_group='test_group'
        )
        assert '--category-group' in script
        assert 'test_group' in script
    
    def test_generate_script_data_only(self, sample_repos, sample_data_download_config, sample_models):
        """测试仅数据模式"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        script = generator.generate_script(
            selected_repos=[],
            snapshots=[],
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            data_only=True
        )
        assert 'git clone' not in script or 'cv-scripts' not in script
    
    def test_parse_snapshot_data_dict(self, sample_repos, sample_data_download_config, sample_models):
        """测试解析字典格式的快照数据"""
        generator = ScriptGenerator({}, {}, {})
        snapshot_data = {
            'id': '12345',
            'url': 'https://example.com/data.zip',
            'bdnd_path': '/apps/autodl/data.zip',
            'name': 'test_snapshot',
            'cache': True
        }
        snapshot_id, snapshot_url, snapshot_bdnd_path, snapshot_name, enable_cache = \
            generator._parse_snapshot_data(snapshot_data)
        assert snapshot_id == '12345'
        assert snapshot_url == 'https://example.com/data.zip'
        assert snapshot_bdnd_path == '/apps/autodl/data.zip'
        assert snapshot_name == 'test_snapshot'
        assert enable_cache is True
    
    def test_parse_snapshot_data_tuple(self, sample_repos, sample_data_download_config, sample_models):
        """测试解析元组格式的快照数据"""
        generator = ScriptGenerator({}, {}, {})
        snapshot_data = ('12345', 'test_snapshot')
        snapshot_id, snapshot_url, snapshot_bdnd_path, snapshot_name, enable_cache = \
            generator._parse_snapshot_data(snapshot_data)
        assert snapshot_id == '12345'
        assert snapshot_name == 'test_snapshot'
        assert snapshot_url == ''
        assert snapshot_bdnd_path == ''
        assert enable_cache is True
    
    def test_determine_snapshot_name(self, sample_repos, sample_data_download_config, sample_models):
        """测试确定快照名称"""
        generator = ScriptGenerator({}, {}, {})
        
        # 测试有名称的情况
        name = generator._determine_snapshot_name('test_name', False, '', False, '', False, '')
        assert name == 'test_name'
        
        # 测试使用ID的情况
        name = generator._determine_snapshot_name('', True, '12345', False, '', False, '')
        assert name == 'snapshot_12345'
        
        # 测试使用bdnd路径的情况
        name = generator._determine_snapshot_name('', False, '', True, '/apps/autodl/data.zip', False, '')
        assert name == 'data'
    
    def test_parse_model_item_dict(self, sample_repos, sample_data_download_config, sample_models):
        """测试解析字典格式的模型项"""
        generator = ScriptGenerator({}, {}, {})
        model_item = {'name': 'model1', 'cache': False}
        model_name, enable_cache = generator._parse_model_item(model_item)
        assert model_name == 'model1'
        assert enable_cache is False
    
    def test_parse_model_item_string(self, sample_repos, sample_data_download_config, sample_models):
        """测试解析字符串格式的模型项"""
        generator = ScriptGenerator({}, {}, {})
        model_item = 'model1'
        model_name, enable_cache = generator._parse_model_item(model_item)
        assert model_name == 'model1'
        assert enable_cache is True
    
    @patch('backend.services.script_generator.get_user_env_config_file')
    def test_get_env_config_content(self, mock_get_file, sample_repos, sample_data_download_config, 
                                     sample_models, mock_env_config_file):
        """测试获取环境配置内容"""
        generator = ScriptGenerator({}, {}, {})
        env_file, env_config = mock_env_config_file
        mock_get_file.return_value = env_file
        
        content = generator._get_env_config_content('test_user')
        # 应该返回压缩后的JSON
        assert 'test_key' in content
        assert 'test_value' in content
        # 验证是有效的JSON
        parsed = json.loads(content)
        assert parsed['test_key'] == 'test_value'
    
    @patch('backend.services.script_generator.get_user_env_config_file')
    def test_get_env_config_content_missing_file(self, mock_get_file, sample_repos, 
                                                  sample_data_download_config, sample_models, temp_dir):
        """测试获取不存在的环境配置文件"""
        generator = ScriptGenerator({}, {}, {})
        env_file = temp_dir / '.env_config.json'
        mock_get_file.return_value = env_file
        
        content = generator._get_env_config_content('test_user')
        # 应该返回空JSON
        assert content == '{}'
    
    def test_generate_script_with_split_ratio(self, sample_repos, sample_data_download_config, sample_models):
        """测试包含划分比例的脚本生成"""
        generator = ScriptGenerator(
            sample_repos,
            sample_data_download_config,
            sample_models
        )
        snapshots = [
            {'id': '12345', 'name': 'test_snapshot', 'cache': True}
        ]
        script = generator.generate_script(
            selected_repos=[],
            snapshots=snapshots,
            output_dir='/root/test',
            dataset_name='test_dataset',
            username='test_user',
            enable_snapshots=True,
            enable_merge=True,
            split_ratio='0.8',
            split_seed=42
        )
        assert 'split_coco.py' in script
        assert '0.8' in script
        assert '42' in script

