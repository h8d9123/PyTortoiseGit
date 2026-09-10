"""cli.py —— 命令行入口逻辑（镜像 TortoiseProc.exe 主函数）。"""

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

from . import __appname__, __version__
from .cmdline import parse

def _print_help():
    from .res.strings import tr
    print(f"{__appname__} {__version__}")
    print()
    print(tr("cli_usage", "Usage: app.py /command:<name> [/path:<path>] [/msg:<message>] ..."))
    print("      app.py /help")
    print()
    print(tr("cli_commands", "Available commands: about  clone  commit  diff  log  blame  browse  reflog"))
    print("          branch tag  settings  sync  pull  push  fetch  shell")
    print("          stash  merge  rebase  submodule (subadd/subupdate)")
    print("          check_modifications (changed)")
    print()
    print(tr("cli_examples", "Examples:"))
    print("  python pytortoisegit/app.py /command:log /path:\"D:\\repo\"")
    print("  python pytortoisegit/app.py /command:clone /url:https://github.com/user/repo.git")

def main(argv: list | None = None) -> int:
    from .res.strings import format_string, tr
    from .commands.dispatcher import CommandContext, UnknownCommandError, dispatch

    argv = list(sys.argv[1:] if argv is None else argv)
    if any(t in argv for t in ("/help", "-help", "--help", "/?")):
        _print_help()
        return 0

    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])
    qapp.setApplicationDisplayName(tr("app_name"))
    qapp.setApplicationVersion(__version__)
    try:
        from .res import icons
        qapp.setWindowIcon(icons.app_icon())
    except Exception:
        pass

    from .utils.logging_utils import get_logger, install_excepthooks
    install_excepthooks(show_dialog=True)
    get_logger().info("startup command: %s", " ".join(argv) if argv else "(no args -> main menu)")

    cl = parse(argv)

    verb = cl.verb
    if not verb:
        # 无命令行参数 -> 打开主菜单 GUI（替代纯文本帮助）
        from .singleinstance import acquire
        if not acquire("menu"):
            return 0
        from .dialogs.mainmenu import MainMenuDlg
        dlg = MainMenuDlg(repo_path="", parent=None)
        dlg.exec_loop()
        return 0

    ctx = CommandContext(qapp=qapp, cl=cl)
    try:
        dispatch(verb, ctx)
    except UnknownCommandError as exc:
        print(format_string(tr("unknown_command"), command=exc.name))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(format_string(tr("command_failed"), name=verb, message=exc))
        return 1
    return 0

