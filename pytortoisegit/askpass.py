"""askpass.py —— Git 认证 Askpass 桥接。

当 git 需要 username/password 时，通过 GIT_ASKPASS 调用本模块，
弹出 TortoiseGit 风格的认证对话框（credentialdlg）。
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

import sys
import os

# git 通过 GIT_ASKPASS 调用：`askpass <prompt>`
# 本模块以独立进程运行，须在无 Qt 事件循环下也能工作。


def main(argv) -> int:
    prompt = " ".join(argv[1:])
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from .dialogs.credentialdlg import SimplePromptDlg
    dlg = SimplePromptDlg(realm=prompt, parent=None)
    if dlg.exec():
        # git askpass 期望把答案写回 stdout；username/password 分开调用
        # 由 GIT_ASKPASS 两次调用：一次用户名一次密码
        if "username" in prompt.lower():
            sys.stdout.write(dlg.username)
        else:
            sys.stdout.write(dlg.password)
        return 0
    return 1


def setup_askpass(env: dict, root: str | None = None) -> dict:
    """把 GIT_ASKPASS / SSH_ASKPASS 指向本模块，并默认开启交互。"""
    import subprocess
    # 用当前 python 执行本模块
    this = os.path.abspath(__file__)
    py = sys.executable
    env = env.copy()
    env["GIT_ASKPASS"] = f"{py} {this}"
    env["SSH_ASKPASS"] = f"{py} {this}"
    env.setdefault("DISPLAY", "localhost:0.0")
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


if __name__ == "__main__":
    sys.exit(main(sys.argv))