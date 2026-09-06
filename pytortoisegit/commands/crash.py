"""commands/crash.py —— /command:crash 触发调试崩溃（模拟异常）。"""

from PySide6.QtWidgets import QMessageBox
from ..res.strings import tr
from .dispatcher import CommandContext, register


@register("crash")
def crash(ctx: CommandContext):
    QMessageBox.information(None, tr("crash_title", "Crash"),
                            tr("crash_text", "crash 调试命令：已捕获为信息框（未真正崩溃）。"))
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
