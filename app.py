#!/usr/bin/env python3
"""
AutoDL Flow - Flask Web工具：自动生成作业执行脚本
重构后的主应用文件
"""
from flask import Flask
from backend.config import SECRET_KEY, AUTODL_AVAILABLE
from backend.routes import register_routes

# 创建 Flask 应用
app = Flask(__name__, 
            template_folder='frontend/templates',
            static_folder='frontend/static')
app.secret_key = SECRET_KEY

# 注册所有路由
register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6008)

