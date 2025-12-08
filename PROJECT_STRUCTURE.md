# AutoDL Flow - 项目结构说明

## 项目目录结构

```
autodl_autoscripts/
├── app.py                    # 原始应用文件（保留用于兼容）
├── app_new.py                # 重构后的主应用入口
├── run.py                    # 运行入口（可选）
├── requirements.txt           # Python 依赖
├── README.md                  # 项目说明
├── PROJECT_STRUCTURE.md       # 项目结构说明（本文件）
│
├── backend/                   # 后端代码
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   │
│   ├── auth/                  # 认证模块
│   │   ├── __init__.py
│   │   ├── decorators.py      # 认证装饰器
│   │   └── utils.py           # 认证工具函数
│   │
│   ├── services/              # 业务逻辑服务层
│   │   ├── __init__.py
│   │   ├── config_service.py  # 配置管理服务
│   │   ├── script_generator.py # 脚本生成服务（待完善）
│   │   ├── account_service.py # 账户管理服务
│   │   └── category_service.py # 类别映射组服务
│   │
│   ├── utils/                 # 工具函数模块
│   │   ├── __init__.py
│   │   ├── storage.py         # 存储相关工具
│   │   ├── token.py           # Token 管理工具
│   │   └── encryption.py      # 加密工具
│   │
│   └── routes/                # 路由模块
│       ├── __init__.py
│       ├── auth_routes.py     # 认证路由
│       ├── view_routes.py     # 视图路由
│       ├── api_routes.py      # API 路由注册
│       └── api/                # API 子路由
│           ├── __init__.py
│           ├── script_routes.py    # 脚本相关 API
│           ├── config_routes.py    # 配置相关 API
│           ├── account_routes.py   # 账户管理 API
│           ├── autodl_routes.py    # AutoDL API
│           ├── category_routes.py  # 类别映射组 API
│           └── user_routes.py      # 用户相关 API
│
├── frontend/                  # 前端代码
│   ├── static/                # 静态资源
│   │   ├── css/               # CSS 文件
│   │   ├── js/                 # JavaScript 文件
│   │   └── images/             # 图片资源
│   └── templates/             # 模板文件
│       ├── dashboard.html
│       ├── login.html
│       ├── index.html
│       ├── task_submit.html
│       └── experiment_manage.html
│
├── data/                      # 数据文件目录
│   ├── configs/               # 配置文件
│   └── storage/               # 存储文件
│
└── 配置文件（根目录）
    ├── repos_config.json
    ├── .accounts.json
    ├── .category_groups.json
    └── run_script_templates.json
```

## 模块说明

### 后端模块

#### 1. config.py
- 集中管理所有配置常量
- 包括文件路径、目录配置、数据中心映射等
- 处理可选依赖的导入

#### 2. auth/ 认证模块
- `decorators.py`: 登录验证装饰器
- `utils.py`: 密码哈希、账户验证等工具函数

#### 3. services/ 服务层
- `config_service.py`: 用户配置的加载和保存
- `script_generator.py`: 脚本生成服务（待完善）
- `account_service.py`: 账户管理服务
- `category_service.py`: 类别映射组管理服务

#### 4. utils/ 工具函数
- `storage.py`: 文件存储、目录管理相关工具
- `token.py`: 临时下载 token 管理
- `encryption.py`: Token 加密存储工具

#### 5. routes/ 路由模块
- `auth_routes.py`: 登录、登出路由
- `view_routes.py`: 页面视图路由
- `api_routes.py`: API 路由注册入口
- `api/`: API 子路由模块

### 前端模块

#### templates/
- HTML 模板文件，已移动到 `frontend/templates/`

#### static/
- 静态资源目录（CSS、JS、图片等）

