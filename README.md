# NQI工具

NQI平台数据提取工具，支持多种数据表的自动导出，包括4G干扰小区、5G干扰小区、5G小区容量报表等。

## 功能特点

- **现代化图形界面**：简洁美观的GUI界面，采用卡片式布局设计
- **自动化导出**：支持多种数据表的自动查询和导出功能
- **自定义字段选择**：支持动态获取表字段配置，用户可选择要导出的字段
- **多日模式**：支持按日分Sheet导出，满足复杂需求
- **授权验证系统**：集成完整的授权验证机制，确保安全使用
- **多种数据源支持**：
  - 4G干扰小区
  - 5G干扰小区
  - 5G小区容量报表
  - 重要场景-天
  - 5G小区工参报表
  - 4G小区工参报表
  - 5GMR覆盖-小区天
  - 4GMR覆盖-小区天
  - VoLTE小区监控预警
  - VONR小区监控预警
  - EPSFB小区监控预警
  - 5G小区性能KPI报表
  - 4G小区性能KPI报表
  - 4G全程完好率报表
  - 5G全程完好率报表
  - 4G语音小区
  - 5G语音小区

## 环境要求

- Python 3.7+
- Windows/Linux/macOS

## 安装步骤

### 方法一：直接使用已构建的 EXE（推荐）

1. 访问 GitHub 仓库的 [Actions](https://github.com/Charlielian/export_tools/actions) 页面
2. 选择最新的成功构建
3. 下载 `NqiTool` 构建产物
4. 解压后运行 `NqiTool.exe`

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

```bash
python NqiTool.py
```

### 使用步骤

1. **启动程序**：运行 `NqiTool.py` 或 `NqiTool.exe`
2. **登录系统**：输入用户名和密码，点击"登录"按钮
3. **选择数据分类**：在"查询参数"中选择您需要的数据分类
4. **选择数据表**：从下拉框中选择要查询的数据表（支持多选）
5. **设置查询参数**：
   - 选择地市（支持多选）
   - 设置日期范围（可使用快捷日期按钮）
   - 可选择多日模式
6. **自定义字段（可选）**：
   - 勾选"自定义字段"复选框
   - 点击"选择字段"按钮
   - 在弹出的窗口中选择要导出的字段
   - 点击"确定"保存选择
7. **开始提取**：点击"开始提取"按钮
8. **查看结果**：提取完成后，数据会自动导出到 `data_output` 目录

## 项目结构

```
.
├── NqiTool.py                   # 主程序入口
├── NqiTool.spec                 # PyInstaller打包配置
├── requirements.txt             # Python依赖列表
├── config.yaml                  # 配置文件
├── README.md                    # 项目说明文档
├── core/                        # 核心功能模块
│   ├── auth.py                  # 登录认证和会话管理
│   ├── query.py                 # 数据查询功能
│   ├── export.py                # Excel导出功能
│   └── license.py               # 授权管理和机器码生成
├── gui/                         # GUI组件模块
│   ├── main_window.py           # 主窗口实现
│   ├── login_dialog.py          # 登录对话框
│   └── widgets.py               # 自定义GUI组件
├── utils/                       # 工具函数模块
│   ├── config.py                # 配置管理
│   ├── logger.py                # 日志系统
│   └── crypto.py                # 加密工具
├── 授权工具/                    # 授权相关工具
│   ├── NqiTool_license_creator.py  # 许可证创建器
│   ├── license_records.json     # 许可证记录
│   └── public_key.pem           # 公钥文件
├── captcha_images/              # 验证码图片目录
├── cookies/                     # Cookie存储目录
├── data_output/                 # 数据输出目录
└── logs/                        # 日志目录
```

## 依赖说明

- `requests>=2.28.0` - HTTP请求库
- `pandas>=1.5.0` - 数据处理
- `openpyxl>=3.0.0` - 用于Excel导出
- `pycryptodome>=3.15.0` - RSA加密
- `lxml>=4.9.0` - XML/HTML解析
- `Pillow>=9.0.0` - 图片处理
- `pyyaml>=6.0` - YAML配置文件解析
- `pyinstaller>=6.0.0` - 用于打包EXE

## 自动构建

项目使用 GitHub Actions 自动构建 EXE 文件。每次推送到 `master` 分支时，系统会自动：

1. 安装依赖
2. 创建配置文件
3. 使用 PyInstaller 打包 EXE
4. 上传构建产物

## 授权说明

项目包含授权工具，用于生成和管理许可证。授权工具位于 `授权工具/` 目录下，包含密钥生成和许可证创建功能。

### 授权流程

1. 首次运行程序会生成机器码
2. 将机器码发送给管理员获取授权文件
3. 将授权文件放在程序目录下，程序会自动验证授权

## 更新日志

### v2.0.0 (2026-04-26)
- 重构：模块化拆分项目，提升代码可维护性
- 新增：现代化GUI界面设计，采用卡片式布局
- 新增：自定义字段选择功能，支持动态获取表字段配置
- 新增：多选择下拉框组件
- 优化：授权验证系统
- 优化：Excel导出格式化效果

### v1.0.0
- 初始版本发布
- 基础数据提取功能
- GUI界面实现
- 授权系统集成

## License

MIT License
