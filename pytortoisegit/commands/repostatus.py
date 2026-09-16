"""commands/repostatus.py —— /command:repostatus 显示仓库状态对话框。"""

from ..dialogs.changedlg import ChangedDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("repostatus")
def repostatus(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    # /path 必须透传：原版 RepoStatusCommand 会 dlg.m_pathList = pathList，
    # 由 GetStatus() 按路径限定列表；不透传则永远列整个仓库。
    paths = ctx.cl.all_values("path") if ctx.cl else []
    dlg = ChangedDlg(repo, paths=paths or None, parent=None)
    dlg.exec()
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
