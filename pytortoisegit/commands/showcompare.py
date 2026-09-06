"""commands/showcompare.py —— /command:showcompare 显示暂存区 vs 工作区比较（再打开 change 对话框）。"""

import os
from PySide6.QtWidgets import QDialog
from ..dialogs.diffdlg import DiffDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("showcompare")
def showcompare(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl else []
    dlg = DiffDlg(repo, rev1="HEAD", rev2="", paths=paths or None, parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"

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
