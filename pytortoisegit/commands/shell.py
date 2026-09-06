"""commands/shell.py —— /command:shell 右键菜单安装/卸载对话框。"""

from __future__ import annotations

import sys

from ..dialogs.shelldlg import ShellDlg
from .dispatcher import CommandContext, register


@register("shell")
def shell(ctx: CommandContext):
    dlg = ShellDlg(parent=None)
    dlg.exec()
    return "ok"


@register("shell_install")
def shell_install(ctx: CommandContext):
    from ..shell_context import install
    n = install()
    if ctx.qapp is None or sys.platform != "win32":
        return f"{n}"
    return None


@register("shell_uninstall")
def shell_uninstall(ctx: CommandContext):
    from ..shell_context import uninstall
    n = uninstall()
    if ctx.qapp is None or sys.platform != "win32":
        return f"{n}"
    return None

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
