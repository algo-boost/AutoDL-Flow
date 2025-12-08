"""
AutoDL Flow - 路由模块
"""
from .auth_routes import register_auth_routes
from .view_routes import register_view_routes
from .api_routes import register_api_routes


def register_routes(app):
    """注册所有路由"""
    register_auth_routes(app)
    register_view_routes(app)
    register_api_routes(app)

