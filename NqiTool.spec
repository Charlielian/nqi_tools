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
        'utils.config',
        'utils.logger',
        'utils.crypto',
        'utils.helpers',
        'core.license',
        'core.auth',
        'core.query',
        'core.export',
        'gui.widgets',
        'gui.login_dialog',
        'gui.main_window',
        'requests',
        'pandas',
        'openpyxl',
        'lxml',
        'yaml',
        'PIL',
        'pytesseract',
        'Crypto',
        'Cryptodome',
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
