"""shell_context.py —— 资源管理器右键菜单集成（Windows only）。

用标准库 winreg 写入 HKCU 注册表，为「文件 / 文件夹 / 文件夹空白处」添加
PyTortoiseGit 右键菜单项；无需 pywin32，也不触碰 HKLM（免管理员权限）。

卸载只需删除对应注册表键。
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

import os
import shutil
import sys
from typing import Dict, List, Optional

from .res.strings import tr

WIN32 = sys.platform == "win32"

# (注册表基路径, 变量) —— HKCU\Software\Classes\...
# %1=选中对象路径；%V=文件夹空白处当前目录
_TARGETS = (
    ("*", "%1"),
    ("Directory", "%1"),
    ("Directory\\Background", "%V"),
)

# verb -> (标签, 适用 target 判定)；
# _TARGETS 顺序固定，files 仅心 `*` 上注册
_COMMON_VERBS = (
    ("commit", "shell_commit", "Commit (PyTortoiseGit)"),
    ("log", "shell_log", "Log (PyTortoiseGit)"),
    ("changed", "shell_changed", "Check for Modifications (PyTortoiseGit)"),
    ("sync", "shell_sync", "Sync (PyTortoiseGit)"),
    ("browse", "shell_browse", "Branches and tags (PyTortoiseGit)"),
    ("settings", "shell_settings", "Settings (PyTortoiseGit)"),
)
_FILE_VERBS = (
    ("blame", "shell_blame", "Blame this file"),
    ("diff", "shell_diff", "Compare with HEAD…"),
)

_ROOT = r"Software\Classes"


def _pythonw() -> str:
    """优先 pythonw，避免每次点击弹出黑色控制台窗口。"""
    exe = sys.executable
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.isfile(cand):
        return cand
    found = shutil.which("pythonw")
    return found or exe


def _app_script() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


def _command(verb: str, path_var: str) -> str:
    return f'"{_pythonw()}" "{_app_script()}" /command:{verb} /path:"{path_var}"'


def _verb_names(target: str) -> List[str]:
    """某 target 上注册的 verb 列表。"""
    verbs = [v for v, _k, _d in _COMMON_VERBS]
    if target == "*":
        verbs += [v for v, _k, _d in _FILE_VERBS]
    return verbs


def _label_of(verb: str) -> str:
    for v, key, default in _COMMON_VERBS + _FILE_VERBS:
        if v == verb:
            return tr(key, default)
    return verb


def install() -> int:
    """写入全部右键菜单项，返回写入的项数。非 Windows 返回 0。"""
    if not WIN32:
        return 0
    import winreg
    written = 0
    for target, path_var in _TARGETS:
        base = rf"{_ROOT}\{target}\shell"
        for verb in _verb_names(target):
            key = rf"{base}\PyTortoiseGit.{verb}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _label_of(verb))
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ,
                                  f'"{_pythonw()}",0')
                with winreg.CreateKeyEx(k, "command") as ck:
                    winreg.SetValueEx(ck, "", 0, winreg.REG_SZ,
                                      _command(verb, path_var))
            written += 1
    return written


def uninstall() -> int:
    """删除全部右键菜单项，返回删除的键数量。"""
    if not WIN32:
        return 0
    import winreg
    removed = 0
    for target, _path_var in _TARGETS:
        base = rf"{_ROOT}\{target}\shell"
        for verb in _verb_names(target):
            key = rf"{base}\PyTortoiseGit.{verb}"
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
                removed += 1
            except FileNotFoundError:
                pass
            except OSError:
                # 键下有子键（command）时逐级删
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                     rf"{key}\command")
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
                    removed += 1
                except OSError:
                    pass
    return removed


def is_installed() -> bool:
    if not WIN32:
        return False
    import winreg
    probe = rf"{_ROOT}\Directory\shell\PyTortoiseGit.commit\command"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, probe):
            return True
    except (OSError, FileNotFoundError):
        return False


def status_text() -> str:
    if not WIN32:
        return tr("shell_windows_only", "Shell integration is only supported on Windows.")
    mode = tr("shell_state_installed", "Installed") if is_installed() \
        else tr("shell_state_not_installed", "Not installed")
    py = _pythonw()
    app = _app_script()
    return tr("shell_status",
              "Context menu status: {mode}\nExecutable: {py}\nEntry: {app}\n\n"
              "Registers entries for files / folders / folder background. "
              "After modifying the registry, you usually need to reopen Explorer."
              ).format(mode=mode, py=py, app=app)