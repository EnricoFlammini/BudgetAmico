# -*- mode: python ; coding: utf-8 -*-

VERSION = '0.24.00'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('docs', 'docs'), ('.env', '.')],
    hiddenimports=['yfinance', 'python_dotenv', 'pg8000', 'scramp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Moduli di test e sviluppo
        'pytest', 'unittest', 'test', 'tests',
        # Moduli non necessari
        'tkinter', 'tcl', 'tk',
        'IPython', 'jupyter', 'notebook',
        'sphinx', 'docutils',
        'setuptools', 'pip', 'wheel',
        # Pre-commit e linting
        'pre_commit', 'black', 'flake8', 'pylint', 'mypy',
        # psycopg2 non piu usato
        'psycopg2', 'psycopg2_binary',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Budget Amico_{VERSION}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
