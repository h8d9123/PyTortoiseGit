"""commands/remove.py —— /command:remove 从 git 移除文件（git rm）。"""

from PySide6.QtWidgets import QMessageBox
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("remove")
def remove(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl else []
    if not paths:
        return "cancel"
    resp = QMessageBox.question(None, tr("remove_title", "Remove"),
                                tr("remove_confirm", "Remove selected files from git?"),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if resp != QMessageBox.StandardButton.Yes:
        return "cancel"
    r = repo.runner.run("rm", "--", *paths)
    return "ok" if r.returncode == 0 else "failed"

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
