# AutoDL Flow

## 项目简介

AutoDL Flow 是一个基于 Flask 的 Web 工具，用于自动生成作业执行脚本。项目采用模块化设计，代码结构清晰，易于维护和扩展。

## 项目结构

项目已重构为标准化的目录结构，详情请参考 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)。

### 主要目录

- `backend/` - 后端代码
  - `auth/` - 认证模块
  - `services/` - 业务逻辑服务层
  - `utils/` - 工具函数模块
  - `routes/` - 路由模块
- `frontend/` - 前端代码
  - `templates/` - HTML 模板
  - `static/` - 静态资源（CSS、JS、图片等）
- `data/` - 数据文件目录（所有用户数据存储在这里）
  - `scripts/` - 历史脚本
  - `configs/` - 用户配置
  - `temp_scripts/` - 临时脚本
  - `deployment_configs/` - 部署配置
  - `deployment_records/` - 部署记录
- `scripts/` - 工具脚本
  - `migrate_data.py` - 数据迁移脚本
  - `package_project.sh` - 项目打包脚本

## 功能说明

这是一个基于 Flask 的 Web 工具，用于自动生成作业执行脚本。

### 主要功能

1. **选择代码仓库**：可选择需要克隆和安装的代码仓库
   - hq_det（可选择是否安装依赖）
   - hq_job（可选择是否安装）
   - Image-Comparison-Tool（可选择是否安装）
   - **每个仓库都支持独立选择是否安装**

2. **选择数据快照**：可添加多个数据快照ID和对应的名称

3. **模型下载**：可选择需要下载的模型文件
   - 支持从百度网盘下载（配置 `remote_path`）
   - 支持从 URL 直接下载（配置 `url`，如 GitHub Releases）

4. **数据集生成**：
   - 按目录生成：将所有快照的 `train` 目录合并为训练集，`valid` 目录合并为验证集
   - 随机划分：将所有图片随机划分为训练集和验证集（可设置比例）

## 使用方法

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置密钥（重要）

**快速修复：**
如果遇到 `SECRET_KEY 未设置` 错误，可以使用修复脚本：
```bash
./fix_secret_key.sh
```

**开发环境**（可选）：
```bash
# 未设置时会自动生成临时密钥（仅用于开发测试）
# 建议设置：export FLASK_SECRET_KEY='your-dev-secret-key'
```

**生产环境**（必须）：
```bash
# 必须设置强密钥，长度至少 32 字符
export FLASK_ENV=production
export FLASK_SECRET_KEY='your-strong-secret-key-at-least-32-chars'

# 生成强密钥的方法：
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**常见问题：**
- **错误：`SECRET_KEY 未设置！检测到生产环境`**
  - 如果这是开发环境，取消生产环境设置：`unset FLASK_ENV` 或 `unset ENVIRONMENT`
  - 如果是生产环境，设置密钥：`export FLASK_SECRET_KEY='your-secret-key'`
  
- **错误：`SECRET_KEY 长度不足`**
  - 使用至少 32 字符的密钥
  - 生成密钥：`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

### 运行工具

**开发环境：**
```bash
python app.py
# 或使用启动脚本
./scripts/start_app.sh
```

**生产环境：**
```bash
# 使用生产环境启动脚本（会自动加载 .env.production）
./scripts/start_production.sh
```

然后在浏览器中访问：`http://localhost:6008`（默认端口 6008）

### 使用步骤

1. **选择代码仓库**：在界面上勾选需要克隆的仓库
2. **添加数据快照**：
   - 设置快照数量
   - 为每个快照输入ID和名称（名称可选）
3. **配置数据集生成**：
   - 设置输出目录（默认：`/root/autodl-tmp`）
   - 设置数据集名称（默认：`merged_dataset`）
   - 选择生成方式：
     - 按目录生成：自动合并所有快照的 train/valid 目录
     - 随机划分：随机划分所有图片（可设置训练集比例）
4. **生成脚本**：点击"生成执行脚本"按钮，查看生成的脚本
5. **下载脚本**：点击"下载脚本"按钮保存为 `auto_job.sh`

## 生成的脚本功能

生成的脚本会自动执行以下操作：

1. 设置环境配置（百度网盘访问令牌等）
2. 安装 bdnd 工具
3. 下载 SSH 配置
4. 克隆选定的代码仓库
5. 安装需要安装的仓库依赖
6. 下载所有选定的数据快照（优先从 `/root/autodl-fs` 复制，不存在则下载）
7. 下载所有选定的模型文件（优先从 `/root/autodl-fs` 复制，不存在则下载，支持 URL 下载和百度网盘下载）
8. 生成数据集（按目录或随机划分）
9. 合并 COCO 格式的标注文件

## 缓存机制

生成的脚本支持智能缓存机制，可以避免重复下载并自动建立缓存：

### 缓存选项说明

每个快照和模型都有一个"启用缓存"选项：
- **启用缓存**：既会从 autodl-fs 读取已有缓存，也会在下载后保存新缓存
- **禁用缓存**：仍会从 autodl-fs 读取已有缓存（如果存在），但下载后不会保存新缓存

**注意**：禁用缓存只是不保存新缓存，而不是不使用已有缓存。这样可以节省存储空间，同时仍然可以利用已有的缓存文件。

