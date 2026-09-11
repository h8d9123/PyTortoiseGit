# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：构建 PyTortoiseGit Windows 桌面版。

用法：
    pyinstaller packaging/PyTortoiseGit.spec --noconfirm
产物：dist/PyTortoiseGit/PyTortoiseGit.exe（onedir 模式）。
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("PySide6")

# 加入 TortoiseGit 图标资源
_icons_dir = Path("pytortoisegit/res/icons")
if _icons_dir.is_dir():
    datas += [(_path, "pytortoisegit/res/icons")
              for _path in sorted(str(p) for p in _icons_dir.glob("*.ico"))]

# 加入原版 TortoiseGitMerge Ribbon 位图（ribbon/*.bmp）
_ribbon_dir = Path("pytortoisegit/res/ribbon")
if _ribbon_dir.is_dir():
    datas += [(_path, "pytortoisegit/res/ribbon")
              for _path in sorted(str(p) for p in _ribbon_dir.glob("*.bmp"))]

# 加入进度对话框顶部动画（animation/*.gif，由原版 download.avi 转换）
_anim_dir = Path("pytortoisegit/res/animation")
if _anim_dir.is_dir():
    datas += [(_path, "pytortoisegit/res/animation")
              for _path in sorted(str(p) for p in _anim_dir.glob("*.gif"))]

# 加入许可与归属文件
for _lic in ("LICENSE", "NOTICE"):
    if Path(_lic).is_file():
        datas += [(str(Path(_lic).resolve()), ".")]

# 自动发现所有命令模块与对话框模块
_cmd_mods = sorted(
    "pytortoisegit.commands." + p.stem
    for p in Path("pytortoisegit/commands").glob("*.py")
    if not p.stem.startswith("__"))
_dlg_mods = sorted(
    "pytortoisegit.dialogs." + p.stem
    for p in Path("pytortoisegit/dialogs").glob("*.py")
    if not p.stem.startswith("__"))
_merge_mods = sorted(
    "pytortoisegit.merge." + p.stem
    for p in Path("pytortoisegit/merge").glob("*.py")
    if not p.stem.startswith("__"))
hiddenimports += [m for m in _cmd_mods + _dlg_mods + _merge_mods if not m.endswith(".tests")]

# attention: 右键菜单入口使用 pythonw 解释器运行 app.py；
# 打包后该入口由资源管理器调用，仍由本程序作为编译器环境提供。
_CMD_MODULES = [
    "pytortoisegit.commands.about",
    "pytortoisegit.commands.commit",
    "pytortoisegit.commands.log",
    "pytortoisegit.commands.diff",
    "pytortoisegit.commands.blame",
    "pytortoisegit.commands.changed",
    "pytortoisegit.commands.sync",
    "pytortoisegit.commands.settings",
    "pytortoisegit.commands.clone",
    "pytortoisegit.commands.branch",
    "pytortoisegit.commands.reflog",
    "pytortoisegit.commands.shell",
    "pytortoisegit.dialogs",
]

a = Analysis(
    ["pytortoisegit/app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + _CMD_MODULES,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyTortoiseGit",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PyTortoiseGit",
)