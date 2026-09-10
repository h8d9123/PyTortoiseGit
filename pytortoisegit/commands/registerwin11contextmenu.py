"""commands/registerwin11contextmenu.py —— /command:registerwin11contextmenu 安装 Win11 右键菜单。"""

from PySide6.QtWidgets import QMessageBox
from ..res.strings import tr
from ..shell_context import install as _install_shell
from .dispatcher import CommandContext, register


@register("registerwin11contextmenu")
def registerwin11contextmenu(ctx: CommandContext):
    try:
        _install_shell()
        QMessageBox.information(None, tr("ctx_title", "Context menu"),
                                tr("ctx_installed", "Windows 11 context menu installed."))
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(None, tr("error"), str(exc))
    return "ok"


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
