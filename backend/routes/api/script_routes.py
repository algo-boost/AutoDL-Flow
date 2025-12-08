"""
AutoDL Flow - 脚本相关 API 路由
"""
from flask import request, jsonify, session, send_file
from backend.auth.decorators import login_required
from backend.utils.storage import get_user_storage_dir, get_accessible_dirs
from backend.config import SCRIPTS_STORAGE_DIR, TEMP_SCRIPTS_DIR
from backend.services.script_generator import ScriptGenerator
from backend.services.config_service import ConfigService
from backend.utils.token import generate_download_token, verify_download_token
from pathlib import Path
from urllib.parse import unquote
import json
import os


def register_routes(bp):
    """注册脚本相关路由"""
    config_service = ConfigService()
    
    @bp.route('/generate', methods=['POST'])
    @login_required
    def generate():
        """生成脚本 API"""
        try:
            data = request.json
            if not data:
                return jsonify({'error': '请求数据为空'}), 400
            
            username = session.get('username', 'admin')
            
            # 加载用户配置
            repos, data_download_config, _, models, _ = config_service.load_user_config(username)
            
            # 创建脚本生成器
            script_generator = ScriptGenerator(repos, data_download_config, models)
            
            selected_repos = data.get('repos', [])
            snapshots = [s for s in data.get('snapshots', []) if s.get('id') or s.get('url') or s.get('bdnd_path')]
            output_dir = data.get('output_dir', '/root/autodl-tmp')
            dataset_name = data.get('dataset_name', 'merged_dataset')
            split_ratio = data.get('split_ratio')
            split_seed = data.get('split_seed', 42) if split_ratio else 42
            data_only = data.get('data_only', False)
            enable_repos = data.get('enable_repos', True)
            enable_snapshots = data.get('enable_snapshots', True)
            enable_merge = data.get('enable_merge', True)
            category_group = data.get('category_group', '')
            selected_models = data.get('models', [])
            
            if enable_merge and not enable_snapshots:
                return jsonify({'error': '数据集生成需要先启用数据快照下载'}), 400
            
            if enable_snapshots and not snapshots:
                return jsonify({'error': '请至少添加一个数据快照'}), 400
            
            script = script_generator.generate_script(
                selected_repos, snapshots, output_dir, dataset_name, 
                split_ratio, split_seed, data_only,
                enable_repos, enable_snapshots, enable_merge, 
                category_group, selected_models, username
            )
            
            return jsonify({'script': script})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/scripts', methods=['GET'])
    @login_required
    def list_scripts():
        """获取脚本列表"""
        try:
            from datetime import datetime
            username = session.get('username', 'admin')
            accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
            
            files = []
            for dir_path in accessible_dirs:
                if dir_path.exists():
                    # 只显示历史脚本，排除运行脚本（run.sh, run.py）
                    for script_file in dir_path.glob('*.sh'):
                        # 排除运行脚本
                        if script_file.name in ['run.sh', 'run.py']:
                            continue
                        try:
                            stat = script_file.stat()
                            # 获取文件所属用户（从路径判断）
                            if dir_path == SCRIPTS_STORAGE_DIR:
                                owner = 'admin'  # 根目录的文件属于 admin
                            else:
                                owner = dir_path.name
                            
                            files.append({
                                'filename': script_file.name,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'local': True,
                                'owner': owner  # 添加所有者信息
                            })
                        except Exception as e:
                            print(f"Error reading file {script_file}: {e}")
                            continue
            
            # 按修改时间倒序排列（最新的在前）
            files = sorted(files, key=lambda x: x['modified'], reverse=True)
            
            return jsonify({'files': files})
        except Exception as e:
            print(f"Error listing scripts: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/save', methods=['POST'])
    @login_required
    def save():
        """保存脚本到服务器（可选备份到百度网盘）"""
        try:
            data = request.json
            selected_repos = data.get('repos', [])
            snapshots = [s for s in data.get('snapshots', []) if s.get('id') or s.get('url') or s.get('bdnd_path')]
            output_dir = data.get('output_dir', '/root/autodl-tmp')
            dataset_name = data.get('dataset_name', 'merged_dataset')
            split_ratio = data.get('split_ratio')
            split_seed = data.get('split_seed', 42) if split_ratio else 42
            data_only = data.get('data_only', False)
            enable_repos = data.get('enable_repos', True)
            enable_snapshots = data.get('enable_snapshots', True)
            enable_merge = data.get('enable_merge', True)
            category_group = data.get('category_group', '')
            selected_models = data.get('models', [])
            filename = data.get('filename', 'auto_job.sh')
            backup_to_netdisk = data.get('backup_to_netdisk', False)
            script_content = data.get('script_content')  # 如果用户编辑了脚本，直接使用编辑后的内容
            
            username = session.get('username', 'admin')
            
            # 如果传入了编辑后的脚本内容，直接使用；否则重新生成
            if script_content:
                script = script_content
            else:
                # 加载用户配置
                repos, data_download_config, _, models, _ = config_service.load_user_config(username)
                
                # 创建脚本生成器
                script_generator = ScriptGenerator(repos, data_download_config, models)
                
                script = script_generator.generate_script(
                    selected_repos, snapshots, output_dir, dataset_name, 
                    split_ratio, split_seed, data_only,
                    enable_repos, enable_snapshots, enable_merge, 
                    category_group, selected_models, username
                )
            
            # 保存到服务器本地（无论是否备份到网盘都保存）
            user_scripts_dir = get_user_storage_dir(SCRIPTS_STORAGE_DIR, username)
            local_file_path = user_scripts_dir / filename
            try:
                with open(local_file_path, 'w', encoding='utf-8') as f:
                    f.write(script)
                print(f"✓ Script saved to server: {local_file_path}")
            except Exception as e:
                print(f"Warning: Failed to save script to server: {e}")
                return jsonify({'error': f'保存脚本失败: {str(e)}'}), 500
            
            # 如果选择备份到网盘，立即在服务器端执行备份
            backup_success = False
            backup_error = None
            if backup_to_netdisk:
                try:
                    from backend.config import BAIDU_NETDISK_SCRIPTS_DIR
                    from bdnd import BaiduNetdiskClient
                    import tempfile
                    import os
                    
                    # 获取访问令牌（从环境变量、env_key_manager 或用户配置中获取）
                    from backend.utils.bdnd import get_baidu_netdisk_access_token
                    access_token = get_baidu_netdisk_access_token(username)
                    
                    if not access_token:
                        backup_error = "Access token not available"
                        print(f"Warning: {backup_error}, skipping backup")
                    else:
                        try:
                            # 上传到百度网盘
                            client = BaiduNetdiskClient(access_token)
                            
                            # 确保目标目录存在
                            remote_dir = BAIDU_NETDISK_SCRIPTS_DIR
                            if not client.create_directory(remote_dir):
                                print(f"Warning: Failed to create directory {remote_dir}, continuing...")
                            
                            # 上传文件
                            remote_path = f"{remote_dir}/{filename}"
                            print(f"Uploading script to Baidu Netdisk: {remote_path}")
                            result = client.upload_file_auto(str(local_file_path), remote_path, show_progress=False)
                            
                            if result and isinstance(result, dict) and result.get("errno") == 0:
                                backup_success = True
                                print(f"✓ Script successfully backed up to Baidu Netdisk: {remote_path}")
                            else:
                                errno = result.get("errno", "unknown") if result else "unknown"
                                errmsg = result.get("errmsg", "Unknown error") if result else "Upload returned None"
                                backup_error = f"Upload failed (errno={errno}): {errmsg}"
                                print(f"✗ Failed to backup script: {backup_error}")
                        except Exception as e:
                            backup_error = str(e)
                            print(f"✗ Exception during backup: {backup_error}")
                            import traceback
                            traceback.print_exc()
                except Exception as e:
                    backup_error = str(e)
                    print(f"✗ Backup to Baidu Netdisk failed: {backup_error}")
                    import traceback
                    traceback.print_exc()
            
            # 只备份到网盘，不下载文件
            if backup_to_netdisk:
                if backup_success:
                    return jsonify({
                        'success': True,
                        'message': f'Script backed up to /apps/autodl/scripts/{filename}',
                        'filename': filename
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': backup_error or 'Unknown error'
                    }), 500
            else:
                return jsonify({
                    'success': True,
                    'message': 'Script saved to server',
                    'filename': filename
                })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/scripts/<filename>/download', methods=['GET'])
    @login_required
    def download_script(filename):
        """提供脚本文件的下载链接（使用临时token，生成完整URL）"""
        try:
            username = session.get('username', 'admin')
            
            # URL 解码文件名
            filename = unquote(filename)
            
            # 安全检查：防止路径遍历攻击
            filename = os.path.basename(filename)
            if not filename.endswith('.sh'):
                return jsonify({'error': 'Invalid file type'}), 400
            
            # 查找文件（先检查用户目录，admin 可以检查所有目录）
            file_path = None
            accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
            
            for scripts_dir in accessible_dirs:
                potential_path = scripts_dir / filename
                if potential_path.exists() and potential_path.is_file():
                    file_path = potential_path
                    break
            
            if not file_path or not file_path.exists():
                print(f"File not found: {filename}")
                return jsonify({'error': f'File not found: {filename}'}), 404
            
            if not file_path.is_file():
                return jsonify({'error': 'Not a file'}), 400
            
            # 生成临时下载token
            token = generate_download_token(filename)
            
            # 从请求中获取正确的 host 和 scheme，生成完整URL
            # 支持通过 Nginx 反向代理的情况
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            # 生成完整的下载URL（使用token，不暴露文件名和服务器路径）
            download_url = f"{scheme}://{host}/api/download/{token}"
            
            print(f"Generated download URL with token for {filename}: {download_url}")
            
            return jsonify({
                'filename': filename,
                'download_url': download_url,
                'size': file_path.stat().st_size
            })
        except Exception as e:
            print(f"Error generating download URL: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/download/<token>', methods=['GET'])
    def serve_script(token):
        """通过token提供脚本文件下载服务（不暴露服务器信息）"""
        try:
            # 验证token
            filename = verify_download_token(token)
            if not filename:
                return jsonify({'error': 'Invalid or expired token'}), 403
            
            file_path = None
            
            # 先检查临时脚本目录（运行脚本）
            if '/' in filename or '\\' in filename:  # 如果包含路径分隔符，说明是临时文件
                potential_path = TEMP_SCRIPTS_DIR / filename
                if potential_path.exists() and potential_path.is_file():
                    file_path = potential_path
            else:
                # 查找文件（在所有用户目录中查找）
                # 先检查根目录（admin 的旧文件）
                potential_path = SCRIPTS_STORAGE_DIR / filename
                if potential_path.exists() and potential_path.is_file():
                    file_path = potential_path
                else:
                    # 检查所有用户目录
                    if SCRIPTS_STORAGE_DIR.exists():
                        for item in SCRIPTS_STORAGE_DIR.iterdir():
                            if item.is_dir():
                                potential_path = item / filename
                                if potential_path.exists() and potential_path.is_file():
                                    file_path = potential_path
                                    break
                    # 如果还没找到，检查临时目录
                    if not file_path:
                        if TEMP_SCRIPTS_DIR.exists():
                            for item in TEMP_SCRIPTS_DIR.iterdir():
                                if item.is_dir():
                                    potential_path = item / filename
                                    if potential_path.exists() and potential_path.is_file():
                                        file_path = potential_path
                                        break
            
            if not file_path or not file_path.exists():
                print(f"File not found when serving: {filename}")
                return jsonify({'error': f'File not found: {filename}'}), 404
            
            if not file_path.is_file():
                return jsonify({'error': 'Not a file'}), 400
            
            print(f"Serving file via token: {file_path}")
            
            # 提取原始文件名（如果是临时文件，可能需要提取）
            download_name = filename
            if file_path.parent.parent == TEMP_SCRIPTS_DIR:
                # 临时文件，提取原始文件名（run.sh 或 run.py）
                if filename.endswith('.py'):
                    download_name = 'run.py'
                elif filename.endswith('.sh'):
                    download_name = 'run.sh'
            
            return send_file(
                str(file_path),
                mimetype='text/plain',
                as_attachment=True,
                download_name=download_name
            )
        except Exception as e:
            print(f"Error serving file: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/scripts/<filename>', methods=['DELETE'])
    @login_required
    def delete_script(filename):
        """删除脚本文件"""
        try:
            username = session.get('username', 'admin')
            filename = unquote(filename)
            filename = os.path.basename(filename)
            
            if not filename.endswith('.sh'):
                return jsonify({'error': 'Invalid file type'}), 400
            
            # 查找文件
            file_path = None
            accessible_dirs = get_accessible_dirs(SCRIPTS_STORAGE_DIR, username)
            
            for scripts_dir in accessible_dirs:
                potential_path = scripts_dir / filename
                if potential_path.exists() and potential_path.is_file():
                    file_path = potential_path
                    break
            
            if not file_path or not file_path.exists():
                return jsonify({'error': 'File not found'}), 404
            
            # 删除文件
            file_path.unlink()
            
            return jsonify({'success': True, 'message': f'Script {filename} deleted'})
        except Exception as e:
            print(f"Error deleting script: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

