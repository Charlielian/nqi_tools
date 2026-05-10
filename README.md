# NQI工具

NQI平台数据提取工具，支持多种数据表的自动导出，包括4G/5G干扰小区、容量报表、MR覆盖、语音报表、小区性能KPI等。

## 功能特点

- **现代化图形界面**：简洁美观的GUI界面，采用卡片式布局设计
- **自动化导出**：支持多种数据表的自动查询和导出功能
- **多线程并发**：支持多报表并发查询，大幅提升数据提取效率
- **自定义字段选择**：支持动态获取表字段配置，用户可选择要导出的字段
- **按日查询**：支持按日分Sheet导出，满足复杂需求
- **自动配置生成**：EXE运行时自动生成默认 `config.yaml`，无需手动创建
- **API测试工具**：提供 CLI 交互式测试脚本，支持多线程并发测试所有报表接口
- **授权验证系统**：集成完整的授权验证机制，确保安全使用
- **自动构建发布**：GitHub Actions 自动打包 EXE 并生成包含配置文件的 ZIP 发布包

## 支持的数据源

| 分类 | 报表 |
|------|------|
| **干扰** | 4G干扰小区、5G干扰小区 |
| **容量** | 5G小区容量报表、重要场景-天 |
| **工参** | 4G小区工参报表、5G小区工参报表 |
| **MR覆盖** | 4GMR覆盖-小区天、5GMR覆盖-小区天 |
| **语音报表** | 4G语音-VoLTE、4G语音-EPSFB、5G语音小区 |
| **语音预警** | VoLTE小区监控预警、EPSFB小区监控预警、VONR小区监控预警 |
| **小区性能** | 4G小区性能KPI报表、5G小区性能KPI报表 |
| **全程完好率** | 4G全程完好率报表、5G全程完好率报表 |

## 环境要求

- Python 3.9+
- Windows

## 安装步骤

### 方法一：直接使用已构建的 EXE（推荐）

