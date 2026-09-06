"""commands/commit.py —— /command:commit 打开提交对话框。"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from ..dialogs.commitdlg import CommitDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("commit")
def commit(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = CommitDlg(repo, parent=None)
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
