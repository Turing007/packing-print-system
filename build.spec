# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for 装箱打印系统。

用法：
    pyinstaller --clean build.spec

注意：本文件由 build.bat 自动调用；版本号从 updater.py 读取后注入到产物文件名。
"""

import os
import sys
import re
from pathlib import Path

# 读取当前版本号（与 updater.py / NSIS 安装器保持单一来源）
def _read_version():
    here = Path(SPECPATH).resolve()
    updater = here / "updater.py"
    if not updater.is_file():
        return "0.0.0"
    text = updater.read_text(encoding="utf-8")
    m = re.search(r'__CURRENT_VERSION__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "0.0.0"

APP_VERSION = _read_version()
APP_NAME = "装箱打印系统"

# 自动探测 Tcl/Tk 路径，避免硬编码用户家目录
def _find_tcl_tk():
    """探测当前 Python 解释器自带的 tcl/tk 目录。"""
    candidates = []
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    candidates.append(Path(base_prefix) / "tcl")
    candidates.append(Path(sys.prefix) / "tcl")
    # pyenv / embed 等场景
    candidates.append(Path(sys.executable).parent / "tcl")
    candidates.append(Path(sys.executable).parent / ".." / "tcl")

    found = {"tcl": None, "tk": None}
    for c in candidates:
        try:
            if not c.is_dir():
                continue
            for sub in c.iterdir():
                if sub.is_dir():
                    if sub.name.startswith("tcl"):
                        found["tcl"] = str(sub.resolve())
                    elif sub.name.startswith("tk"):
                        found["tk"] = str(sub.resolve())
            if found["tcl"] and found["tk"]:
                return found["tcl"], found["tk"]
        except Exception:
            continue
    return None, None

tcl_dir, tk_dir = _find_tcl_tk()

datas = [('packing_label.css', '.')]
hidden = ['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog',
          'json', 'os', 'tempfile', 'webbrowser', 'datetime', 'dataclasses', 'typing',
          'updater', 'tray', 'pystray', 'pystray._win32', 'PIL']

if tcl_dir and tk_dir:
    datas.append((tcl_dir, 'tcl\\' + Path(tcl_dir).name))
    datas.append((tk_dir, 'tcl\\' + Path(tk_dir).name))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas + [('icon.ico', '.')],
    hiddenimports=hidden,
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
    a.binaries,
    a.datas,
    [],
    name=f'PackingPrint_v{APP_VERSION}_portable',
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
    icon='icon.ico',
)