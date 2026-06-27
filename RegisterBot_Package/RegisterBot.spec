# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/__init__.py', 'src'), ('src/config.py', 'src'), ('src/xiaowei_client.py', 'src'), ('src/phone_bot.py', 'src'), ('src/db_handler.py', 'src'), ('src/excel_handler.py', 'src'), ('src/gmail_otp.py', 'src'), ('src/mock_captcha.py', 'src'), ('src/captcha_helper.py', 'src'), ('src/web_server.py', 'src'), ('src/web', 'src/web'), ('data/accounts.xlsx', 'data')],
    hiddenimports=['openpyxl', 'pandas', 'httpx', 'imaplib', 'email', 'flask', 'sqlite3', 'src', 'src.xiaowei_client', 'src.phone_bot', 'src.db_handler', 'src.excel_handler', 'src.gmail_otp', 'src.config', 'src.captcha_helper', 'src.web_server', 'src.mock_captcha'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RegisterBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RegisterBot',
)
