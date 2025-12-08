"""
AutoDL Flow - 实验管理 API 路由
"""
from flask import request, jsonify, session
from backend.auth.decorators import login_required


def register_routes(bp):
    """注册实验管理路由"""
    
    @bp.route('/experiments/list', methods=['GET'])
    @login_required
    def list_experiments():
        """获取实验列表（占位功能）"""
        try:
            # 这里是占位实现，后续可以根据实际需求完善
            experiments = []
            return jsonify({'experiments': experiments})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

