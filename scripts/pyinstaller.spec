from PyInstaller.utils.hooks import collect_data_files
from sys import platform

block_cipher = None

a = Analysis(
    ['../src/app.py'],
    pathex=[],
    binaries=[
        ('../src/lib/win/*.dll', 'lib/win')
    ] if platform == 'win32' else [],
    datas=[
        ('../src/kanjidic.db', '.'),
        ('../src/data/img/ico/app.ico', 'data/img/ico')
    ] + collect_data_files('cairosvg') + collect_data_files('cairocffi') + collect_data_files('pywin32'),
    hiddenimports=['wmi', 'pywin32', 'pystray', 'tkinter', 'PIL.ImageTk', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kanjireader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../src/data/img/ico/app.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kanjireader'
)