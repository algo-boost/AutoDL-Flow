"""
AutoDL Flow - 类别映射组 API 路由
"""
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.services.category_service import CategoryService


def register_routes(bp):
    """注册类别映射组路由"""
    category_service = CategoryService()
    
    @bp.route('/category-groups', methods=['GET'])
    @login_required
    def get_category_groups():
        """获取类别映射组列表"""
        try:
            category_groups = category_service.load_category_groups()
            return jsonify({'category_groups': category_groups})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/category-groups', methods=['POST'])
    @login_required
    def save_category_groups():
        """保存类别映射组"""
        try:
            data = request.json
            category_groups = data.get('category_groups', [])
            
            if category_service.save_category_groups(category_groups):
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Failed to save category groups'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

