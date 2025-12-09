"""
AccountService 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.services.account_service import AccountService


class TestAccountService:
    """AccountService 测试类"""
    
    def test_init(self):
        """测试初始化"""
        service = AccountService()
        assert service is not None
    
    @patch('backend.services.account_service.get_all_accounts')
    def test_get_all_accounts(self, mock_get_accounts, mock_accounts):
        """测试获取所有账户"""
        service = AccountService()
        mock_get_accounts.return_value = mock_accounts
        
        accounts = service.get_all_accounts()
        
        assert accounts == mock_accounts
        mock_get_accounts.assert_called_once()
    
    @patch('backend.services.account_service.save_accounts')
    @patch('backend.services.account_service.get_all_accounts')
    @patch('backend.services.account_service.hash_password')
    def test_add_account_success(self, mock_hash, mock_get, mock_save, mock_accounts):
        """测试成功添加账户"""
        service = AccountService()
        mock_get.return_value = {}
        mock_hash.return_value = 'hashed_password'
        mock_save.return_value = True
        
        success, message = service.add_account('new_user', 'password123')
        
        assert success is True
        assert '成功' in message
        mock_hash.assert_called_once_with('password123')
        mock_save.assert_called_once()
    
    @patch('backend.services.account_service.get_all_accounts')
    def test_add_account_exists(self, mock_get, mock_accounts):
        """测试添加已存在的账户"""
        service = AccountService()
        mock_get.return_value = {'existing_user': 'hashed_password'}
        
        success, message = service.add_account('existing_user', 'password123')
        
        assert success is False
        assert '已存在' in message
    
    @patch('backend.services.account_service.save_accounts')
    @patch('backend.services.account_service.get_all_accounts')
    @patch('backend.services.account_service.hash_password')
    def test_add_account_save_failed(self, mock_hash, mock_get, mock_save):
        """测试保存账户失败"""
        service = AccountService()
        mock_get.return_value = {}
        mock_hash.return_value = 'hashed_password'
        mock_save.return_value = False
        
        success, message = service.add_account('new_user', 'password123')
        
        assert success is False
        assert '失败' in message
    
    @patch('backend.services.account_service.save_accounts')
    @patch('backend.services.account_service.get_all_accounts')
    def test_delete_account_success(self, mock_get, mock_save, mock_accounts):
        """测试成功删除账户"""
        service = AccountService()
        accounts = {'test_user': 'hashed_password', 'other_user': 'hashed_password'}
        mock_get.return_value = accounts.copy()
        mock_save.return_value = True
        
        success, message = service.delete_account('test_user')
        
        assert success is True
        assert '成功' in message
        mock_save.assert_called_once()
        # 验证账户已从字典中删除
        call_args = mock_save.call_args[0][0]
        assert 'test_user' not in call_args
    
    @patch('backend.services.account_service.get_all_accounts')
    def test_delete_account_admin(self, mock_get, mock_accounts):
        """测试删除admin账户（应该失败）"""
        service = AccountService()
        
        success, message = service.delete_account('admin')
        
        assert success is False
        assert '不能删除' in message or 'admin' in message
    
    @patch('backend.services.account_service.get_all_accounts')
    def test_delete_account_not_exists(self, mock_get):
        """测试删除不存在的账户"""
        service = AccountService()
        mock_get.return_value = {}
        
        success, message = service.delete_account('nonexistent_user')
        
        assert success is False
        assert '不存在' in message
    
    @patch('backend.services.account_service.save_accounts')
    @patch('backend.services.account_service.get_all_accounts')
    @patch('backend.services.account_service.hash_password')
    def test_reset_password_success(self, mock_hash, mock_get, mock_save, mock_accounts):
        """测试成功重置密码"""
        service = AccountService()
        accounts = {'test_user': 'old_hashed_password'}
        mock_get.return_value = accounts.copy()
        mock_hash.return_value = 'new_hashed_password'
        mock_save.return_value = True
        
        success, message = service.reset_password('test_user', 'new_password')
        
        assert success is True
        assert '成功' in message
        mock_hash.assert_called_once_with('new_password')
        mock_save.assert_called_once()
    
    @patch('backend.services.account_service.get_all_accounts')
    def test_reset_password_not_exists(self, mock_get):
        """测试重置不存在的账户密码"""
        service = AccountService()
        mock_get.return_value = {}
        
        success, message = service.reset_password('nonexistent_user', 'new_password')
        
        assert success is False
        assert '不存在' in message
    
    @patch('backend.services.account_service.save_accounts')
    @patch('backend.services.account_service.get_all_accounts')
    @patch('backend.services.account_service.hash_password')
    def test_reset_password_save_failed(self, mock_hash, mock_get, mock_save):
        """测试重置密码保存失败"""
        service = AccountService()
        accounts = {'test_user': 'old_hashed_password'}
        mock_get.return_value = accounts.copy()
        mock_hash.return_value = 'new_hashed_password'
        mock_save.return_value = False
        
        success, message = service.reset_password('test_user', 'new_password')
        
        assert success is False
        assert '失败' in message

