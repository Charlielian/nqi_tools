# -*- mode: python ; coding: utf-8 -*-
"""
NqiTool 打包配置文件
用于 PyInstaller 打包

使用方法：
    pyinstaller NqiTool.spec
"""

block_cipher = None

a = Analysis(
    ['NqiTool.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('授权工具/public_key.pem', '授权工具'),
        ('config.yaml', '.'),
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
        'core.license',
        'core.auth',
        'core.query',
        'core.export',
        # 项目内部模块 - gui
        'gui.widgets',
        'gui.login_dialog',
        'gui.main_window',
        'gui.components',
        'gui.field_configs',
        'gui.payload_templates',
        'gui.theme',
        'gui.first_run',
        # 第三方库
        'requests',
        'pandas',
        'openpyxl',
        'lxml',
        'yaml',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
        'PIL.ImageDraw',
        'pytesseract',
        'Crypto',
        'Cryptodome',
        'Cryptodome.Cipher',
        'Cryptodome.Util',
        'Cryptodome.PublicKey',
        'Cryptodome.Hash',
        'Cryptodome.Signature',
        'wmi',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3.util',
        'urllib3.util.ssl_',
        # tkinter 相关
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.scrolledtext',
        '_tkinter',
    ],
    hookspath=[],
    hooksconfig={
        'PIL': {
            'scripts': [
                'PIL._tkinter_finder',
            ],
        },
    },
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
    name='NqiTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    windowed=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
