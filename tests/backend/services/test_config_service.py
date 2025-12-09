"""
ConfigService 单元测试
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from backend.services.config_service import ConfigService


class TestConfigService:
    """ConfigService 测试类"""
    
    def test_init(self):
        """测试初始化"""
        service = ConfigService()
        assert service.category_service is not None
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    def test_load_user_config_exists(self, mock_is_admin, mock_get_file, temp_dir, sample_user_config):
        """测试加载存在的用户配置"""
        service = ConfigService()
        config_file, config = sample_user_config
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = False
        
        repos, data_download, category_groups, models, bdnd_config = service.load_user_config('test_user')
        
        assert repos == config['repos']
        assert data_download == config['data_download']
        assert models == config['models']
        assert bdnd_config == config['bdnd_config']
        assert isinstance(category_groups, list)
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    @patch('backend.services.config_service.CONFIG_FILE')
    @patch('backend.services.config_service.CategoryService')
    def test_load_user_config_admin_fallback(self, mock_category_service, mock_config_file, 
                                             mock_is_admin, mock_get_file, temp_dir, sample_user_config):
        """测试管理员用户回退到全局配置"""
        service = ConfigService()
        config_file, config = sample_user_config
        mock_get_file.return_value = Path(temp_dir / 'nonexistent.json')
        mock_is_admin.return_value = True
        
        # Mock category_service 返回空列表
        mock_category_instance = MagicMock()
        mock_category_instance.load_category_groups.return_value = []
        mock_category_instance.load_user_category_groups.return_value = []
        mock_category_service.return_value = mock_category_instance
        service.category_service = mock_category_instance
        
        # 创建全局配置文件
        global_config_file = temp_dir / 'repos_config.json'
        with open(global_config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # Mock CONFIG_FILE
        mock_config_file_path = MagicMock()
        mock_config_file_path.exists.return_value = True
        mock_config_file_path.__str__ = lambda x: str(global_config_file)
        
        with patch('backend.services.config_service.CONFIG_FILE', mock_config_file_path):
            with patch('builtins.open', mock_open(read_data=json.dumps(config))):
                repos, data_download, category_groups, models, bdnd_config = service.load_user_config('admin')
                assert isinstance(repos, dict)
                assert isinstance(category_groups, list)
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    def test_load_user_config_not_exists(self, mock_is_admin, mock_get_file, temp_dir):
        """测试加载不存在的用户配置"""
        service = ConfigService()
        config_file = temp_dir / 'nonexistent.json'
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = False
        
        repos, data_download, category_groups, models, bdnd_config = service.load_user_config('test_user')
        
        assert repos == {}
        assert data_download == {}
        assert models == {}
        assert bdnd_config == {}
        assert isinstance(category_groups, list)
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    def test_save_user_config(self, mock_is_admin, mock_get_file, temp_dir, sample_user_config):
        """测试保存用户配置"""
        service = ConfigService()
        config_file, _ = sample_user_config
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = False
        
        new_repos = {'new_repo': {'url': 'https://example.com/new.git'}}
        result = service.save_user_config('test_user', repos=new_repos)
        
        assert result is True
        # 验证文件已保存
        assert config_file.exists()
        with open(config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
            assert saved_config['repos'] == new_repos
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    def test_save_user_config_partial_update(self, mock_is_admin, mock_get_file, temp_dir, sample_user_config):
        """测试部分更新用户配置"""
        service = ConfigService()
        config_file, original_config = sample_user_config
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = False
        
        # 只更新 repos
        new_repos = {'new_repo': {'url': 'https://example.com/new.git'}}
        result = service.save_user_config('test_user', repos=new_repos)
        
        assert result is True
        with open(config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
            assert saved_config['repos'] == new_repos
            # 其他配置应该保持不变（从原始配置加载）
            assert 'data_download' in saved_config
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    @patch('backend.services.config_service.CategoryService')
    def test_save_user_config_category_groups_admin(self, mock_category_service, 
                                                    mock_is_admin, mock_get_file, temp_dir, 
                                                    sample_category_groups):
        """测试管理员保存类别映射组"""
        service = ConfigService()
        config_file = temp_dir / 'user_config.json'
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = True
        
        # 使用真实的 CategoryService 实例
        from backend.services.category_service import CategoryService
        real_category_service = CategoryService()
        service.category_service = real_category_service
        
        # 临时替换 CATEGORY_GROUPS_FILE 到临时目录
        import backend.services.category_service as cat_module
        temp_category_file = temp_dir / 'category_groups.json'
        original_cat_file = cat_module.CATEGORY_GROUPS_FILE
        cat_module.CATEGORY_GROUPS_FILE = temp_category_file
        
        try:
            result = service.save_user_config('admin', category_groups=sample_category_groups)
            
            assert result is True
            assert temp_category_file.exists()
            # 验证保存的内容
            import json
            with open(temp_category_file, 'r', encoding='utf-8') as f:
                saved_groups = json.load(f)
                assert saved_groups == sample_category_groups
        finally:
            cat_module.CATEGORY_GROUPS_FILE = original_cat_file
    
    @patch('backend.services.config_service.get_user_config_file')
    @patch('backend.services.config_service.is_admin')
    def test_save_user_config_category_groups_non_admin(self, mock_is_admin, mock_get_file, temp_dir):
        """测试非管理员不能保存全局类别映射组"""
        service = ConfigService()
        config_file = temp_dir / 'user_config.json'
        mock_get_file.return_value = config_file
        mock_is_admin.return_value = False
        
        result = service.save_user_config('test_user', category_groups=[{'name': 'test'}])
        
        assert result is False

