"""
AutoDL Flow - 账户管理 API 路由
"""
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.auth.utils import is_admin
from backend.services.account_service import AccountService
from urllib.parse import unquote


def register_routes(bp):
    """注册账户管理路由"""
    account_service = AccountService()
    
    @bp.route('/admin/accounts', methods=['GET'])
    @login_required
    def list_accounts():
        """获取账户列表（仅管理员）"""
        if not is_admin(session.get('username', '')):
            return jsonify({'error': 'Unauthorized'}), 403
        
        accounts = account_service.get_all_accounts()
        # 不返回密码哈希
        account_list = [{'username': username} for username in accounts.keys()]
        return jsonify({'accounts': account_list})
    
    @bp.route('/admin/accounts', methods=['POST'])
    @login_required
    def add_account():
        """添加账户（仅管理员）"""
        if not is_admin(session.get('username', '')):
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.json
        username = data.get('username', '')
        password = data.get('password', '')
        
        success, message = account_service.add_account(username, password)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
    
    @bp.route('/admin/accounts/<account_name>', methods=['DELETE'])
    @login_required
    def delete_account(account_name):
        """删除账户（仅管理员，不能删除admin）"""
        if not is_admin(session.get('username', '')):
            return jsonify({'error': 'Unauthorized'}), 403
        
        account_name = unquote(account_name)
        
        success, message = account_service.delete_account(account_name)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            status_code = 404 if '不存在' in message else 400
            return jsonify({'error': message}), status_code
    
    @bp.route('/admin/accounts/<account_name>/reset-password', methods=['POST'])
    @login_required
    def reset_account_password(account_name):
        """重置账户密码（仅管理员）"""
        if not is_admin(session.get('username', '')):
            return jsonify({'error': 'Unauthorized'}), 403
        
        account_name = unquote(account_name)
        data = request.json
        new_password = data.get('password', '').strip()
        
        if not new_password:
            return jsonify({'error': '新密码不能为空'}), 400
        
        success, message = account_service.reset_password(account_name, new_password)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            status_code = 404 if '不存在' in message else 500
            return jsonify({'error': message}), status_code