1. 访问 GitHub 仓库的 [Actions](https://github.com/Charlielian/export_tools/actions) 页面
2. 选择最新的成功构建
3. 下载 `NqiTool.zip` 构建产物
4. 解压后运行 `NqiTool.exe`

> ZIP 包已包含 `config.yaml` 和必要的运行时目录，解压即可使用。

### 方法二：从源码运行

1. 克隆项目
```bash
git clone https://github.com/Charlielian/export_tools.git
cd export_tools
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置文件
编辑 `config.yaml` 文件，配置您的用户名、密码等信息。

## 使用方法

### 主程序

```bash
python NqiTool.py
```

**使用步骤：**

1. **启动程序**：运行 `NqiTool.py` 或 `NqiTool.exe`
2. **登录系统**：输入用户名和密码，点击"登录"按钮
3. **选择数据分类**：在"查询参数"中选择您需要的数据分类
4. **选择数据表**：从下拉框中选择要查询的数据表（支持多选）
5. **设置查询参数**：
   - 选择地市（支持多选）
   - 设置日期范围（可使用快捷日期按钮）
   - 可选择按日查询
6. **自定义字段（可选）**：
   - 勾选"自定义字段"复选框
   - 点击"选择字段"按钮
   - 在弹出的窗口中选择要导出的字段
7. **开始提取**：点击"开始提取"按钮
8. **查看结果**：提取完成后，数据会自动导出到 `data_output` 目录

### API 测试脚本

```bash
# 交互式测试（选择报表、配置参数）
python test_api.py

# 支持多线程并发测试，可配置线程数（默认3，最大10）
```

测试日志保存在 `logs/test_api/` 目录下。

## 项目结构

```
.
├── NqiTool.py                   # 主程序入口
├── NqiTool.spec                 # PyInstaller 打包配置
├── test_api.py                  # API 统一测试脚本（多线程版）
├── test_cluster_api.py          # 集群 API 测试脚本
├── requirements.txt             # Python 依赖列表
├── config.yaml                  # 配置文件（运行时自动生成）
├── README.md                    # 项目说明文档
│
├── .github/workflows/
│   └── build.yml                # GitHub Actions 自动构建配置
│
├── core/                        # 核心功能模块
│   ├── auth.py                  # 登录认证和会话管理
│   ├── query.py                 # 数据查询（支持多线程并发）
│   ├── export.py                # Excel 导出功能
│   └── license.py               # 授权管理和机器码生成
│
├── gui/                         # GUI 组件模块
│   ├── main_window.py           # 主窗口实现
│   ├── login_dialog.py          # 登录对话框
│   ├── widgets.py               # 自定义 GUI 组件（含报表配置注册表）
│   ├── components.py            # 通用 UI 组件
│   ├── field_configs.py         # 字段配置管理
│   ├── first_run.py             # 首次运行引导向导
│   ├── payload_templates.py     # 各报表 Payload 构建模板
│   └── theme.py                 # 界面主题配置
│
├── utils/                       # 工具函数模块
│   ├── config.py                # 配置管理（自动生成默认配置）
│   ├── constants.py             # 全局常量定义
│   ├── logger.py                # 日志系统
│   ├── crypto.py                # 加密工具
│   ├── helpers.py               # 辅助函数（验证码处理等）
│   ├── excel_styler.py          # Excel 样式美化
│   └── retry.py                 # 请求重试机制
│
├── 授权工具/                    # 授权相关工具
│   ├── NqiTool_license_creator.py  # 许可证创建器
│   └── public_key.pem           # 公钥文件
│
├── data_output/                 # 数据输出目录
├── cookies/                     # Cookie 存储目录
├── captcha_images/              # 验证码图片目录
└── logs/                        # 日志目录
```

## 依赖说明

| 依赖 | 版本 | 说明 |
|------|------|------|
| `requests` | >=2.28.0 | HTTP 请求库 |
| `pandas` | >=1.5.0 | 数据处理 |
| `openpyxl` | >=3.0.0 | Excel 导出 |
| `pycryptodome` | >=3.15.0 | RSA 加密 |
| `lxml` | >=4.9.0 | XML/HTML 解析 |
| `Pillow` | >=9.0.0 | 图片处理（验证码识别） |
| `pyyaml` | >=6.0 | YAML 配置文件解析 |
| `wmi` | >=1.5.1 | Windows 系统信息（机器码） |

## 自动构建

项目使用 GitHub Actions 自动构建 EXE 文件。每次推送到 `master` 分支时自动触发：

1. 安装 Python 3.13 + 项目依赖
2. 创建默认 `config.yaml`
3. 使用 PyInstaller 打包 EXE
4. 打包为 ZIP（包含 EXE + config.yaml + 运行时目录）
5. 上传构建产物到 Actions Artifacts

**ZIP 包结构：**
```
NqiTool.zip
└── NqiTool/
    ├── NqiTool.exe
    ├── config.yaml
    ├── data_output/
    ├── cookies/
    ├── captcha_images/
    └── logs/
```

## 授权说明

项目包含授权工具，用于生成和管理许可证。

### 授权流程

1. 首次运行程序会生成机器码
2. 将机器码发送给管理员获取授权文件
3. 将授权文件放在程序目录下，程序会自动验证授权

## 更新日志

### v2.1.0 (2026-05-10)
- 新增：API 统一测试脚本 `test_api.py`，支持 CLI 交互选择报表
- 新增：多线程并发测试，可配置线程数（默认3，最大10）
- 新增：自动从 `TableConfig` 读取报表列表，无需硬编码
- 新增：首次运行引导向导 `first_run.py`
- 新增：`config.yaml` 运行时自动生成，无需手动创建
- 优化：GitHub Actions 打包输出为 ZIP（含配置文件和运行时目录）
- 优化：补充 `NqiTool.spec` hiddenimports 缺失模块
- 优化：新增 `utils/retry.py` 请求重试机制
- 优化：新增 `utils/excel_styler.py` Excel 样式美化
- 优化：新增 `utils/constants.py` 全局常量管理

### v2.0.0 (2026-04-26)
- 重构：模块化拆分项目，提升代码可维护性
- 新增：现代化 GUI 界面设计，采用卡片式布局
- 新增：自定义字段选择功能，支持动态获取表字段配置
- 新增：多选择下拉框组件
- 优化：授权验证系统
- 优化：Excel 导出格式化效果

### v1.0.0
- 初始版本发布
- 基础数据提取功能
- GUI 界面实现
- 授权系统集成

## License

MIT License
