# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['bg3_compatibility_generator.pyw'],
    pathex=[],
    binaries=[],
    datas=[('src/asset/image/打包图标.ico', 'src/asset/image'), ('locales', 'locales'), ('src', 'src'), ('src/asset', 'src/asset'), ('src/asset/image/sponsor.jpg', '.'), ('src/asset/image/sponsor.jpg', 'src/asset/image')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', 'tkinter.scrolledtext', 'PIL', 'PIL.Image', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy'],
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
    name='BG3_Race_CC_Generator',
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
    icon=['src\\asset\\image\\打包图标.ico'],
)
