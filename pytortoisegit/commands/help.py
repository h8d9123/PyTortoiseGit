"""commands/help.py —— /command:help 帮助对话框。"""

from PySide6.QtWidgets import QMessageBox
from ..res.strings import format_string, tr
from .dispatcher import CommandContext, register


@register("help")
def help(ctx: CommandContext):
    from ..commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = ", ".join(available_commands())
    QMessageBox.information(
        None, tr("help_title", "Help"),
        format_string(tr("help_text", "用法：app.py /command:&lt;名称&gt; [/path:&lt;路径&gt;]\\n\\n可用命令：\\n{cmds}"),
                      cmds=cmds))
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
