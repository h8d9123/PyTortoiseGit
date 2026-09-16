"""commands/changed.py —— /command:check_modifications / :changed 检查修改。"""

from __future__ import annotations

from ..dialogs.changedlg import ChangedDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


def _changed(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    # 与 repostatus 一致：把 /path 透传给对话框，由它按路径限定列表
    paths = ctx.cl.all_values("path") if ctx.cl else []
    dlg = ChangedDlg(repo, paths=paths or None, parent=None)
    dlg.exec()
    return "ok"


@register("check_modifications")
def check_modifications(ctx: CommandContext):
    return _changed(ctx)


@register("changed")
def changed(ctx: CommandContext):
    return _changed(ctx)

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
