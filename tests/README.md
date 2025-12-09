# 单元测试说明

## 概述

本项目使用 `pytest` 编写单元测试，测试覆盖关键业务逻辑服务。

## 安装测试依赖

```bash
pip install -r requirements.txt
```

或者单独安装测试依赖：

```bash
pip install pytest pytest-cov pytest-mock
```

## 运行测试

### 运行所有测试

```bash
pytest tests/ -v
```

### 运行特定测试文件

```bash
pytest tests/backend/services/test_script_generator.py -v
```

### 运行特定测试类

```bash
pytest tests/backend/services/test_script_generator.py::TestScriptGenerator -v
```

### 运行特定测试方法

```bash
pytest tests/backend/services/test_script_generator.py::TestScriptGenerator::test_generate_script_basic -v
```

## 生成覆盖率报告

### 终端输出

```bash
pytest tests/ --cov=backend --cov-report=term-missing
```

### HTML 报告

```bash
pytest tests/ --cov=backend --cov-report=html
```

生成的 HTML 报告位于 `htmlcov/index.html`

### XML 报告（用于 CI/CD）

```bash
pytest tests/ --cov=backend --cov-report=xml
```

## 测试覆盖率目标

目标覆盖率：**>80%**

当前配置在 `pytest.ini` 中设置了 `--cov-fail-under=80`，如果覆盖率低于 80%，测试将失败。

## 测试结构

```
tests/
├── conftest.py                    # pytest 配置和 fixtures
├── backend/
│   └── services/
│       ├── test_script_generator.py    # ScriptGenerator 测试
│       ├── test_config_service.py      # ConfigService 测试
│       ├── test_category_service.py    # CategoryService 测试
│       └── test_account_service.py     # AccountService 测试
└── README.md                      # 本文件
```

## 测试 Fixtures

在 `conftest.py` 中定义了以下 fixtures：

- `temp_dir`: 创建临时目录用于测试
- `sample_repos`: 示例仓库配置
- `sample_data_download_config`: 示例数据下载配置
- `sample_models`: 示例模型配置
- `sample_category_groups`: 示例类别映射组
- `sample_user_config`: 示例用户配置文件
- `mock_env_config_file`: 模拟的 .env_config.json 文件
- `mock_accounts`: 模拟账户数据

## 编写新测试

1. 在相应的测试文件中添加新的测试方法
2. 测试方法名应以 `test_` 开头
3. 使用 fixtures 来提供测试数据
4. 使用 `unittest.mock` 来模拟外部依赖

示例：

```python
def test_new_feature(self, sample_repos):
    """测试新功能"""
    service = ScriptGenerator(sample_repos, {}, {})
    result = service.new_method()
    assert result is not None
```

## 注意事项

- 测试应该独立运行，不依赖外部服务
- 使用 mock 来隔离外部依赖
- 测试应该快速执行
- 每个测试应该只测试一个功能点

