# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（--onedir，供 Inno Setup 制作安装包）。

- 入口：app.py（图形界面）。compress.py 是命令行入口，不放进安装包。
- 资源：assets/ 会原样进入 _internal/assets，运行时由 app_window 的 BASE_DIR 解析。
- 拖拽：vendor/tkinterdnd2 随仓库附带，借助它自带的 PyInstaller hook，
  只收集当前平台 + 当前 Tcl 版本需要的 tkdnd 目录（含 DLL）。
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
IS_WINDOWS = sys.platform == "win32"

datas = [(str(ROOT / "assets"), "assets")]
hiddenimports = []
hookspath = []
excludes = ["pytest", "unittest", "pydoc_data"]

if IS_WINDOWS:
    # 拖拽组件是随仓库附带的，需要显式加入模块搜索路径
    sys.path.insert(0, str(ROOT / "vendor"))
    hiddenimports.append("tkinterdnd2")
    hookspath.append(str(ROOT / "vendor" / "tkinterdnd2" / "__pyinstaller"))
else:
    # tkinterdnd2 只带桌面平台预编译库，其它平台退化为“点击选择文件夹”
    excludes.append("tkinterdnd2")

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT), str(ROOT / "vendor")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LightPress",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "logo.ico") if IS_WINDOWS else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LightPress",
)
