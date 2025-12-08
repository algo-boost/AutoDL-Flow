"""
AutoDL Flow - 视图路由
"""
from flask import render_template, session, redirect, url_for
from backend.config import AUTODL_AVAILABLE
from backend.services.config_service import ConfigService


def register_view_routes(app):
    """注册视图路由"""
    config_service = ConfigService()
    
    @app.route('/')
    def dashboard():
        """主菜单页面"""
        # 检查是否已登录
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        # 获取用户信息
        username = session.get('username', 'admin')
        
        return render_template('dashboard.html', username=username)
    
    @app.route('/task_setup')
    def task_setup():
        """任务设置页面（原 index 页面）"""
        # 检查是否已登录
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        # 获取用户信息
        username = session.get('username', 'admin')
        is_admin_user = session.get('is_admin', False)
        
        # 按用户加载配置（支持热更新）
        repos, _, _, models, _ = config_service.load_user_config(username)
        
        return render_template('index.html', 
                             repos=repos, 
                             models=models,
                             username=username,
                             is_admin=is_admin_user)
    
    @app.route('/task_submit')
    def task_submit():
        """任务提交页面"""
        # 检查是否已登录
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        username = session.get('username', 'admin')
        return render_template('task_submit.html', 
                             username=username, 
                             autodl_available=AUTODL_AVAILABLE)
    
    @app.route('/experiment_manage')
    def experiment_manage():
        """实验管理页面"""
        # 检查是否已登录
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        username = session.get('username', 'admin')
        return render_template('experiment_manage.html', username=username)

