"""
CategoryService 单元测试
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from backend.services.category_service import CategoryService


class TestCategoryService:
    """CategoryService 测试类"""
    
    def test_init(self):
        """测试初始化"""
        service = CategoryService()
        assert service is not None
    
    @patch('backend.services.category_service.CATEGORY_GROUPS_FILE')
    def test_load_category_groups_exists(self, mock_file, temp_dir, sample_category_groups):
        """测试加载存在的类别映射组"""
        service = CategoryService()
        category_file = temp_dir / 'category_groups.json'
        with open(category_file, 'w', encoding='utf-8') as f:
            json.dump(sample_category_groups, f, ensure_ascii=False, indent=2)
        
        mock_file.__class__ = Path
        mock_file.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=json.dumps(sample_category_groups))):
            groups = service.load_category_groups()
            assert groups == sample_category_groups
    
    @patch('backend.services.category_service.CATEGORY_GROUPS_FILE')
    def test_load_category_groups_not_exists(self, mock_file):
        """测试加载不存在的类别映射组"""
        service = CategoryService()
        mock_file.__class__ = Path
        mock_file.exists.return_value = False
        
        groups = service.load_category_groups()
        assert groups == []
    
    @patch('backend.services.category_service.CATEGORY_GROUPS_FILE')
    def test_load_category_groups_invalid_json(self, mock_file, temp_dir):
        """测试加载无效JSON的类别映射组"""
        service = CategoryService()
        category_file = temp_dir / 'category_groups.json'
        with open(category_file, 'w', encoding='utf-8') as f:
            f.write('invalid json')
        
        mock_file.__class__ = Path
        mock_file.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data='invalid json')):
            groups = service.load_category_groups()
            # 应该返回空列表（异常被捕获）
            assert groups == []
    
    def test_save_category_groups(self, temp_dir, sample_category_groups, monkeypatch):
        """测试保存类别映射组"""
        service = CategoryService()
        category_file = temp_dir / 'category_groups.json'
        
        # 使用 monkeypatch 替换 CATEGORY_GROUPS_FILE
        from backend.services import category_service
        original_file = category_service.CATEGORY_GROUPS_FILE
        monkeypatch.setattr(category_service, 'CATEGORY_GROUPS_FILE', category_file)
        
        try:
            result = service.save_category_groups(sample_category_groups)
            
            assert result is True
            assert category_file.exists()
            with open(category_file, 'r', encoding='utf-8') as f:
                saved_groups = json.load(f)
                assert saved_groups == sample_category_groups
        finally:
            monkeypatch.setattr(category_service, 'CATEGORY_GROUPS_FILE', original_file)
    
    @patch('backend.services.category_service.get_user_config_file')
    def test_load_user_category_groups_exists(self, mock_get_file, temp_dir):
        """测试加载存在的用户类别映射组"""
        service = CategoryService()
        config_file = temp_dir / 'user_config.json'
        user_groups = [{'name': 'user_group', 'mappings': {'1': 'test'}}]
        config = {'user_category_groups': user_groups}
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        mock_get_file.return_value = config_file
        
        groups = service.load_user_category_groups('test_user')
        assert groups == user_groups
    
    @patch('backend.services.category_service.get_user_config_file')
    def test_load_user_category_groups_not_exists(self, mock_get_file, temp_dir):
        """测试加载不存在的用户类别映射组"""
        service = CategoryService()
        config_file = temp_dir / 'nonexistent.json'
        mock_get_file.return_value = config_file
        
        groups = service.load_user_category_groups('test_user')
        assert groups == []
    
    @patch('backend.services.category_service.get_user_config_file')
    def test_load_user_category_groups_no_field(self, mock_get_file, temp_dir):
        """测试配置文件中没有用户类别映射组字段"""
        service = CategoryService()
        config_file = temp_dir / 'user_config.json'
        config = {'repos': {}}
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        mock_get_file.return_value = config_file
        
        groups = service.load_user_category_groups('test_user')
        assert groups == []
    
    @patch('backend.services.category_service.get_user_config_file')
    def test_save_user_category_groups(self, mock_get_file, temp_dir):
        """测试保存用户类别映射组"""
        service = CategoryService()
        config_file = temp_dir / 'user_config.json'
        mock_get_file.return_value = config_file
        
        user_groups = [{'name': 'user_group', 'mappings': {'1': 'test'}}]
        result = service.save_user_category_groups('test_user', user_groups)
        
        assert result is True
        assert config_file.exists()
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            assert config['user_category_groups'] == user_groups
    
    @patch('backend.services.category_service.get_user_config_file')
    def test_save_user_category_groups_existing_config(self, mock_get_file, temp_dir):
        """测试保存用户类别映射组到已存在的配置"""
        service = CategoryService()
        config_file = temp_dir / 'user_config.json'
        existing_config = {
            'repos': {'test': {'url': 'https://example.com'}},
            'data_download': {}
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, ensure_ascii=False, indent=2)
        
        mock_get_file.return_value = config_file
        
        user_groups = [{'name': 'user_group', 'mappings': {'1': 'test'}}]
        result = service.save_user_category_groups('test_user', user_groups)
        
        assert result is True
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            assert config['user_category_groups'] == user_groups
            # 原有配置应该保留
            assert config['repos'] == existing_config['repos']

