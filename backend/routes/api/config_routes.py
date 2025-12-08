"""
AutoDL Flow - 配置相关 API 路由
"""
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.services.config_service import ConfigService
from backend.utils.storage import get_accessible_dirs, get_user_storage_dir
from backend.config import CONFIGS_STORAGE_DIR
from pathlib import Path
from datetime import datetime
import json
import os


def register_routes(bp):
    """注册配置相关路由"""
    config_service = ConfigService()
    
    @bp.route('/configs', methods=['GET'])
    @login_required
    def list_configs():
        """列出保存的配置"""
        try:
            username = session.get('username', 'admin')
            configs = []
            
            # 获取用户可访问的目录列表
            accessible_dirs = get_accessible_dirs(CONFIGS_STORAGE_DIR, username)
            
            # 从所有可访问的目录获取配置列表
            for configs_dir in accessible_dirs:
                if configs_dir.exists():
                    for file_path in configs_dir.glob('*.json'):
                        # 跳过用户配置文件
                        if file_path.name == 'user_config.json' or file_path.name.startswith('.'):
                            continue
                        try:
                            stat = file_path.stat()
                            with open(file_path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                            
                            # 获取配置所属用户（从路径判断）
                            if configs_dir == CONFIGS_STORAGE_DIR:
                                owner = 'admin'  # 根目录的配置属于 admin
                            else:
                                owner = configs_dir.name
                            
                            configs.append({
                                'filename': file_path.stem,
                                'config': config_data,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'owner': owner  # 添加所有者信息
                            })
                        except Exception as e:
                            print(f"Error reading config {file_path}: {e}")
                            continue
            
            configs = sorted(configs, key=lambda x: x['modified'], reverse=True)
            return jsonify({'configs': configs})
        except Exception as e:
            print(f"Error listing configs: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/configs', methods=['POST'])
    @login_required
    def save_config():
        """保存配置"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            config_name = data.get('name', '')
            config_data = data.get('config', {})
            
            if not config_name:
                # 生成默认名称
                now = datetime.now()
                config_name = f"config_{now.strftime('%Y%m%d_%H%M%S')}"
            
            # 保存到用户目录
            user_configs_dir = get_user_storage_dir(CONFIGS_STORAGE_DIR, username)
            config_file = user_configs_dir / f"{config_name}.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True, 'name': config_name})
        except Exception as e:
            print(f"Error saving config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/configs/<config_name>', methods=['DELETE'])
    @login_required
    def delete_config(config_name):
        """删除配置"""
        try:
            username = session.get('username', 'admin')
            from urllib.parse import unquote
            config_name = unquote(config_name)
            config_name = os.path.basename(config_name)
            
            # 查找配置文件（检查用户可访问的目录）
            config_file = None
            accessible_dirs = get_accessible_dirs(CONFIGS_STORAGE_DIR, username)
            
            for configs_dir in accessible_dirs:
                potential_path = configs_dir / f"{config_name}.json"
                if potential_path.exists() and potential_path.is_file():
                    config_file = potential_path
                    break
            
            if not config_file or not config_file.exists():
                return jsonify({'error': 'Config not found'}), 404
            
            config_file.unlink()
            return jsonify({'success': True})
        except Exception as e:
            print(f"Error deleting config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

