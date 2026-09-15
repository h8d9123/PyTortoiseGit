# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：构建 PyTortoiseGit Windows 桌面版。

用法：
    pyinstaller packaging/PyTortoiseGit.spec --noconfirm
产物：dist/PyTortoiseGit/PyTortoiseGit.exe（onedir 模式）。
"""

from pathlib import Path

# 所有相对路径一律基于仓库根目录解析，避免受调用时工作目录 / spec 目录影响。
ROOT = Path(SPECPATH).resolve().parent

# 只用 QtCore/QtGui/QtWidgets，交给 PyInstaller 的 PySide6 钩子按导入自动收集，
# 不再 collect_all("PySide6")，避免拖入 WebEngine(~190MB)/Quick/3D/Designer 等。
datas, binaries, hiddenimports = [], [], []

# 内置资源数据文件（保留目录结构）：
#   res/rc_dialogs.json  —— ui/rc.py 运行时按路径加载的对话框模板
#   res/icons/*.ico      —— 命令/工具栏图标
#   res/ribbon/*.bmp     —— TortoiseGitMerge Ribbon 位图
#   res/animation/*.gif  —— 进度对话框顶部动画
#   res/overlay/*.ico    —— 版本控制状态覆盖图标
# 排除 .py/.pyc 源码与 __pycache__（模块本身由 PyInstaller 分析收集）。
_res_dir = ROOT / "pytortoisegit/res"
for _p in sorted(_res_dir.rglob("*")):
    if not _p.is_file() or _p.suffix in (".py", ".pyc"):
        continue
    if "__pycache__" in _p.parts:
        continue
    datas.append((str(_p), _p.relative_to(ROOT).parent.as_posix()))

# 加入许可与归属文件
for _lic in ("LICENSE", "NOTICE"):
    if (ROOT / _lic).is_file():
        datas += [(str(ROOT / _lic), ".")]

# 构建期守护：必需资源缺失立即失败（fail fast），避免到运行时才报
# FileNotFoundError（例如曾漏打包 res/rc_dialogs.json）。
import posixpath as _posixpath

_DATAS_REL = {
    _posixpath.normpath(_posixpath.join(d[1].replace("\\", "/"), Path(d[0]).name))
    for d in datas
}
for _req in ("pytortoisegit/res/rc_dialogs.json", "LICENSE", "NOTICE"):
    if _req not in _DATAS_REL:
        raise SystemExit(f"[spec] 缺少必需资源：{_req}（检查打包清单）")
if not any(p.startswith("pytortoisegit/res/icons/") for p in _DATAS_REL):
    raise SystemExit("[spec] 未打包任何图标资源：pytortoisegit/res/icons/*")

# 自动发现所有命令模块与对话框模块
_cmd_mods = sorted(
    "pytortoisegit.commands." + p.stem
    for p in (ROOT / "pytortoisegit/commands").glob("*.py")
    if not p.stem.startswith("__"))
_dlg_mods = sorted(
    "pytortoisegit.dialogs." + p.stem
    for p in (ROOT / "pytortoisegit/dialogs").glob("*.py")
    if not p.stem.startswith("__"))
_merge_mods = sorted(
    "pytortoisegit.merge." + p.stem
    for p in (ROOT / "pytortoisegit/merge").glob("*.py")
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

# 未使用的 Qt 模块，显式排除以避免被间接依赖带入（WebEngine/Quick/3D 等体积巨大）。
_EXCLUDES = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtGraphs", "PySide6.QtHelp",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
    "tkinter",
]

a = Analysis(
    [str(ROOT / "pytortoisegit/app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + _CMD_MODULES,
    hookspath=[],
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)
# ---- 精简 Qt 依赖 ----
# PyInstaller 的 Qt 钩子会按插件连带收集 DLL：虚拟键盘插件 -> Quick/Qml 全家桶；
# qpdf/qsvg -> Qt6Pdf/Qt6Svg；tls/networkinformation -> Qt6Network。本程序只用
# QtCore/QtGui/QtWidgets，这些都用不到，统一剔除（含软件 OpenGL 兜底 DLL）。
_DROP_BINARIES = {
    "opengl32sw.dll",
    "qt6quick.dll", "qt6quick3d.dll", "qt6quick3dutils.dll",
    "qt6quick3druntimerender.dll", "qt6quick3dparticles.dll",
    "qt6qml.dll", "qt6qmlcompiler.dll", "qt6qmlmeta.dll", "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll", "qt6qmlnet.dll", "qt6qmlxmllistmodel.dll",
    "qt6virtualkeyboard.dll", "qt6virtualkeyboardqml.dll",
    "qt6pdf.dll", "qt6svg.dll", "qt6network.dll", "qt6opengl.dll",
    "qt6openglwidgets.dll", "qt6shadertools.dll",
    "qtnetwork.pyd", "qtpdf.pyd", "qtsvg.pyd", "qtsvgwidgets.pyd",
    "qtqml.pyd", "qtquick.pyd", "qtquick3d.pyd", "qtvirtualkeyboard.pyd",
    "qmlls.exe",
}
_DROP_PLUGIN_PARTS = (
    "/platforminputcontexts/", "/virtualkeyboard/", "/qmltooling/",
    "/imageformats/qpdf", "/imageformats/qsvg", "/iconengines/qsvgicon",
    "/tls/", "/networkinformation/", "/generic/qtuiotouchplugin",
    "/platforms/qdirect2d",
)


def _keep_binary(entry) -> bool:
    low = entry[0].replace("\\", "/").lower()
    if low.rsplit("/", 1)[-1] in _DROP_BINARIES:
        return False
    return not any(part in low for part in _DROP_PLUGIN_PARTS)


a.binaries = [e for e in a.binaries if _keep_binary(e)]
# Qt 自带翻译（~6MB）不使用：本程序界面文案自带中英字符串表。
a.datas = [e for e in a.datas
           if "/translations/" not in e[0].replace("\\", "/").lower()]

# 构建期守护：确保瘦身后核心 Qt 运行库仍在（防止误删）。
_BIN_NAMES = {Path(e[0].replace("\\", "/")).name.lower() for e in a.binaries}
for _need in ("qt6core.dll", "qt6gui.dll", "qt6widgets.dll"):
    if _need not in _BIN_NAMES:
        raise SystemExit(f"[spec] 缺少必需运行库：{_need}（检查 _DROP_BINARIES）")

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