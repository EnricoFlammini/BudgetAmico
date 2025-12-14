# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['yfinance', 'python_dotenv', 'pg8000', 'scramp'],
    hookspath=['hooks'],
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
        'pyinstaller',
        # Moduli grafici non usati
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        # Pre-commit e linting
        'pre_commit', 'black', 'flake8', 'pylint', 'mypy',
    ],
    noarchive=False,
    optimize=2,  # Ottimizzazione bytecode
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Budget Amico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip symbols
    upx=True,    # Compressione UPX
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='Budget Amico',
)
