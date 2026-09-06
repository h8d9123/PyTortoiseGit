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
    ("commit", "提交 (PyTortoiseGit)"),
    ("log", "日志 (PyTortoiseGit)"),
    ("changed", "检查修改 (PyTortoiseGit)"),
    ("sync", "同步 (PyTortoiseGit)"),
    ("browse", "分支与标签 (PyTortoiseGit)"),
    ("settings", "设置 (PyTortoiseGit)"),
)
_FILE_VERBS = (
    ("blame", "标注此文件 (Blame)"),
    ("diff", "与 HEAD 比较…"),
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
    verbs = [v for v, _ in _COMMON_VERBS]
    if target == "*":
        verbs += [v for v, _ in _FILE_VERBS]
    return verbs


def _label_of(verb: str) -> str:
    for v, label in _COMMON_VERBS + _FILE_VERBS:
        if v == verb:
            return label
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
        return "Shell 集成仅支持 Windows。"
    mode = "已安装" if is_installed() else "未安装"
    py = _pythonw()
    app = _app_script()
    return (
        f"右键菜单状态：{mode}\n"
        f"可执行：{py}\n"
        f"入口：{app}\n\n"
        "安装到 文件 / 文件夹 / 文件夹空白处 三类右键菜单。"
        "修改注册表后，通常需要重新打开资源管理器才生效。"
    )