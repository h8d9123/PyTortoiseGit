"""proc.py —— 子进程启动相关的平台辅助。

GUI 程序（PyInstaller windowed 模式）自身没有控制台，若直接调用控制台
子进程（如 git.exe），Windows 会为每个子进程弹出一个黑色控制台窗口。
统一通过 no_window_kwargs() 传入 CREATE_NO_WINDOW 抑制。
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
import subprocess


def no_window_kwargs() -> dict:
    """返回抑制控制台窗口的 subprocess 关键字参数（仅 Windows 生效）。"""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}
