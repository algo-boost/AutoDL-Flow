#!/usr/bin/env python3
"""
AutoDL Flow - Flask Web工具：自动生成作业执行脚本
重构后的主应用文件
"""
import logging
from flask import Flask
from backend.config import SECRET_KEY, AUTODL_AVAILABLE
from backend.routes import register_routes
from backend.utils.logging_config import setup_logging
from backend.utils.errors import (
    APIError, 
    handle_api_error, 
    handle_generic_error
)

# 初始化日志系统
setup_logging(log_level=logging.INFO)

# 创建 Flask 应用
app = Flask(__name__, 
            template_folder='frontend/templates',
            static_folder='frontend/static')
app.secret_key = SECRET_KEY

# 注册全局错误处理器
app.register_error_handler(APIError, handle_api_error)
app.register_error_handler(Exception, handle_generic_error)

# 注册所有路由
register_routes(app)

if __name__ == '__main__':
    import os
    # 生产环境不使用 debug 模式
    debug_mode = os.environ.get('FLASK_ENV', '').lower() != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=6008)

