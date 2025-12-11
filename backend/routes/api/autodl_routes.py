"""
AutoDL Flow - AutoDL API 路由
"""
from flask import request, jsonify, session
from backend.auth.decorators import login_required
from backend.config import AUTODL_AVAILABLE, DATACENTER_MAPPING, RUN_SCRIPT_TEMPLATES_FILE, TEMP_SCRIPTS_DIR, UPLOADED_FILES_DIR
from backend.utils.encryption import load_user_autodl_token
from backend.utils.storage import (
    get_user_deployment_config_dir,
    get_user_deployment_records_dir,
    save_deployment_config,
    save_deployment_record,
    cleanup_old_temp_scripts
)
from backend.utils.token import generate_download_token
from backend.utils.errors import APIError, ValidationError, NotFoundError, UnauthorizedError, log_error
from backend.auth.utils import is_admin
from datetime import datetime
from pathlib import Path
import json
import os
import time
import random
import re
from urllib.parse import unquote


def register_routes(bp):
    """注册 AutoDL 相关路由"""
    
    if not AUTODL_AVAILABLE:
        # 如果 autodl-api 未安装，返回占位响应
        @bp.route('/autodl/test', methods=['POST'])
        @login_required
        def test_autodl_connection():
            return jsonify({'error': 'autodl-api library not installed'}), 400
        
        @bp.route('/autodl/images', methods=['POST'])
        @login_required
        def get_autodl_images():
            return jsonify({'error': 'autodl-api library not installed'}), 500
        
        return
    
    from autodl import AutoDLElasticDeployment
    
    @bp.route('/autodl/test', methods=['POST'])
    @login_required
    def test_autodl_connection():
        """测试 AutoDL API 连接"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
            token = data.get('token', '').strip() if data else ''
            if not token:
                token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            # 创建客户端并测试连接
            client = AutoDLElasticDeployment(token)
            # 尝试获取部署列表来测试连接
            deployments = client.get_deployments()
            
            return jsonify({'success': True, 'message': '连接成功'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/images', methods=['POST'])
    @login_required
    def get_autodl_images():
        """获取 AutoDL 镜像列表"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
            token = data.get('token', '').strip() if data else ''
            if not token:
                token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            images = client.get_images()
            
            # 处理镜像列表，确保每个镜像都有清晰的名称和UUID
            processed_images = []
            for img in images:
                if isinstance(img, dict):
                    # 优先获取UUID（用于API调用）- 尝试多个可能的字段名
                    image_uuid = (img.get('uuid') or img.get('image_uuid') or 
                                 img.get('id') or img.get('image_id') or 
                                 img.get('uid') or img.get('image_uid'))
                    
                    # 尝试从不同字段获取名称（用于显示）
                    image_name = (img.get('name') or img.get('image_name') or 
                                 img.get('title') or img.get('repository') or 
                                 img.get('display_name') or img.get('image') or
                                 img.get('repo_name'))
                    
                    # 如果UUID不存在，使用名称作为UUID（向后兼容）
                    if not image_uuid:
                        image_uuid = image_name
                    
                    # 如果名称不存在，使用UUID作为名称
                    if not image_name:
                        image_name = image_uuid
                    
                    # 构建处理后的镜像对象
                    processed_img = {
                        'id': image_uuid,  # 使用UUID作为ID
                        'uuid': image_uuid,  # 明确标记UUID字段
                        'name': image_name,  # 显示名称
                        **img  # 保留原始数据
                    }
                    processed_images.append(processed_img)
                elif isinstance(img, str):
                    # 如果返回的是字符串列表（假设是UUID）
                    processed_images.append({
                        'id': img,
                        'uuid': img,
                        'name': img
                    })
                else:
                    # 其他格式，直接添加
                    processed_images.append(img)
            
            return jsonify({'images': processed_images})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployments', methods=['POST'])
    @login_required
    def get_autodl_deployments():
        """获取 AutoDL 部署列表"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
            token = data.get('token', '').strip() if data else ''
            if not token:
                token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            deployments = client.get_deployments()

            # 非 admin 仅显示自己提交的任务（如果返回包含用户名字段则尝试过滤）
            if not is_admin(username) and isinstance(deployments, list):
                filtered = []
                for item in deployments:
                    owner = (
                        item.get('username')
                        or item.get('user')
                        or item.get('user_name')
                        or item.get('owner')
                        or item.get('creator')
                    )
                    if owner:
                        if owner == username:
                            filtered.append(item)
                    else:
                        # 如果没有 owner 字段，则保留（避免误删）
                        filtered.append(item)
                deployments = filtered
            
            return jsonify({'deployments': deployments})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment/<deployment_uuid>/stop', methods=['POST'])
    @login_required
    def stop_autodl_deployment(deployment_uuid):
        """停止 AutoDL 部署"""
        try:
            username = session.get('username', 'admin')
            token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            
            # 调用 stop_deployment 方法
            success = client.stop_deployment(deployment_uuid)
            
            if success:
                return jsonify({'success': True, 'message': '部署已停止'})
            else:
                return jsonify({'error': '停止部署失败'}), 500
        except Exception as e:
            print(f"Error stopping deployment: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment/<deployment_uuid>/delete', methods=['DELETE'])
    @login_required
    def delete_autodl_deployment(deployment_uuid):
        """删除 AutoDL 部署"""
        try:
            username = session.get('username', 'admin')
            token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            
            # 调用 delete_deployment 方法
            success = client.delete_deployment(deployment_uuid)
            
            if success:
                return jsonify({'success': True, 'message': '部署已删除'})
            else:
                return jsonify({'error': '删除部署失败'}), 500
        except Exception as e:
            print(f"Error deleting deployment: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @bp.route('/autodl/deployments/batch-delete', methods=['POST'])
    @login_required
    def batch_delete_autodl_deployments():
        """批量删除 AutoDL 部署（用于已停止任务多选删除）"""
        try:
            username = session.get('username', 'admin')
            data = request.json or {}
            deployment_uuids = data.get('deployment_uuids', [])

            if not isinstance(deployment_uuids, list) or not deployment_uuids:
                return jsonify({'error': 'deployment_uuids 参数必须为非空列表'}), 400
            
            token = load_user_autodl_token(username)
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            results = []
            success_count = 0

            for uuid in deployment_uuids:
                try:
                    ok = client.delete_deployment(uuid)
                    results.append({'deployment_uuid': uuid, 'success': bool(ok)})
                    if ok:
                        success_count += 1
                except Exception as inner_e:
                    results.append({'deployment_uuid': uuid, 'success': False, 'error': str(inner_e)})
                    continue
            
            return jsonify({
                'success': success_count == len(deployment_uuids),
                'deleted': success_count,
                'total': len(deployment_uuids),
                'results': results
            })
        except Exception as e:
            print(f"Error batch deleting deployments: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment/<deployment_uuid>/ssh', methods=['GET'])
    @login_required
    def get_deployment_ssh(deployment_uuid):
        """获取部署的SSH连接信息"""
        try:
            username = session.get('username', 'admin')
            token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            
            try:
                # 使用 query_containers 方法查询容器信息
                containers_list = client.query_containers(deployment_uuid)['list']
                print(f"DEBUG: Containers info for deployment {deployment_uuid}: {containers_list}")
                
                if len(containers_list) == 0:
                    return jsonify({'info': '容器尚未分配，正在排队中'}), 202
                container_info = containers_list[0]['info']
                ssh_info = {
                    'ssh_command': container_info.get('ssh_command', ''),
                    'root_password': container_info.get('root_password', ''),
                    'service_6006_port_url': container_info.get('service_6006_port_url', ''),
                    'service_6008_port_url': container_info.get('service_6008_port_url', ''),
                    'command': container_info.get('ssh_command', '')  
                }
                            
                return jsonify({
                    'deployment_uuid': deployment_uuid,
                    'ssh_info': ssh_info,
                    'container_info': container_info  # 返回完整容器信息以便调试
                })
            except AttributeError as e:
                return jsonify({
                    'error': f'获取SSH信息失败。请检查 autodl-api 库的版本。错误：{str(e)}'
                }), 501
            except Exception as e:
                # 如果 query_containers 方法不存在或调用失败，尝试使用旧方法
                try:
                    deployments = client.get_deployments()
                    deployment = None
                    for dep in deployments:
                        if isinstance(dep, dict):
                            if dep.get('uuid') == deployment_uuid or dep.get('id') == deployment_uuid:
                                deployment = dep
                                break
                    
                    if not deployment:
                        return jsonify({'error': '部署不存在'}), 404
                    
                    ssh_info = {
                        'host': deployment.get('ssh_host') or deployment.get('host') or deployment.get('ip'),
                        'port': deployment.get('ssh_port') or deployment.get('port') or 22,
                        'user': deployment.get('ssh_user') or deployment.get('user') or 'root',
                        'password': deployment.get('ssh_password') or deployment.get('password'),
                        'command': None,
                        'ssh_command': None,
                        'root_password': None,
                        'service_6006_port_url': None,
                        'service_6008_port_url': None
                    }
                    
                    # 如果有密码，构建SSH命令
                    if ssh_info['host']:
                        if ssh_info['password']:
                            ssh_command = f"sshpass -p '{ssh_info['password']}' ssh -p {ssh_info['port']} {ssh_info['user']}@{ssh_info['host']}"
                        else:
                            ssh_command = f"ssh -p {ssh_info['port']} {ssh_info['user']}@{ssh_info['host']}"
                        ssh_info['command'] = ssh_command
                        ssh_info['ssh_command'] = ssh_command
                        ssh_info['root_password'] = ssh_info['password']
                    
                    return jsonify({
                        'deployment_uuid': deployment_uuid,
                        'ssh_info': ssh_info,
                        'deployment': deployment
                    })
                except Exception as fallback_error:
                    return jsonify({
                        'error': f'获取SSH信息失败: {str(e)}。回退方法也失败: {str(fallback_error)}'
                    }), 500
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/gpu-stock', methods=['GET'])
    @login_required
    def get_autodl_gpu_stock():
        """获取 AutoDL GPU 库存"""
        try:
            username = session.get('username', 'admin')
            token = load_user_autodl_token(username)
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            client = AutoDLElasticDeployment(token)
            
            # 获取所有分区的 GPU 库存
            # 根据 autodl-api 文档，get_gpu_stock 需要数据中心和 GPU ID
            gpu_stock = {}
            
            # 使用全局数据中心映射
            datacenter_mapping = DATACENTER_MAPPING
            
            # GPU名称映射：前端格式 -> API返回格式
            gpu_name_mapping = {
                'RTX-5090': 'RTX 5090',
                'RTX-4090': 'RTX 4090',
                'RTX-4090D': 'RTX 4090D',
                'RTX-4080': 'RTX 4080',
                'RTX-3090': 'RTX 3090',
                'RTX-3080': 'RTX 3080',
                'RTX-3070': 'RTX 3070',
                'V100': 'V100',
                'A100': 'A100',
                'H100': 'H100',
                'L20': 'L20',
                'L40': 'L40'
            }
            
            # 遍历所有数据中心
            for dc_name_cn, dc_code in datacenter_mapping.items():
                gpu_stock[dc_name_cn] = {
                    '_code': dc_code,  # 保存英文编号，用于API调用
                    '_name': dc_name_cn  # 保存中文名称，用于显示
                }
                
                # 初始化所有GPU类型为0
                for frontend_name in gpu_name_mapping.keys():
                    gpu_stock[dc_name_cn][frontend_name] = {
                        'available': 0,
                        'idle_gpu_num': 0,
                        'total_gpu_num': 0,
                        'count': 0
                    }
                
                # 尝试使用通用方法获取该数据中心的所有GPU库存
                # 使用一个通用的GPU ID（比如118，通常能返回所有GPU类型）
                common_gpu_ids = [118, 117, 119, 120, 121, 122, 123, 124, 125, 126, 127]
                
                for gpu_id in common_gpu_ids:
                    try:
                        stock = client.get_gpu_stock(dc_code, gpu_id)
                        
                        if isinstance(stock, list):
                            # 遍历返回的GPU列表，匹配所有我们需要的GPU类型
                            for gpu_item in stock:
                                if isinstance(gpu_item, dict):
                                    gpu_type = gpu_item.get('gpu_type', '').strip()
                                    
                                    # 尝试匹配每个我们需要的GPU类型
                                    for frontend_name, api_name in gpu_name_mapping.items():
                                        matched = False
                                        
                                        # 精确匹配（API返回的是"RTX 4090"格式）
                                        if gpu_type == api_name:
                                            matched = True
                                        else:
                                            # 模糊匹配：去除空格和连字符，统一比较
                                            gpu_type_normalized = gpu_type.replace(' ', '').replace('-', '').upper()
                                            api_name_normalized = api_name.replace(' ', '').replace('-', '').upper()
                                            
                                            # 特殊处理：RTX-4090D 需要精确匹配（不能匹配到 RTX 4090）
                                            if frontend_name == 'RTX-4090D':
                                                if '4090D' in gpu_type_normalized:
                                                    matched = True
                                            # RTX-4090 不能匹配到 RTX 4090D
                                            elif frontend_name == 'RTX-4090':
                                                if api_name_normalized in gpu_type_normalized and '4090D' not in gpu_type_normalized:
                                                    matched = True
                                            # 其他GPU类型：包含匹配
                                            else:
                                                if api_name_normalized in gpu_type_normalized or gpu_type_normalized in api_name_normalized:
                                                    matched = True
                                        
                                        if matched:
                                            # 累加空闲GPU数量
                                            idle_num = gpu_item.get('idle_gpu_num', 0)
                                            total_num = gpu_item.get('total_gpu_num', 0)
                                            
                                            # 累加到对应的GPU类型
                                            current_idle = gpu_stock[dc_name_cn][frontend_name].get('idle_gpu_num', 0)
                                            current_total = gpu_stock[dc_name_cn][frontend_name].get('total_gpu_num', 0)
                                            
                                            gpu_stock[dc_name_cn][frontend_name] = {
                                                'available': current_idle + idle_num,
                                                'idle_gpu_num': current_idle + idle_num,
                                                'total_gpu_num': current_total + total_num,
                                                'count': current_idle + idle_num
                                            }
                                            
                                            print(f"DEBUG: Matched {gpu_type} -> {frontend_name} in {dc_name_cn}: idle={idle_num}, total={total_num}")
                                            break  # 匹配成功后跳出内层循环
                        
                    except Exception as e:
                        # 某些GPU ID可能不存在，继续尝试下一个
                        continue
            
            # 打印汇总信息以便调试
            print(f"DEBUG: GPU Stock Summary - Total datacenters: {len(gpu_stock)}")
            for dc_name, dc_data in gpu_stock.items():
                print(f"DEBUG: {dc_name}: {len([k for k in dc_data.keys() if not k.startswith('_')])} GPU types")
            
            return jsonify({
                'gpu_stock': gpu_stock,
                'datacenter_mapping': datacenter_mapping,  # 同时返回映射关系，方便前端使用
                'debug_info': {
                    'total_datacenters': len(gpu_stock),
                    'gpu_types': list(gpu_name_mapping.keys())
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/run-script-templates', methods=['GET'])
    @login_required
    def get_run_script_templates():
        """获取运行脚本模板"""
        try:
            if RUN_SCRIPT_TEMPLATES_FILE.exists():
                with open(RUN_SCRIPT_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                    templates = json.load(f)
                return jsonify({
                    'success': True,
                    'templates': templates
                })
            else:
                # 如果文件不存在，返回默认模板
                default_templates = {
                    'run_sh_template': '#!/bin/bash\ncd /root\n\nnohup bash build.sh > $OUTPUT/build.log 2>&1',
                    'run_py_template': '#!/usr/bin/env python3\nimport subprocess\nimport os\nimport sys\nfrom pathlib import Path\n\n# 切换到 /root 目录\nos.chdir(\'/root\')\n\n# 获取 OUTPUT 环境变量\noutput_dir = os.environ.get(\'OUTPUT\', \'/root/output\')\nlog_file = os.path.join(output_dir, \'build.log\')\n\n# 确保日志目录存在\nPath(output_dir).mkdir(parents=True, exist_ok=True)\n\n# 执行 build.sh，将输出重定向到日志文件\nprint(f\'Starting build.sh, logs will be saved to {log_file}...\')\ntry:\n    with open(log_file, \'w\', encoding=\'utf-8\') as log:\n        log.write(f\'=== Starting build.sh ===\\n\')\n        log.flush()\n        \n        result = subprocess.run(\n            [\'bash\', \'build.sh\'],\n            cwd=\'/root\',\n            stdout=log,\n            stderr=subprocess.STDOUT,\n            check=True\n        )\n        \n        log.write(f\'\\n=== build.sh completed successfully ===\\n\')\n        log.flush()\n    \n    print(f\'build.sh completed successfully, logs saved to {log_file}\')\n    sys.exit(0)\nexcept subprocess.CalledProcessError as e:\n    error_msg = f\'build.sh failed with error code {e.returncode}\'\n    print(error_msg)\n    with open(log_file, \'a\', encoding=\'utf-8\') as log:\n        log.write(f\'\\n=== ERROR: {error_msg} ===\\n\')\n    sys.exit(1)\nexcept Exception as e:\n    error_msg = f\'Error running build.sh: {e}\'\n    print(error_msg)\n    with open(log_file, \'a\', encoding=\'utf-8\') as log:\n        log.write(f\'\\n=== ERROR: {error_msg} ===\\n\')\n    sys.exit(1)'
                }
                return jsonify({
                    'success': True,
                    'templates': default_templates
                })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/cleanup-temp-scripts', methods=['POST'])
    @login_required
    def cleanup_temp_scripts_api():
        """手动触发清理过期临时脚本"""
        try:
            cleanup_old_temp_scripts()
            return jsonify({'success': True, 'message': '清理完成'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/save-env-script', methods=['POST'])
    @login_required
    def save_env_script():
        """保存环境变量脚本文件（env.sh）并返回下载URL"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            env_vars = data.get('env_vars', {})  # 环境变量字典
            
            if not env_vars or not isinstance(env_vars, dict):
                return jsonify({'error': '环境变量不能为空'}), 400
            
            # 生成 env.sh 脚本内容
            script_lines = ['#!/bin/bash']
            script_lines.append('# 环境变量配置文件')
            script_lines.append('# 自动生成，请勿手动修改')
            script_lines.append('')
            
            for key, value in env_vars.items():
                # 转义特殊字符，确保值被正确引用
                escaped_value = str(value).replace("'", "'\\''")
                script_lines.append(f"export {key}='{escaped_value}'")
            
            script_content = '\n'.join(script_lines) + '\n'
            
            # 生成唯一的文件名（使用时间戳和随机数，避免冲突）
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
            random_id = random.randint(1000, 9999)
            filename = f'env_{timestamp}_{random_id}.sh'
            
            # 保存到临时目录（每个用户有自己的子目录，1小时后自动删除）
            user_temp_dir = TEMP_SCRIPTS_DIR / username
            user_temp_dir.mkdir(parents=True, exist_ok=True)
            script_file_path = user_temp_dir / filename
            
            try:
                # 确保目录存在
                script_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 保存脚本内容
                with open(script_file_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                print(f"✓ Env script saved to temp directory: {script_file_path} (will be deleted after 1 hour)")
                
                # 在保存时触发清理（异步清理旧文件）
                cleanup_old_temp_scripts()
            except Exception as e:
                print(f"Error saving env script: {e}")
                return jsonify({'error': f'保存环境变量脚本失败: {str(e)}'}), 500
            
            # 生成下载URL（保存临时文件路径到token中，用于后续下载）
            relative_path = str(script_file_path.relative_to(TEMP_SCRIPTS_DIR))
            token = generate_download_token(relative_path)
            
            # 从请求中获取正确的 host 和 scheme
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            download_url = f"{scheme}://{host}/api/download/{token}"
            
            return jsonify({
                'success': True,
                'filename': 'env.sh',
                'temp_filename': filename,
                'download_url': download_url
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/save-run-script', methods=['POST'])
    @login_required
    def save_run_script():
        """保存run脚本文件并返回下载URL"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            script_content = data.get('script_content', '').strip()
            script_type = data.get('script_type', 'shell')  # 'shell' or 'python'
            
            if not script_content:
                return jsonify({'error': '脚本内容不能为空'}), 400
            
            # 确定文件扩展名
            extension = '.py' if script_type == 'python' else '.sh'
            
            # 生成唯一的文件名（使用时间戳和随机数，避免冲突）
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
            random_id = random.randint(1000, 9999)
            filename = f'run_{timestamp}_{random_id}{extension}'
            
            # 保存到临时目录（每个用户有自己的子目录，1小时后自动删除）
            user_temp_dir = TEMP_SCRIPTS_DIR / username
            user_temp_dir.mkdir(parents=True, exist_ok=True)
            script_file_path = user_temp_dir / filename
            
            try:
                # 确保目录存在
                script_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 保存脚本内容
                with open(script_file_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                print(f"✓ Run script saved to temp directory: {script_file_path} (will be deleted after 1 hour)")
                
                # 在保存时触发清理（异步清理旧文件）
                cleanup_old_temp_scripts()
            except Exception as e:
                print(f"Error saving run script: {e}")
                return jsonify({'error': f'保存脚本失败: {str(e)}'}), 500
            
            # 生成下载URL（保存临时文件路径到token中，用于后续下载）
            relative_path = str(script_file_path.relative_to(TEMP_SCRIPTS_DIR))
            token = generate_download_token(relative_path)
            
            # 从请求中获取正确的 host 和 scheme
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            download_url = f"{scheme}://{host}/api/download/{token}"
            
            # 返回文件名，用于命令行下载（run.sh 或 run.py）
            display_filename = 'run.py' if script_type == 'python' else 'run.sh'
            
            return jsonify({
                'success': True,
                'filename': display_filename,  # 返回显示用的文件名（run.sh 或 run.py）
                'temp_filename': filename,  # 临时文件名
                'download_url': download_url
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/create-deployment', methods=['POST'])
    @login_required
    def create_autodl_deployment():
        """创建 AutoDL 部署"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            # 优先使用请求中的 token（用于测试），如果没有则使用存储的 token
            token = data.get('token', '').strip() if data else ''
            if not token:
                token = load_user_autodl_token(username)
            
            # 获取参数
            name = data.get('name', '').strip()
            image_uuid = data.get('image_uuid', '').strip()  # 镜像UUID
            deployment_type = data.get('deployment_type', 'Job')  # 默认Job，首字母大写
            dc_list = data.get('dc_list', [])  # 数据中心列表（中文名称）
            gpu_num = data.get('gpu_num', 1)
            gpu_name_set = data.get('gpu_name_set', [])  # GPU类型列表
            env_vars_for_config = data.get('env_vars', {})  # 仅用于保存配置，不传递给 API
            
            # 可选参数
            replica_num = data.get('replica_num', 1)
            parallelism_num = data.get('parallelism_num', None)
            cmd = data.get('cmd', 'sleep 100')
            
            if not token:
                return jsonify({'error': 'API Token 未设置，请先配置 Token'}), 400
            
            if not name:
                return jsonify({'error': '部署名称不能为空'}), 400
            
            if not image_uuid:
                return jsonify({'error': '请选择镜像'}), 400
            
            client = AutoDLElasticDeployment(token)
            
            # 将中文数据中心名称转换为英文编号
            dc_codes = []
            for dc_name_cn in dc_list:
                if dc_name_cn in DATACENTER_MAPPING:
                    dc_codes.append(DATACENTER_MAPPING[dc_name_cn])
            
            # 如果没有指定数据中心，使用空列表（让API自动选择）
            if not dc_codes:
                dc_codes = None
            
            # 转换GPU名称格式（从"RTX-4090"转换为"RTX 4090"）
            gpu_names = [gpu.replace('-', ' ') for gpu in gpu_name_set] if gpu_name_set else None
            
            try:
                # 清理命令：移除多余的空白字符，确保命令正确
                if cmd:
                    # 移除命令开头和结尾的空白
                    cmd = cmd.strip()
                    # 移除多余的 && 连接符（如 " && && "）
                    cmd = re.sub(r'\s*&&\s*&&\s*', ' && ', cmd)
                    # 移除命令开头的 && 
                    cmd = re.sub(r'^\s*&&\s*', '', cmd)
                    # 移除命令结尾的 &&
                    cmd = re.sub(r'\s*&&\s*$', '', cmd)
                
                # 记录命令（用于调试，使用 info 级别）
                log_error(f"创建部署命令: {cmd[:200]}..." if len(cmd) > 200 else f"创建部署命令: {cmd}", 
                         level='info', username=username, deployment_name=name)
                
                # 调用 create_deployment 方法
                deployment_uuid = client.create_deployment(
                    name=name,
                    image_uuid=image_uuid,
                    deployment_type=deployment_type,
                    replica_num=replica_num,
                    parallelism_num=parallelism_num,
                    gpu_name_set=gpu_names,
                    gpu_num=gpu_num,
                    dc_list=dc_codes,
                    cmd=cmd
                )
                
                print(f"\n✓✓✓ 部署创建成功！部署UUID: {deployment_uuid}\n")
                
                # 保存任务提交配置（自动保存当前界面所有设置）
                try:
                    # 获取前端传递的完整配置信息（包括运行脚本内容等）
                    run_script_type = data.get('run_script_type', 'shell')
                    run_script_content = data.get('run_script_content', '')
                    history_script = data.get('history_script', '')
                    
                    config_data = {
                        'name': name,
                        'deployment_type': deployment_type,
                        'image_uuid': image_uuid,
                        'dc_list': dc_list,  # 中文名称列表
                        'gpu_num': gpu_num,
                        'gpu_name_set': gpu_name_set,  # GPU类型列表
                        'env_vars': env_vars_for_config,  # 从请求数据获取，用于保存配置
                        'replica_num': replica_num,
                        'parallelism_num': parallelism_num,
                        'cmd': cmd,
                        'run_script_type': run_script_type,
                        'run_script_content': run_script_content,
                        'history_script': history_script if history_script else None,
                        'deployment_uuid': deployment_uuid,
                        'created_at': datetime.now().isoformat()
                    }
                    # 保存到提交记录，不保存到历史配置
                    save_deployment_record(username, config_data)
                except Exception as e:
                    print(f"Warning: Failed to save deployment record: {e}")
                    import traceback
                    traceback.print_exc()
                    # 不影响部署创建，只记录警告
                
                return jsonify({
                    'success': True,
                    'deployment_uuid': deployment_uuid,
                    'message': f'部署创建成功！部署UUID: {deployment_uuid}'
                })
            except AttributeError as e:
                return jsonify({
                    'error': f'create_deployment 方法不存在。请检查 autodl-api 库的版本。错误：{str(e)}'
                }), 501
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs', methods=['GET'])
    @login_required
    def list_deployment_configs():
        """列出所有任务提交配置（支持分组过滤和分页）"""
        try:
            username = session.get('username', 'admin')
            config_dir = get_user_deployment_config_dir(username)
            configs = []
            
            # 获取查询参数
            group = request.args.get('group', '').strip()  # 分组过滤
            page = int(request.args.get('page', 1))  # 页码，从1开始
            per_page = int(request.args.get('per_page', 10))  # 每页数量
            
            # 确定搜索目录
            if group:
                search_dir = config_dir / group
            else:
                search_dir = config_dir
            
            if search_dir.exists():
                # 搜索所有配置文件（包括子目录）
                for file_path in search_dir.rglob('deployment_config_*.json'):
                    try:
                        stat = file_path.stat()
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        
                        # 获取相对路径，用于确定分组
                        relative_path = file_path.relative_to(config_dir)
                        file_group = None
                        if len(relative_path.parts) > 1:
                            file_group = relative_path.parts[0]  # 第一级目录名作为分组
                        
                        configs.append({
                            'filename': file_path.stem,  # 不含扩展名
                            'full_filename': file_path.name,  # 完整文件名
                            'relative_path': str(relative_path),  # 相对路径，用于删除
                            'config': config_data,
                            'group': file_group or config_data.get('group', ''),
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                    except Exception as e:
                        print(f"Error reading config {file_path}: {e}")
                        continue
            
            # 按修改时间倒序排列（最新的在前）
            configs = sorted(configs, key=lambda x: x['modified'], reverse=True)
            
            # 分页处理
            total = len(configs)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_configs = configs[start:end]
            
            return jsonify({
                'configs': paginated_configs,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page  # 总页数
                }
            })
        except Exception as e:
            print(f"Error listing deployment configs: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs/<path:relative_path>', methods=['GET'])
    @login_required
    def get_deployment_config(relative_path):
        """获取特定的任务提交配置（支持分组路径）"""
        try:
            username = session.get('username', 'admin')
            config_dir = get_user_deployment_config_dir(username)
            
            # 确保是JSON文件
            if not relative_path.endswith('.json'):
                relative_path += '.json'
            
            config_file = config_dir / relative_path
            
            if not config_file.exists():
                return jsonify({'error': '配置不存在'}), 404
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return jsonify({
                'success': True,
                'config': config_data,
                'filename': config_file.stem,
                'relative_path': relative_path
            })
        except Exception as e:
            print(f"Error getting deployment config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs/<path:relative_path>', methods=['DELETE'])
    @login_required
    def delete_deployment_config(relative_path):
        """删除任务提交配置（支持分组路径）"""
        try:
            username = session.get('username', 'admin')
            config_dir = get_user_deployment_config_dir(username)
            
            # 确保是JSON文件
            if not relative_path.endswith('.json'):
                relative_path += '.json'
            
            config_file = config_dir / relative_path
            
            if not config_file.exists():
                return jsonify({'error': '配置不存在'}), 404
            
            # 删除配置文件
            config_file.unlink()
            
            print(f"✓ Deployment config deleted: {config_file}")
            return jsonify({'success': True, 'message': '配置删除成功'})
        except Exception as e:
            print(f"Error deleting deployment config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs', methods=['POST'])
    @login_required
    def save_deployment_config_api():
        """手动保存任务提交配置（不创建部署）"""
        try:
            username = session.get('username', 'admin')
            data = request.json
            
            # 获取分组信息
            group = data.get('group', '').strip() or None
            
            # 收集所有配置信息
            config_data = {
                'name': data.get('name', '').strip() or '未命名配置',
                'deployment_type': data.get('deployment_type', 'Job'),
                'image_uuid': data.get('image_uuid', ''),
                'dc_list': data.get('dc_list', []),
                'gpu_num': data.get('gpu_num', 1),
                'gpu_name_set': data.get('gpu_name_set', []),
                'env_vars': data.get('env_vars', {}),
                'replica_num': data.get('replica_num', 1),
                'parallelism_num': data.get('parallelism_num', None),
                'cmd': data.get('cmd', ''),
                'run_script_type': data.get('run_script_type', 'shell'),
                'run_script_content': data.get('run_script_content', ''),
                'history_script': data.get('history_script', None),
                'created_at': datetime.now().isoformat()
            }
            
            save_deployment_config(username, config_data, group=group)
            
            return jsonify({
                'success': True,
                'message': '配置保存成功'
            })
        except Exception as e:
            print(f"Error saving deployment config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs/groups', methods=['GET'])
    @login_required
    def list_deployment_config_groups():
        """获取所有配置分组列表"""
        try:
            username = session.get('username', 'admin')
            config_dir = get_user_deployment_config_dir(username)
            groups = set()
            
            if config_dir.exists():
                # 遍历所有子目录作为分组
                for item in config_dir.iterdir():
                    if item.is_dir():
                        groups.add(item.name)
            
            return jsonify({
                'groups': sorted(list(groups))
            })
        except Exception as e:
            print(f"Error listing deployment config groups: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-configs/move', methods=['POST'])
    @login_required
    def move_deployment_config():
        """移动配置到指定分组"""
        try:
            username = session.get('username', 'admin')
            config_dir = get_user_deployment_config_dir(username)
            data = request.json
            
            relative_path = data.get('relative_path', '')
            target_group = data.get('group', '').strip() or None
            
            if not relative_path:
                return jsonify({'error': '缺少配置路径'}), 400
            
            # 确保是JSON文件
            if not relative_path.endswith('.json'):
                relative_path += '.json'
            
            source_file = config_dir / relative_path
            
            if not source_file.exists():
                return jsonify({'error': '配置不存在'}), 404
            
            # 读取配置数据
            with open(source_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新分组信息
            if target_group:
                config_data['group'] = target_group
            
            # 确定目标目录和文件
            if target_group:
                target_dir = config_dir / target_group
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / source_file.name
            else:
                target_file = config_dir / source_file.name
            
            # 如果目标文件与源文件不同，移动文件
            if target_file != source_file:
                # 保存到新位置
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                # 删除原文件
                source_file.unlink()
            
            print(f"✓ Deployment config moved: {source_file} -> {target_file}")
            return jsonify({
                'success': True,
                'message': '配置移动成功',
                'relative_path': str(target_file.relative_to(config_dir))
            })
        except Exception as e:
            print(f"Error moving deployment config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-records', methods=['GET'])
    @login_required
    def list_deployment_records():
        """列出所有提交记录（支持分页）"""
        try:
            username = session.get('username', 'admin')
            records_dir = get_user_deployment_records_dir(username)
            records = []
            
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))
            
            if records_dir.exists():
                for file_path in records_dir.glob('deployment_record_*.json'):
                    try:
                        stat = file_path.stat()
                        with open(file_path, 'r', encoding='utf-8') as f:
                            record_data = json.load(f)
                        
                        records.append({
                            'filename': file_path.stem,
                            'full_filename': file_path.name,
                            'relative_path': file_path.name,
                            'record': record_data,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                    except Exception as e:
                        print(f"Error reading record {file_path}: {e}")
                        continue
            
            # 按修改时间倒序排列
            records = sorted(records, key=lambda x: x['modified'], reverse=True)
            
            # 分页处理
            total = len(records)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_records = records[start:end]
            
            return jsonify({
                'records': paginated_records,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as e:
            print(f"Error listing deployment records: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-records/<record_filename>', methods=['GET'])
    @login_required
    def get_deployment_record(record_filename):
        """获取特定的提交记录"""
        try:
            username = session.get('username', 'admin')
            records_dir = get_user_deployment_records_dir(username)
            
            record_filename = unquote(record_filename)
            if not record_filename.endswith('.json'):
                record_filename += '.json'
            
            record_file = records_dir / record_filename
            
            if not record_file.exists():
                return jsonify({'error': '记录不存在'}), 404
            
            with open(record_file, 'r', encoding='utf-8') as f:
                record_data = json.load(f)
            
            return jsonify({
                'success': True,
                'record': record_data,
                'filename': record_file.stem
            })
        except Exception as e:
            print(f"Error getting deployment record: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-records/<record_filename>', methods=['DELETE'])
    @login_required
    def delete_deployment_record(record_filename):
        """删除提交记录"""
        try:
            username = session.get('username', 'admin')
            records_dir = get_user_deployment_records_dir(username)
            
            record_filename = unquote(record_filename)
            if not record_filename.endswith('.json'):
                record_filename += '.json'
            
            record_file = records_dir / record_filename
            
            if not record_file.exists():
                return jsonify({'error': '记录不存在'}), 404
            
            record_file.unlink()
            
            print(f"✓ Deployment record deleted: {record_file}")
            return jsonify({'success': True, 'message': '记录删除成功'})
        except Exception as e:
            print(f"Error deleting deployment record: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/deployment-records/<record_filename>/save-to-config', methods=['POST'])
    @login_required
    def save_record_to_config(record_filename):
        """将提交记录保存到历史配置"""
        try:
            username = session.get('username', 'admin')
            records_dir = get_user_deployment_records_dir(username)
            data = request.json or {}
            
            record_filename = unquote(record_filename)
            if not record_filename.endswith('.json'):
                record_filename += '.json'
            
            record_file = records_dir / record_filename
            
            if not record_file.exists():
                return jsonify({'error': '记录不存在'}), 404
            
            with open(record_file, 'r', encoding='utf-8') as f:
                record_data = json.load(f)
            
            group = data.get('group', '').strip() or None
            
            # 移除记录标记
            if 'is_record' in record_data:
                del record_data['is_record']
            
            # 保存到历史配置
            save_deployment_config(username, record_data, group=group)
            
            return jsonify({
                'success': True,
                'message': '记录已保存到历史配置' + (f'（分组: {group}）' if group else '')
            })
        except Exception as e:
            print(f"Error saving record to config: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/autodl/upload-file', methods=['POST'])
    @login_required
    def upload_file():
        """上传文件到服务器"""
        try:
            username = session.get('username', 'admin')
            
            if 'file' not in request.files:
                raise ValidationError('没有文件被上传')
            
            file = request.files['file']
            if file.filename == '':
                raise ValidationError('文件名为空')
            
            # 获取目标路径（可选）
            target_path = request.form.get('target_path', '').strip()
            
            # 创建用户目录
            user_upload_dir = UPLOADED_FILES_DIR / username
            try:
                user_upload_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log_error(f"创建用户上传目录失败: {user_upload_dir}", exception=e, username=username)
                raise APIError('创建上传目录失败', status_code=500, error_code='DIR_CREATE_FAILED')
            
            # 保存文件
            filename = file.filename
            # 处理文件名冲突
            file_path = user_upload_dir / filename
            counter = 1
            while file_path.exists():
                name_part = file_path.stem
                ext_part = file_path.suffix
                file_path = user_upload_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            
            try:
                file.save(str(file_path))
            except Exception as e:
                log_error(f"保存文件失败: {file_path}", exception=e, username=username, filename=filename)
                raise APIError('保存文件失败', status_code=500, error_code='FILE_SAVE_FAILED')
            
            # 生成下载 token
            try:
                relative_path = file_path.relative_to(UPLOADED_FILES_DIR)
                token = generate_download_token(str(relative_path))
            except Exception as e:
                log_error(f"生成下载token失败", exception=e, username=username, filename=filename)
                raise APIError('生成下载链接失败', status_code=500, error_code='TOKEN_GENERATE_FAILED')
            
            # 从请求中获取正确的 host 和 scheme（用于生成完整URL）
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            download_url = f"{scheme}://{host}/api/download/{token}"
            
            try:
                file_size = file_path.stat().st_size
            except Exception as e:
                log_error(f"获取文件大小失败", exception=e, username=username, filename=filename)
                file_size = 0
            
            return jsonify({
                'success': True,
                'filename': file_path.name,
                'original_filename': filename,
                'target_path': target_path,
                'size': file_size,
                'upload_time': datetime.now().isoformat(),
                'download_token': token,
                'download_url': download_url
            })
        except (APIError, ValidationError, NotFoundError):
            raise
        except Exception as e:
            log_error(f"上传文件时发生未预期的错误", exception=e, username=session.get('username', 'admin'))
            raise APIError('上传文件失败', status_code=500, error_code='UPLOAD_FAILED')
    
    @bp.route('/autodl/uploaded-files', methods=['GET'])
    @login_required
    def list_uploaded_files():
        """列出用户上传的文件"""
        try:
            username = session.get('username', 'admin')
            user_upload_dir = UPLOADED_FILES_DIR / username
            
            # 从请求中获取正确的 host 和 scheme（用于生成完整URL）
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            files = []
            if user_upload_dir.exists():
                try:
                    for file_path in user_upload_dir.iterdir():
                        if file_path.is_file():
                            try:
                                stat = file_path.stat()
                                relative_path = file_path.relative_to(UPLOADED_FILES_DIR)
                                token = generate_download_token(str(relative_path))
                                download_url = f"{scheme}://{host}/api/download/{token}"
                                files.append({
                                    'filename': file_path.name,
                                    'size': stat.st_size,
                                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    'download_token': token,
                                    'download_url': download_url
                                })
                            except Exception as e:
                                log_error(f"处理文件信息失败: {file_path}", exception=e, username=username)
                                continue
                except Exception as e:
                    log_error(f"读取用户上传目录失败: {user_upload_dir}", exception=e, username=username)
                    raise APIError('读取文件列表失败', status_code=500, error_code='LIST_FILES_FAILED')
            
            # 按修改时间倒序排列
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return jsonify({'files': files})
        except (APIError, ValidationError, NotFoundError):
            raise
        except Exception as e:
            log_error(f"列出上传文件时发生未预期的错误", exception=e, username=session.get('username', 'admin'))
            raise APIError('获取文件列表失败', status_code=500, error_code='LIST_FAILED')
    
    @bp.route('/autodl/uploaded-files/<filename>/download-url', methods=['GET'])
    @login_required
    def get_file_download_url(filename):
        """获取文件的新下载URL（重新生成token）"""
        try:
            from urllib.parse import unquote
            from backend.utils.file_finder import find_file_in_user_dirs, get_username
            
            username = get_username()
            filename = unquote(filename)
            
            # 安全检查：防止路径遍历攻击
            filename = os.path.basename(filename)
            
            # 查找文件
            file_path = find_file_in_user_dirs(
                filename=filename,
                file_type='upload',
                username=username,
                search_all_users=False  # 只查找当前用户的文件
            )
            
            if not file_path or not file_path.exists():
                raise NotFoundError('文件不存在')
            
            # 生成新的下载 token
            try:
                relative_path = file_path.relative_to(UPLOADED_FILES_DIR)
                token = generate_download_token(str(relative_path))
            except Exception as e:
                log_error(f"生成下载token失败", exception=e, username=username, filename=filename)
                raise APIError('生成下载链接失败', status_code=500, error_code='TOKEN_GENERATE_FAILED')
            
            # 从请求中获取正确的 host 和 scheme（用于生成完整URL）
            scheme = request.headers.get('X-Forwarded-Proto', 'http')
            if scheme == 'http' and request.is_secure:
                scheme = 'https'
            
            host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', request.host))
            if not host:
                host = request.host or 'localhost:6008'
            
            download_url = f"{scheme}://{host}/api/download/{token}"
            
            return jsonify({
                'success': True,
                'filename': file_path.name,
                'download_url': download_url
            })
        except (APIError, ValidationError, NotFoundError, UnauthorizedError):
            raise
        except Exception as e:
            log_error(f"获取文件下载URL时发生未预期的错误", exception=e, username=session.get('username', 'admin'), filename=filename)
            raise APIError('获取下载链接失败', status_code=500, error_code='GET_DOWNLOAD_URL_FAILED')
    
    @bp.route('/autodl/uploaded-files/<filename>', methods=['DELETE'])
    @login_required
    def delete_uploaded_file(filename):
        """删除上传的文件"""
        try:
            username = session.get('username', 'admin')
            user_upload_dir = UPLOADED_FILES_DIR / username
            file_path = user_upload_dir / filename
            
            # 安全检查：确保文件在用户目录内
            try:
                file_path.resolve().relative_to(user_upload_dir.resolve())
            except ValueError:
                raise UnauthorizedError('无权访问该文件')
            
            if not file_path.exists():
                raise NotFoundError('文件不存在')
            
            try:
                file_path.unlink()
            except Exception as e:
                log_error(f"删除文件失败: {file_path}", exception=e, username=username, filename=filename)
                raise APIError('删除文件失败', status_code=500, error_code='DELETE_FAILED')
            
            return jsonify({'success': True, 'message': '文件已删除'})
        except (APIError, ValidationError, NotFoundError, UnauthorizedError):
            raise
        except Exception as e:
            log_error(f"删除上传文件时发生未预期的错误", exception=e, username=session.get('username', 'admin'), filename=filename)
            raise APIError('删除文件失败', status_code=500, error_code='DELETE_FAILED')
