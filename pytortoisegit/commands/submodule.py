"""commands/submodule.py —— /command:submodule / subupdate / subadd。"""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ..dialogs.submoduledlg import SubmoduleDlg
from ..git.submodule import GitSubmodule
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("submodule")
def submodule(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = SubmoduleDlg(repo, parent=None)
    dlg.exec()
    return "ok"


@register("subupdate")
def subupdate(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    sub = GitSubmodule(repo)
    ok = sub.update(init=True, recursive=True)
    return "ok" if ok else "failed"


@register("subadd")
def subadd(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    url, ok = QInputDialog.getText(None, tr("submodule_add"), tr("submodule_url"))
    if not ok or not url.strip():
        return "cancel"
    path = url.strip().rstrip("/").rsplit("/", 1)[-1]
    if path.endswith(".git"):
        path = path[:-4]
    sub = GitSubmodule(repo)
    if sub.add(path, url.strip()):
        return "ok"
    QMessageBox.warning(None, tr("error"), tr("submodule_added"))
    return "failed"

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
