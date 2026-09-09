# -*- mode: python ; coding: utf-8 -*-
"""
NqiTool_qt 打包配置文件
用于 PyInstaller 打包 Qt6 现代化版本
"""

block_cipher = None

a = Analysis(
    ['NqiTool_qt.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 字段配置数据文件
        ('gui/field_configs.json', 'gui'),
        # Qt QSS 样式表目录
        ('qt_gui/styles', 'qt_gui/styles'),
    ],
    hiddenimports=[
        # 项目内部模块 - utils
        'utils.config',
        'utils.logger',
        'utils.crypto',
        'utils.helpers',
        'utils.constants',
        'utils.excel_styler',
        'utils.retry',
        # 项目内部模块 - core
        'core.auth',
        'core.query',
        'core.export',
        'core.common',
        'core.session_mixin',
        'core.payload_builder_mixin',
        'core.data_fetcher_mixin',
        'core.voice_merger_mixin',
        'core.flow_table_builder',
        'core.workers',
        # 项目内部模块 - gui 与 qt_gui
        'gui.widgets',
        'gui.field_configs',
        'gui.payload_templates',
        'qt_gui',
        'qt_gui.main_window',
        'qt_gui.components',
        'qt_gui.components.date_range_picker',
        'qt_gui.components.multi_select_combo',
        'qt_gui.components.log_panel',
        'qt_gui.components.login_dialog',
        'qt_gui.components.week_selector',
        # 第三方库
        'requests',
        'pandas',
        'openpyxl',
        'xlsxwriter',
        'lxml',
        'yaml',
        'PIL',
        'PIL.Image',
        'Crypto',
        'Cryptodome',
        'Cryptodome.Cipher',
        'Cryptodome.PublicKey',
        'wmi',
        'urllib3',
        'certifi',
        # PyQt6 相关
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NqiTool_qt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 模式，不显示黑色控制台黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
