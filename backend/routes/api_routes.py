"""
AutoDL Flow - API 路由
"""
from flask import Blueprint

# 创建 API 蓝图
api_bp = Blueprint('api', __name__, url_prefix='/api')


def register_api_routes(app):
    """注册 API 路由"""
    # 导入各个 API 路由模块
    from .api import (
        script_routes,
        config_routes,
        account_routes,
        autodl_routes,
        category_routes,
        user_routes,
        experiment_routes
    )
    
    # 注册各个 API 路由模块
    script_routes.register_routes(api_bp)
    config_routes.register_routes(api_bp)
    account_routes.register_routes(api_bp)
    autodl_routes.register_routes(api_bp)
    category_routes.register_routes(api_bp)
    user_routes.register_routes(api_bp)
    experiment_routes.register_routes(api_bp)
    
    # 注册蓝图
    app.register_blueprint(api_bp)

