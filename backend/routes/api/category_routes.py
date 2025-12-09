"""
AutoDL Flow - 类别映射组 API 路由
"""
import logging
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.services.category_service import CategoryService
from backend.utils.errors import APIError, log_error

logger = logging.getLogger(__name__)


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
            log_error("Error loading category groups", exception=e)
            raise APIError('加载类别映射组失败', status_code=500, error_code='LOAD_FAILED')
    
    @bp.route('/category-groups', methods=['POST'])
    @login_required
    def save_category_groups():
        """保存类别映射组"""
        try:
            data = request.json
            category_groups = data.get('category_groups', [])
            
            if not isinstance(category_groups, list):
                raise APIError('category_groups 必须是列表', status_code=400, error_code='INVALID_DATA')
            
            if not category_service.save_category_groups(category_groups):
                raise APIError('保存类别映射组失败', status_code=500, error_code='SAVE_FAILED')
            
            logger.info(f"Category groups saved successfully, count: {len(category_groups)}")
            return jsonify({'success': True})
        except APIError:
            raise
        except Exception as e:
            log_error("Error saving category groups", exception=e)
            raise APIError('保存类别映射组时发生错误', status_code=500, error_code='INTERNAL_ERROR')

