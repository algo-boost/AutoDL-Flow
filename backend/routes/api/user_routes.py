"""
AutoDL Flow - 用户相关 API 路由
"""
import logging
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.auth.utils import verify_password, hash_password, get_all_accounts, save_accounts
from backend.services.config_service import ConfigService
from backend.services.category_service import CategoryService
from backend.utils.storage import get_user_env_config_file
from backend.utils.errors import ValidationError, NotFoundError, APIError, log_error
import json
from urllib.parse import unquote

logger = logging.getLogger(__name__)


def register_routes(bp):
    """注册用户相关路由"""
    config_service = ConfigService()
    category_service = CategoryService()
    
    @bp.route('/user/change-password', methods=['POST'])
    @login_required
    def change_password():
        """修改密码"""
        try:
            data = request.json
            old_password = data.get('old_password', '')
            new_password = data.get('new_password', '')
            username = session.get('username', 'admin')
            
            accounts = get_all_accounts()
            if username not in accounts:
                return jsonify({'error': '用户不存在'}), 400
            
            # 验证旧密码
            if not verify_password(old_password, accounts[username]):
                return jsonify({'error': '旧密码错误'}), 400
            
            # 更新密码
            accounts[username] = hash_password(new_password)
            if save_accounts(accounts):
                return jsonify({'success': True, 'message': '密码修改成功'})
            else:
                return jsonify({'error': '保存失败'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/models', methods=['GET'])
    @login_required
    def get_user_models():
        """获取当前用户的模型配置"""
        try:
            username = session.get('username', 'admin')
            _, _, _, models, _ = config_service.load_user_config(username)
            return jsonify({'models': models})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/models', methods=['POST'])
    @login_required
    def add_user_model():
        """添加或更新模型配置"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            model_name = data.get('name', '')
            model_config = data.get('config', {})
            
            if not model_name:
                raise ValidationError('模型名称不能为空')
            
            # 加载当前配置
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            # 更新模型配置
            models[model_name] = model_config
            
            # 保存配置
            if not config_service.save_user_config(username, models=models):
                raise APIError('保存配置失败', status_code=500, error_code='SAVE_FAILED')
            
            logger.info(f"User {username} added/updated model: {model_name}")
            return jsonify({'success': True, 'message': f'模型 {model_name} 配置已保存'})
        except (ValidationError, APIError):
            raise
        except Exception as e:
            log_error(f"Error adding model: {e}", exception=e, username=username)
            raise APIError('添加模型配置时发生错误', status_code=500, error_code='INTERNAL_ERROR')
    
    @bp.route('/user/models/<model_name>', methods=['DELETE'])
    @login_required
    def delete_user_model(model_name):
        """删除模型配置"""
        try:
            username = session.get('username', 'admin')
            model_name = unquote(model_name)
            
            # 加载当前配置
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            if model_name not in models:
                raise NotFoundError(f'模型 {model_name} 不存在')
            
            # 删除模型
            del models[model_name]
            
            # 保存配置
            if not config_service.save_user_config(username, models=models):
                raise APIError('保存配置失败', status_code=500, error_code='SAVE_FAILED')
            
            logger.info(f"User {username} deleted model: {model_name}")
            return jsonify({'success': True, 'message': f'模型 {model_name} 已删除'})
        except (NotFoundError, APIError):
            raise
        except Exception as e:
            log_error(f"Error deleting model: {e}", exception=e, username=username, model_name=model_name)
            raise APIError('删除模型配置时发生错误', status_code=500, error_code='INTERNAL_ERROR')
    
    @bp.route('/user/repos', methods=['GET'])
    @login_required
    def get_user_repos():
        """获取当前用户的代码仓库配置"""
        try:
            username = session.get('username', 'admin')
            repos, _, _, _, _ = config_service.load_user_config(username)
            return jsonify({'repos': repos})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/repos', methods=['POST'])
    @login_required
    def add_user_repo():
        """添加或更新代码仓库配置"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            repo_name = data.get('name', '')
            repo_config = data.get('config', {})
            
            if not repo_name:
                return jsonify({'error': '仓库名称不能为空'}), 400
            
            if 'url' not in repo_config:
                return jsonify({'error': '仓库 URL 不能为空'}), 400
            
            # 加载当前配置
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            # 确保 install_cmds 存在
            if 'install_cmds' not in repo_config:
                repo_config['install_cmds'] = []
            
            # 更新仓库配置
            repos[repo_name] = repo_config
            
            # 保存配置
            if config_service.save_user_config(username, repos=repos):
                return jsonify({'success': True, 'message': f'仓库 {repo_name} 配置已保存'})
            else:
                return jsonify({'error': '保存配置失败'}), 500
        except Exception as e:
            print(f"Error adding repo: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/repos/<repo_name>', methods=['DELETE'])
    @login_required
    def delete_user_repo(repo_name):
        """删除代码仓库配置"""
        try:
            username = session.get('username', 'admin')
            repo_name = unquote(repo_name)
            
            # 加载当前配置
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            if repo_name not in repos:
                return jsonify({'error': '仓库不存在'}), 404
            
            # 删除仓库
            del repos[repo_name]
            
            # 保存配置
            if config_service.save_user_config(username, repos=repos):
                return jsonify({'success': True, 'message': f'仓库 {repo_name} 已删除'})
            else:
                return jsonify({'error': '保存配置失败'}), 500
        except Exception as e:
            print(f"Error deleting repo: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/system-config', methods=['GET'])
    @login_required
    def get_system_config():
        """获取当前用户的系统配置（百度网盘、Git SSH等）"""
        try:
            username = session.get('username', 'admin')
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            # 读取用户自己的 .env_config.json 文件内容
            env_config_content = ''
            env_config_file = get_user_env_config_file(username)
            if env_config_file.exists():
                try:
                    with open(env_config_file, 'r', encoding='utf-8') as f:
                        env_config_content = f.read()
                except Exception as e:
                    print(f"Warning: Failed to read .env_config.json: {e}")
            
            return jsonify({
                'env_config_content': env_config_content,
                'git_ssh_path': data_download.get('git_ssh_path', ''),
                'dataset_cache_path': data_download.get('dataset_cache_path', 'cache/datasets')
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/system-config', methods=['POST'])
    @login_required
    def save_system_config():
        """保存当前用户的系统配置"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            env_config_content = data.get('env_config_content', '').strip()
            git_ssh_path = data.get('git_ssh_path', '').strip()
            dataset_cache_path = data.get('dataset_cache_path', 'cache/datasets').strip()
            
            # 保存用户自己的 .env_config.json 文件
            if env_config_content:
                try:
                    # 验证JSON格式
                    json.loads(env_config_content)
                    # 保存到用户特定的文件
                    env_config_file = get_user_env_config_file(username)
                    env_config_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(env_config_file, 'w', encoding='utf-8') as f:
                        f.write(env_config_content)
                except json.JSONDecodeError as e:
                    return jsonify({'error': f'JSON格式错误: {str(e)}'}), 400
                except Exception as e:
                    return jsonify({'error': f'保存文件失败: {str(e)}'}), 500
            
            # 加载现有配置
            repos, data_download, category_groups, models, bdnd_config = config_service.load_user_config(username)
            
            updated_data_download = data_download.copy()
            if git_ssh_path:
                updated_data_download['git_ssh_path'] = git_ssh_path
            if dataset_cache_path:
                updated_data_download['dataset_cache_path'] = dataset_cache_path
            
            # 保存配置
            if config_service.save_user_config(username, data_download=updated_data_download):
                return jsonify({'success': True, 'message': '系统配置已保存'})
            else:
                return jsonify({'error': '保存配置失败'}), 500
        except Exception as e:
            print(f"Error saving system config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/autodl-token', methods=['GET'])
    @login_required
    def get_user_autodl_token_status():
        """获取当前用户的 AutoDL Token 状态（不返回实际值）"""
        try:
            from backend.utils.encryption import load_user_autodl_token
            username = session.get('username', 'admin')
            token = load_user_autodl_token(username)
            return jsonify({
                'has_token': token is not None,
                'token_set': bool(token)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/autodl-token', methods=['POST'])
    @login_required
    def save_user_autodl_token_api():
        """保存当前用户的 AutoDL Token"""
        try:
            from backend.utils.encryption import save_user_autodl_token
            username = session.get('username', 'admin')
            data = request.json
            token = data.get('token', '').strip()
            
            if not token:
                return jsonify({'error': 'Token 不能为空'}), 400
            
            if save_user_autodl_token(username, token):
                return jsonify({'success': True, 'message': 'Token 保存成功'})
            else:
                return jsonify({'error': '保存失败'}), 500
        except Exception as e:
            print(f"Error saving autodl token: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/autodl-token', methods=['DELETE'])
    @login_required
    def delete_user_autodl_token_api():
        """删除当前用户的 AutoDL Token"""
        try:
            from backend.utils.encryption import delete_user_autodl_token
            username = session.get('username', 'admin')
            if delete_user_autodl_token(username):
                return jsonify({'success': True, 'message': 'Token 已删除'})
            else:
                return jsonify({'error': '删除失败'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/category-groups', methods=['GET'])
    @login_required
    def get_user_category_groups():
        """获取当前用户的类别映射组"""
        try:
            username = session.get('username', 'admin')
            category_groups = category_service.load_user_category_groups(username)
            return jsonify({'category_groups': category_groups})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/user/category-groups', methods=['POST'])
    @login_required
    def save_user_category_groups():
        """保存当前用户的类别映射组"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            category_groups = data.get('category_groups', [])
            
            if category_service.save_user_category_groups(username, category_groups):
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Failed to save user category groups'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

