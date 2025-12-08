"""
AutoDL Flow - 认证路由
"""
from flask import render_template, request, jsonify, session, redirect, url_for
from backend.auth.utils import verify_account, is_admin


def register_auth_routes(app):
    """注册认证相关路由"""
    
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
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='用户名或密码错误')
        
        # 如果已登录，重定向到主菜单
        if session.get('logged_in'):
            return redirect(url_for('dashboard'))
        
        return render_template('login.html')
    
    @app.route('/logout', methods=['POST'])
    def logout():
        """登出"""
        session.clear()
        return jsonify({'success': True})