### 快照缓存
- **读取缓存**：无论是否启用缓存，脚本都会先检查 `/root/autodl-fs/{快照名称}` 目录是否存在
  - 如果存在，直接复制到 `/root/autodl-tmp/{快照名称}`，跳过下载
  - 如果不存在，才执行下载操作
- **保存缓存**：只有启用缓存时，下载完成后才会复制一份到 `/root/autodl-fs/{快照名称}` 作为缓存

### 模型缓存
- **读取缓存**：无论是否启用缓存，脚本都会先检查 `/root/autodl-fs/model/{模型名称}` 目录是否存在
  - 对于 URL 下载：优先检查是否存在对应的模型文件
  - 对于百度网盘下载：检查整个模型目录
  - 如果存在，直接复制到目标路径，跳过下载
  - 如果不存在，才执行下载操作
- **保存缓存**：只有启用缓存时，下载完成后才会复制一份到 `/root/autodl-fs/model/{模型名称}` 作为缓存

这样可以显著提高脚本执行速度，特别是在重复运行相同配置时。首次下载后如果启用了缓存会自动建立缓存，后续运行可以直接使用缓存，无需重复下载。

## 多账户系统

工具支持多账户登录，每个账户的数据是隔离的：

### 账户配置

在配置文件中配置多个账户：

```json
{
    "accounts": {
        "admin": "admin_password",
        "user1": "user1_password",
        "user2": "user2_password"
    }
}
```

### 权限说明

- **admin 账户**：拥有最高权限
  - 可以查看所有用户保存的脚本和配置
  - 可以访问所有用户的数据
  - 脚本和配置保存在根目录

- **普通账户**：数据隔离
  - 只能查看和操作自己保存的脚本和配置
  - 脚本和配置保存在各自的用户目录下
  - 无法访问其他用户的数据

### 数据存储结构

所有数据存储在项目目录内的 `data/` 目录中：

```
data/
├── scripts/                       # 脚本存储目录
│   ├── script1.sh                # admin 的脚本（根目录）
│   ├── admin/                    # admin 的脚本目录
│   │   └── script2.sh
│   ├── user1/                    # user1 的脚本目录
│   │   └── script3.sh
│   └── user2/                    # user2 的脚本目录
│       └── script4.sh
│
├── configs/                       # 配置存储目录
│   ├── config1.json              # admin 的配置（根目录）
│   ├── admin/                    # admin 的配置目录
│   │   └── config2.json
│   ├── user1/                    # user1 的配置目录
│   │   └── config3.json
│   └── user2/                    # user2 的配置目录
│       └── config4.json
│
├── temp_scripts/                  # 临时脚本目录
├── deployment_configs/            # 部署配置目录
└── deployment_records/             # 部署记录目录
```

**注意**：所有数据都在项目目录内，方便打包和迁移到其他服务器。

## 项目可移植性

项目已完全可移植，所有配置和数据都在项目目录内：

- ✅ 所有数据存储在 `data/` 目录
- ✅ 所有配置文件在项目根目录
- ✅ 使用相对路径，不依赖系统目录

### 打包项目

```bash
./scripts/package_project.sh
```

### 迁移到新服务器

1. 传输打包文件到新服务器
2. 解压项目
3. 安装依赖：`pip install -r requirements.txt`
4. 启动应用：`python app.py`

详细说明请参考 [DATA_MIGRATION_GUIDE.md](DATA_MIGRATION_GUIDE.md) 和 [PORTABILITY_SUMMARY.md](PORTABILITY_SUMMARY.md)。

## 注意事项

- 确保已配置 `.config` 文件（包含 API 凭证）
- 确保已安装 `moli_dataset_export.py` 脚本
- 生成的脚本需要在 Linux 环境下运行
- 随机划分使用固定随机种子（42）确保可复现
- 如果 `/root/autodl-fs` 目录中有缓存文件，脚本会优先使用缓存，避免重复下载
- **多账户配置**：在配置文件中使用 `accounts` 字段配置多个账户，`login` 字段用于向后兼容
- **数据存储**：所有数据存储在项目目录内的 `data/` 目录，方便打包和迁移

## 模型配置说明

模型配置支持两种下载方式：

### 1. 从百度网盘下载（原有方式）

```json
{
    "models": {
        "dino": {
            "remote_path": "/apps/autodl/model/dino/",
            "local_path": "/root/autodl-tmp/model/dino"
        }
    }
}
```

### 2. 从 URL 直接下载（新增）

```json
{
    "models": {
        "rtdetrv2": {
            "url": "https://github.com/lyuwenyu/storage/releases/download/v0.1/rtdetrv2_r34vd_120e_coco_ema.pth",
            "local_path": "/root/autodl-tmp/model/rtdetrv2",
            "filename": "rtdetrv2_r34vd_120e_coco_ema.pth"
        }
    }
}
```

**配置字段说明：**
- `url`（必需）：模型文件的下载 URL
- `local_path`（必需）：本地保存路径
- `filename`（可选）：保存的文件名，如果不指定则从 URL 中自动提取

**优先级：** 如果同时配置了 `url` 和 `remote_path`，优先使用 `url` 下载。

