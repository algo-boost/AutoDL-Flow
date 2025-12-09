"""
AutoDL Flow - 脚本生成服务
"""
import json
import os
from urllib.parse import urlparse
from backend.utils.storage import get_user_env_config_file


class ScriptGenerator:
    """脚本生成服务"""
    
    def __init__(self, repos, data_download_config, models):
        self.repos = repos
        self.data_download_config = data_download_config
        self.models = models
    
    def generate_script(self, selected_repos, snapshots, output_dir, dataset_name, 
                       split_ratio=None, split_seed=42, data_only=False, 
                       enable_repos=True, enable_snapshots=True, enable_merge=True, 
                       category_group=None, selected_models=None, username='admin'):
        """生成执行脚本"""
        script = """#!/usr/bin/env bash

set -e         
set -u         
set -o pipefail 

# 颜色输出
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
RED='\\033[0;31m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# 输出函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\\n${YELLOW}==>${NC} $1"
}

error_exit() {
    log_error "脚本执行失败于第 $1 行"
    exit 1
}

pip install --upgrade pip
pip install bdnd -i https://pypi.org/simple

trap 'error_exit $LINENO' ERR

# 配置 bdnd
log_info "配置 bdnd..."
OUTFILE="$HOME/.env_config.json"
mkdir -p "$(dirname "$OUTFILE")"
rm -f "$OUTFILE"

cat > "$OUTFILE" << 'EOF'
{env_config_json}
EOF

log_success "bdnd 配置完成"

"""
        
        # 如果选择了仓库，需要配置 git
        if enable_repos and not data_only and selected_repos:
            # 获取Git SSH路径配置
            git_ssh_path = self.data_download_config.get('git_ssh_path', '')
            script += f"""
# 配置 Git SSH
log_info "配置 Git SSH..."
cd $HOME
rm -rf .ssh .gitconfig
# 优先从 autodl-fs 读取 Git SSH 配置
GIT_SSH_PATH="{git_ssh_path}"
if [ -n "$GIT_SSH_PATH" ] && [ -d "/root/autodl-fs/$GIT_SSH_PATH" ]; then
    log_info "从 autodl-fs 复制 Git SSH 配置: $GIT_SSH_PATH"
    cp -r "/root/autodl-fs/$GIT_SSH_PATH/.ssh" "$HOME/" 2>/dev/null || true
    cp "/root/autodl-fs/$GIT_SSH_PATH/.gitconfig" "$HOME/" 2>/dev/null || true
    if [ -d "$HOME/.ssh" ] && [ -f "$HOME/.ssh/id_rsa" ]; then
        log_success "从 autodl-fs 复制 Git SSH 配置完成"
    else
        log_info "autodl-fs 中未找到完整的 Git SSH 配置，从百度网盘下载..."
        bdnd /apps/autodl/git_ssh_backup .
    fi
else
    log_info "从百度网盘下载 Git SSH 配置..."
    bdnd /apps/autodl/git_ssh_backup .
fi
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/id_rsa
chmod 600 $HOME/.ssh/id_*
log_success "Git SSH 配置完成"

log_info "开始安装包..."
echo "========================================"

cd /root
log_success "当前目录: $(pwd)"

"""
            
            # 克隆和安装代码仓库
            for repo_data in selected_repos:
                repo_name = repo_data['name']
                should_install = repo_data.get('install', False)
                repo = self.repos.get(repo_name, {})
                
                if not repo:
                    continue
                
                repo_url = repo.get('url', '')
                repo_branch = repo.get('branch', '')
                
                # 构建 git clone 命令
                if repo_branch:
                    clone_cmd = f'git clone -b {repo_branch} {repo_url}'
                else:
                    clone_cmd = f'git clone {repo_url}'
                
                script += f"""
# 克隆 {repo_name}
log_step "克隆 {repo_name} 仓库"
if [ -d "{repo_name}" ]; then
    log_info "{repo_name} 目录已存在，删除旧目录"
    rm -rf {repo_name}
fi
{clone_cmd}
log_success "{repo_name} 克隆完成"
"""
                if should_install and repo.get('install_cmds'):
                    script += f"""
# 安装 {repo_name}
log_step "安装 {repo_name}"
cd /root/{repo_name}
log_info "当前目录: $(pwd)"
"""
                    for cmd in repo['install_cmds']:
                        script += f"{cmd}\n"
                    script += f"""
log_success "{repo_name} 安装完成"
cd /root
"""
            
            script += """
echo "========================================"
log_success "所有包安装完成！"
"""
        
        # 如果启用了快照下载，需要先下载数据下载脚本
        if enable_snapshots:
            script += """
# 下载数据下载脚本
log_step "下载数据下载脚本..."
"""
            script += f"bdnd --mode download {self.data_download_config.get('script_remote_path', '/apps/autodl/dataset_down/')} {self.data_download_config.get('script_local_path', '/root/dataset_down/')}\n"
            script += f"cd {self.data_download_config.get('script_local_path', '/root/dataset_down/').rstrip('/')}\n"
        
        if enable_snapshots:
            script += """
# 下载数据集快照
log_step "下载数据集快照..."
"""
            
            # 下载数据快照
            for snapshot_data in snapshots:
                snapshot_id, snapshot_url, snapshot_bdnd_path, snapshot_name, enable_cache = self._parse_snapshot_data(snapshot_data)
                
                # 确定下载方式：优先级：快照ID > 百度网盘 > URL
                use_id = bool(snapshot_id and snapshot_id.strip())
                use_bdnd = bool(snapshot_bdnd_path and snapshot_bdnd_path.strip()) and not use_id
                use_url = bool(snapshot_url and snapshot_url.strip()) and not use_id and not use_bdnd
                
                # 确定快照名称
                name = self._determine_snapshot_name(snapshot_name, use_id, snapshot_id, 
                                                     use_bdnd, snapshot_bdnd_path, 
                                                     use_url, snapshot_url)
                
                # 使用配置的缓存路径，默认为 cache/datasets
                cache_path = self.data_download_config.get('dataset_cache_path', 'cache/datasets')
                fs_snapshot_path = f"/root/autodl-fs/{cache_path}/{name}"
                tmp_snapshot_path = f"/root/autodl-tmp/{name}"
                
                script += self._generate_snapshot_download_script(
                    name, fs_snapshot_path, tmp_snapshot_path,
                    use_id, snapshot_id, use_bdnd, snapshot_bdnd_path,
                    use_url, snapshot_url, category_group, enable_cache
                )
        
        # 如果选择了模型，下载模型文件
        if selected_models:
            script += """
# 下载模型
log_step "下载模型..."
mkdir -p /root/autodl-tmp/model
"""
            for model_item in selected_models:
                model_name, enable_cache = self._parse_model_item(model_item)
                model_config = self.models.get(model_name, {})
                if model_config:
                    script += self._generate_model_download_script(model_name, model_config, enable_cache)
            script += """
log_success "所有模型下载完成！"
"""
        
        if enable_merge:
            script += self._generate_dataset_merge_script(
                selected_repos, enable_repos, data_only,
                snapshots, output_dir, dataset_name, split_ratio, split_seed
            )
        
        script += '\nlog_success "END"\n'
        
        # 读取用户自己的 .env_config.json 文件内容并嵌入到脚本中
        env_config_json = self._get_env_config_content(username)
        
        # 替换占位符
        script = script.replace('{env_config_json}', env_config_json)
        
        return script
    
    def _parse_snapshot_data(self, snapshot_data):
        """解析快照数据"""
        if isinstance(snapshot_data, tuple):
            snapshot_id, snapshot_name = snapshot_data
            snapshot_url = ''
            snapshot_bdnd_path = ''
            enable_cache = True
        else:
            snapshot_id = snapshot_data.get('id', '')
            snapshot_url = snapshot_data.get('url', '')
            snapshot_bdnd_path = snapshot_data.get('bdnd_path', '')
            snapshot_name = snapshot_data.get('name', '')
            enable_cache = snapshot_data.get('cache', True)
        return snapshot_id, snapshot_url, snapshot_bdnd_path, snapshot_name, enable_cache
    
    def _determine_snapshot_name(self, snapshot_name, use_id, snapshot_id,
                                 use_bdnd, snapshot_bdnd_path, use_url, snapshot_url):
        """确定快照名称"""
        if snapshot_name:
            return snapshot_name
        elif use_id:
            return f"snapshot_{snapshot_id}"
        elif use_bdnd:
            bdnd_path = snapshot_bdnd_path.rstrip('/')
            bdnd_filename = os.path.basename(bdnd_path)
            if bdnd_filename:
                if bdnd_filename.endswith('.zip'):
                    return os.path.splitext(bdnd_filename)[0]
                else:
                    return bdnd_filename
            else:
                return f"snapshot_bdnd_{hash(snapshot_bdnd_path) % 10000}"
        elif use_url:
            parsed_url = urlparse(snapshot_url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename and '.' in url_filename:
                return os.path.splitext(url_filename)[0]
            else:
                return f"snapshot_url_{hash(snapshot_url) % 10000}"
        else:
            return "snapshot_unknown"
    
    def _generate_snapshot_download_script(self, name, fs_snapshot_path, tmp_snapshot_path,
                                          use_id, snapshot_id, use_bdnd, snapshot_bdnd_path,
                                          use_url, snapshot_url, category_group, enable_cache):
        """生成快照下载脚本"""
        script = f"""
log_info "处理快照 {name}"
# 先检查 autodl-fs 缓存目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -d "{fs_snapshot_path}" ]; then
    log_info "在 autodl-fs 缓存中找到快照 {name}，直接复制..."
    mkdir -p "$(dirname "{tmp_snapshot_path}")"
    # 如果目标目录已存在，先删除
    if [ -d "{tmp_snapshot_path}" ]; then
        log_info "目标目录已存在，删除旧目录"
        rm -rf "{tmp_snapshot_path}"
    fi
    cp -r "{fs_snapshot_path}" "{tmp_snapshot_path}"
    log_success "快照 {name} 复制完成"
else
    log_info "autodl-fs 缓存中未找到快照 {name}，开始下载..."
"""
        
        if use_id:
            cmd = f"python moli_dataset_export.py {snapshot_id} --output-dir /root/autodl-tmp/ --dir-name {name}"
            if category_group:
                cmd += f' --category-group "{category_group}"'
            script += f"""    {cmd}
    log_success "快照 {name} 下载完成"
"""
        elif use_bdnd:
            bdnd_path = snapshot_bdnd_path.rstrip('/')
            is_zip = bdnd_path.endswith('.zip')
            script += f"""    mkdir -p "{tmp_snapshot_path}"
    cd "{tmp_snapshot_path}"
    
    log_info "从百度网盘下载: {bdnd_path}"
    bdnd --mode download {bdnd_path} .
    
    if [ $? -ne 0 ]; then
        log_error "从百度网盘下载失败"
        exit 1
    fi
    
"""
            if is_zip:
                zip_filename = os.path.basename(bdnd_path)
                script += f"""    log_info "下载完成，开始解压: {zip_filename}"
    # 查找下载的zip文件（可能文件名不完全匹配）
    ZIP_FILE=$(find . -name "*.zip" -type f | head -n 1)
    if [ -z "$ZIP_FILE" ]; then
        # 如果没找到zip文件，尝试使用原始文件名
        if [ -f "{zip_filename}" ]; then
            ZIP_FILE="{zip_filename}"
        else
            log_error "未找到zip文件"
            exit 1
        fi
    fi
    
    log_info "解压文件: $ZIP_FILE"
    unzip -q "$ZIP_FILE" || {{
        log_error "解压 zip 文件失败"
        exit 1
    }}
    
    # 删除下载的压缩文件
    rm -f "$ZIP_FILE"
    log_success "快照 {name} 下载并解压完成"
"""
            else:
                script += f"""    log_success "快照 {name} 下载完成"
"""
        elif use_url:
            script += f"""    mkdir -p "{tmp_snapshot_path}"
    cd "{tmp_snapshot_path}"
    # 从URL中提取文件名
    DOWNLOAD_URL="{snapshot_url}"
    FILENAME=$(basename "$DOWNLOAD_URL" | cut -d'?' -f1)
    if [ -z "$FILENAME" ] || [ "$FILENAME" = "/" ]; then
        FILENAME="dataset.zip"
    fi
    
    log_info "从URL下载: $DOWNLOAD_URL"
    # 使用 wget 下载
    wget -q --show-progress -O "$FILENAME" "$DOWNLOAD_URL" || {{
        log_error "wget 下载失败，尝试使用 curl..."
        curl -L -o "$FILENAME" "$DOWNLOAD_URL" || {{
            log_error "快照 {name} 下载失败"
            exit 1
        }}
    }}
    
    log_info "下载完成，开始解压: $FILENAME"
    # 根据文件扩展名选择解压方式
    if [[ "$FILENAME" == *.zip ]]; then
        unzip -q "$FILENAME" || {{
            log_error "解压 zip 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar.gz ]] || [[ "$FILENAME" == *.tgz ]]; then
        tar -xzf "$FILENAME" || {{
            log_error "解压 tar.gz 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar ]]; then
        tar -xf "$FILENAME" || {{
            log_error "解压 tar 文件失败"
            exit 1
        }}
    elif [[ "$FILENAME" == *.tar.bz2 ]]; then
        tar -xjf "$FILENAME" || {{
            log_error "解压 tar.bz2 文件失败"
            exit 1
        }}
    else
        log_info "文件不是压缩格式，保持原样"
    fi
    
    # 删除下载的压缩文件
    rm -f "$FILENAME"
    log_success "快照 {name} 下载并解压完成"
"""
        else:
            script += f"""    log_error "未指定有效的下载方式（ID、百度网盘路径或URL）"
    exit 1
"""
        
        if enable_cache:
            script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs 缓存目录
    if [ ! -d "{fs_snapshot_path}" ] && [ -d "{tmp_snapshot_path}" ]; then
        log_info "缓存快照 {name} 到 autodl-fs 缓存目录..."
        mkdir -p "$(dirname "{fs_snapshot_path}")"
        cp -r "{tmp_snapshot_path}" "{fs_snapshot_path}"
        log_success "快照 {name} 已缓存到 autodl-fs 缓存目录"
    fi
"""
        else:
            script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
        script += "fi\n"
        return script
    
    def _parse_model_item(self, model_item):
        """解析模型项"""
        if isinstance(model_item, dict):
            model_name = model_item.get('name', '')
            enable_cache = model_item.get('cache', True)
        else:
            model_name = model_item
            enable_cache = True
        return model_name, enable_cache
    
    def _generate_model_download_script(self, model_name, model_config, enable_cache):
        """生成模型下载脚本"""
        download_url = model_config.get('url', '')
        local_path = model_config.get('local_path', '')
        fs_model_path = f"/root/autodl-fs/cache/models/{model_name}"
        
        if download_url and local_path:
            # 使用 URL 下载
            filename = model_config.get('filename', '')
            if not filename:
                parsed_url = urlparse(download_url)
                filename = os.path.basename(parsed_url.path)
                if not filename or '.' not in filename:
                    filename = f"{model_name}.pth"
            
            fs_model_file = f"{fs_model_path}/{filename}"
            
            script = f"""
log_info "处理模型 {model_name}..."
mkdir -p {local_path}
# 先检查 autodl-fs 目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -f "{fs_model_file}" ]; then
    log_info "在 autodl-fs 中找到模型文件，直接复制..."
    cp "{fs_model_file}" "{local_path}/{filename}"
    log_success "{model_name} 模型复制完成: {filename}"
elif [ -d "{fs_model_path}" ] && [ "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
    log_info "在 autodl-fs 中找到模型目录，复制所有文件..."
    cp -r {fs_model_path}/* {local_path}/
    log_success "{model_name} 模型复制完成"
else
    log_info "autodl-fs 中未找到模型 {model_name}，从 URL 下载..."
    cd {local_path}
    # 如果文件已存在，先删除
    if [ -f "{filename}" ]; then
        log_info "文件 {filename} 已存在，删除旧文件"
        rm -f "{filename}"
    fi
    # 使用 wget 下载
    wget -q --show-progress -O "{filename}" "{download_url}" || {{
        log_error "下载失败，尝试使用 curl..."
        curl -L -o "{filename}" "{download_url}" || {{
            log_error "模型 {model_name} 下载失败"
            exit 1
        }}
    }}
    log_success "{model_name} 模型下载完成: {filename}"
"""
            if enable_cache:
                script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs
    if [ ! -f "{fs_model_file}" ] && [ -f "{local_path}/{filename}" ]; then
        log_info "缓存模型 {model_name} 到 autodl-fs..."
        mkdir -p "{fs_model_path}"
        cp "{local_path}/{filename}" "{fs_model_file}"
        log_success "模型 {model_name} 已缓存到 autodl-fs"
    fi
"""
            else:
                script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
            script += "fi\n"
            return script
        else:
            # 使用百度网盘下载（原有方式）
            remote_path = model_config.get('remote_path', '')
            if remote_path and local_path:
                script = f"""
log_info "处理模型 {model_name}..."
mkdir -p {local_path}
# 先检查 autodl-fs 目录是否存在（无论是否启用缓存，都会检查并使用已有缓存）
if [ -d "{fs_model_path}" ] && [ "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
    log_info "在 autodl-fs 中找到模型目录，直接复制..."
    # 如果目标目录已存在，先删除
    if [ -d "{local_path}" ] && [ "$(ls -A {local_path} 2>/dev/null)" ]; then
        log_info "目标目录已有文件，删除旧文件"
        rm -rf {local_path}/*
    fi
    cp -r {fs_model_path}/* {local_path}/
    log_success "{model_name} 模型复制完成"
else
    log_info "autodl-fs 中未找到模型 {model_name}，从百度网盘下载..."
    cd {local_path}
    bdnd --mode download {remote_path} .
    log_success "{model_name} 模型下载完成"
"""
                if enable_cache:
                    script += f"""    # 下载完成后，如果启用了缓存，则复制一份到 autodl-fs
    if [ ! -d "{fs_model_path}" ] || [ -z "$(ls -A {fs_model_path} 2>/dev/null)" ]; then
        if [ -d "{local_path}" ] && [ "$(ls -A {local_path} 2>/dev/null)" ]; then
            log_info "缓存模型 {model_name} 到 autodl-fs..."
            mkdir -p "{fs_model_path}"
            cp -r {local_path}/* {fs_model_path}/
            log_success "模型 {model_name} 已缓存到 autodl-fs"
        fi
    fi
"""
                else:
                    script += f"""    # 缓存已禁用，不保存到 autodl-fs
"""
                script += "fi\n"
                return script
        return ""
    
    def _generate_dataset_merge_script(self, selected_repos, enable_repos, data_only,
                                     snapshots, output_dir, dataset_name, split_ratio, split_seed):
        """生成数据集合并脚本"""
        script = ""
        
        # 如果 data_only=True，不需要 git 和 cv-scripts，直接返回空脚本或简化脚本
        if data_only:
            return script
        
        # 检查是否已经选择了 cv_scripts 仓库，如果没有则需要克隆
        has_cv_scripts = False
        if enable_repos and selected_repos:
            for repo_data in selected_repos:
                if repo_data['name'] == 'cv_scripts':
                    has_cv_scripts = True
                    break
        
        if not has_cv_scripts:
            # 需要先克隆 cv-scripts 仓库
            cv_scripts_repo = self.repos.get('cv-scripts', {})
            if cv_scripts_repo:
                # 如果没有配置 Git SSH，需要先配置
                needs_git_config = not (enable_repos and selected_repos)
                if needs_git_config:
                    git_ssh_path = self.data_download_config.get('git_ssh_path', '')
                    script += f"""
# 配置 Git SSH（数据集生成需要克隆 cv-scripts）
log_info "配置 Git SSH..."
cd $HOME
rm -rf .ssh .gitconfig
# 优先从 autodl-fs 读取 Git SSH 配置
GIT_SSH_PATH="{git_ssh_path}"
if [ -n "$GIT_SSH_PATH" ] && [ -d "/root/autodl-fs/$GIT_SSH_PATH" ]; then
    log_info "从 autodl-fs 复制 Git SSH 配置: $GIT_SSH_PATH"
    cp -r "/root/autodl-fs/$GIT_SSH_PATH/.ssh" "$HOME/" 2>/dev/null || true
    cp "/root/autodl-fs/$GIT_SSH_PATH/.gitconfig" "$HOME/" 2>/dev/null || true
    if [ -d "$HOME/.ssh" ] && [ -f "$HOME/.ssh/id_rsa" ]; then
        log_success "从 autodl-fs 复制 Git SSH 配置完成"
    else
        log_info "autodl-fs 中未找到完整的 Git SSH 配置，从百度网盘下载..."
        bdnd /apps/autodl/git_ssh_backup .
    fi
else
    log_info "从百度网盘下载 Git SSH 配置..."
    bdnd /apps/autodl/git_ssh_backup .
fi
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/id_rsa
chmod 600 $HOME/.ssh/id_*
log_success "Git SSH 配置完成"

cd /root
"""
                # 构建 cv-scripts 的 git clone 命令
                cv_scripts_url = cv_scripts_repo.get('url', '')
                cv_scripts_branch = cv_scripts_repo.get('branch', '')
                if cv_scripts_branch:
                    cv_scripts_clone_cmd = f'git clone -b {cv_scripts_branch} {cv_scripts_url}'
                else:
                    cv_scripts_clone_cmd = f'git clone {cv_scripts_url}'
                
                script += f"""
# 克隆 cv-scripts 仓库（数据集生成需要）
log_step "克隆 cv-scripts 仓库..."
if [ ! -d "/root/cv-scripts" ]; then
    {cv_scripts_clone_cmd}
    log_success "cv-scripts 克隆完成"
else
    log_info "cv-scripts 仓库已存在"
fi
"""
        
        script += f"""
cd /root/autodl-tmp

# 汇总数据集
log_step "汇总数据集..."
OUTPUT_DIR="{output_dir}"
DATASET_NAME="{dataset_name}"

# 检查 cv-scripts 仓库是否存在
if [ ! -d "/root/cv-scripts" ]; then
    log_error "cv-scripts 仓库不存在，请确保已克隆该仓库"
    exit 1
fi

MERGED_COCO_SCRIPT="/root/cv-scripts/dataset/merged_coco.py"
SPLIT_COCO_SCRIPT="/root/cv-scripts/dataset/split_coco.py"

if [ ! -f "$MERGED_COCO_SCRIPT" ]; then
    log_error "合并脚本不存在: $MERGED_COCO_SCRIPT"
    exit 1
fi

if [ ! -f "$SPLIT_COCO_SCRIPT" ]; then
    log_error "划分脚本不存在: $SPLIT_COCO_SCRIPT"
    exit 1
fi

# 安装必要的 Python 依赖
log_info "安装数据集处理所需的依赖..."
pip install tqdm -q
log_success "依赖安装完成"
"""
        
        # 收集所有快照目录名
        snapshot_names = []
        for snapshot_data in snapshots:
            snapshot_id, _, _, snapshot_name, _ = self._parse_snapshot_data(snapshot_data)
            name = snapshot_name if snapshot_name else f"snapshot_{snapshot_id}"
            snapshot_names.append(name)
        
        if split_ratio:
            # 随机划分模式
            script += f"""
# 随机划分模式
log_info "使用随机划分模式 (比例: {split_ratio})"

# 创建临时合并目录
TEMP_MERGED_DIR="/root/autodl-tmp/_temp_merged"
mkdir -p "$TEMP_MERGED_DIR"

# 收集所有需要合并的目录
INPUT_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}" ]; then
    # 如果有train目录，优先使用train目录
    if [ -d "/root/autodl-tmp/{name}/train" ] && [ -f "/root/autodl-tmp/{name}/train/_annotations.coco.json" ]; then
        INPUT_DIRS="$INPUT_DIRS /root/autodl-tmp/{name}/train"
    elif [ -f "/root/autodl-tmp/{name}/_annotations.coco.json" ]; then
        INPUT_DIRS="$INPUT_DIRS /root/autodl-tmp/{name}"
    fi
fi
"""
            script += f"""
if [ -z "$INPUT_DIRS" ]; then
    log_error "没有找到有效的快照目录"
    exit 1
fi

# 先合并所有数据集
log_info "合并所有数据集..."
python3 "$MERGED_COCO_SCRIPT" --input-dirs $INPUT_DIRS --output-dir "$TEMP_MERGED_DIR"
if [ $? -ne 0 ]; then
    log_error "合并数据集失败"
    exit 1
fi

# 然后随机划分
log_info "随机划分数据集 (随机种子: {split_seed})..."
mkdir -p "$OUTPUT_DIR/$DATASET_NAME"
python3 "$SPLIT_COCO_SCRIPT" "$TEMP_MERGED_DIR" "$OUTPUT_DIR/$DATASET_NAME" --ratio {split_ratio} --seed {split_seed}
if [ $? -ne 0 ]; then
    log_error "划分数据集失败"
    exit 1
fi

# 清理临时目录
rm -rf "$TEMP_MERGED_DIR"
log_success "数据集生成完成: $OUTPUT_DIR/$DATASET_NAME"
"""
        else:
            # 按目录汇总（train/valid）
            script += f"""
# 按目录汇总模式（train/valid）
log_info "使用目录汇总模式"

# 汇总训练集
TRAIN_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}/train" ] && [ -f "/root/autodl-tmp/{name}/train/_annotations.coco.json" ]; then
    TRAIN_DIRS="$TRAIN_DIRS /root/autodl-tmp/{name}/train"
fi
"""
            script += f"""
if [ -n "$TRAIN_DIRS" ]; then
    log_info "合并训练集..."
    mkdir -p "$OUTPUT_DIR/$DATASET_NAME/train"
    python3 "$MERGED_COCO_SCRIPT" --input-dirs $TRAIN_DIRS --output-dir "$OUTPUT_DIR/$DATASET_NAME/train"
    if [ $? -ne 0 ]; then
        log_error "合并训练集失败"
        exit 1
    fi
else
    log_info "未找到训练集目录"
fi

# 汇总验证集
VALID_DIRS=""
"""
            for name in snapshot_names:
                script += f"""
if [ -d "/root/autodl-tmp/{name}/valid" ] && [ -f "/root/autodl-tmp/{name}/valid/_annotations.coco.json" ]; then
    VALID_DIRS="$VALID_DIRS /root/autodl-tmp/{name}/valid"
fi
"""
            script += f"""
if [ -n "$VALID_DIRS" ]; then
    log_info "合并验证集..."
    mkdir -p "$OUTPUT_DIR/$DATASET_NAME/valid"
    python3 "$MERGED_COCO_SCRIPT" --input-dirs $VALID_DIRS --output-dir "$OUTPUT_DIR/$DATASET_NAME/valid"
    if [ $? -ne 0 ]; then
        log_error "合并验证集失败"
        exit 1
    fi
else
    log_info "未找到验证集目录"
fi

log_success "数据集生成完成: $OUTPUT_DIR/$DATASET_NAME"
"""
        
        return script
    
    def _get_env_config_content(self, username):
        """获取用户的 .env_config.json 文件内容"""
        env_config_content = '{}'  # 默认空JSON
        env_config_file = get_user_env_config_file(username)
        if env_config_file.exists():
            try:
                with open(env_config_file, 'r', encoding='utf-8') as f:
                    env_config_content = f.read().strip()
                    # 验证JSON格式
                    json.loads(env_config_content)
            except Exception as e:
                print(f"Warning: Failed to read or parse .env_config.json: {e}")
                env_config_content = '{}'
        
        # 将 JSON 内容压缩为单行（去除换行和多余空格）
        try:
            env_config_obj = json.loads(env_config_content)
            return json.dumps(env_config_obj, separators=(',', ':'))
        except Exception:
            return env_config_content
