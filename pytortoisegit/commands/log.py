"""commands/log.py —— /command:log / /command:revision 打开日志对话框。"""

from __future__ import annotations

import os

from PySide6.QtWidgets import QDialog

from ..dialogs.logdlg import LogDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


def _log(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    startrev = ctx.cl.value("startrev") if ctx.cl else None
    pathspec = None
    if ctx.cl is not None and repo is not None:
        rel = []
        for p in ctx.cl.all_values("path"):
            if p and os.path.abspath(p) != os.path.abspath(repo.root):
                rel.append(os.path.relpath(p, repo.root).replace("\\", "/"))
        if rel:
            pathspec = rel[0]
    dlg = LogDlg(repo, pathspec=pathspec, rev=startrev or None, parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"


@register("log")
def log(ctx: CommandContext):
    return _log(ctx)


@register("revision")
def revision(ctx: CommandContext):
    return _log(ctx)

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
