"""commands/branch.py —— /command:branch / :tag / :reflog 分支标签相关仓库操作。"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from ..dialogs.browserefs import BrowseRefsDlg
from ..dialogs.createbranchdlg import CreateBranchDlg, CreateTagDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("browse")
def browse(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = BrowseRefsDlg(repo, parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"


@register("branch")
def branch(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    start = ctx.cl.value("startrev", "HEAD") if ctx.cl else "HEAD"
    dlg = CreateBranchDlg(repo, start=start, parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"


@register("tag")
def tag(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    start = ctx.cl.value("startrev", "HEAD") if ctx.cl else "HEAD"
    dlg = CreateTagDlg(repo, start=start, parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"


@register("refbrowse")
def refbrowse(ctx: CommandContext):
    """TGit 的 /command:refbrowse —— 浏览分支/标签，同 browse。"""

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
    repo = repo_from_cl(ctx.cl)
    dlg = BrowseRefsDlg(repo, parent=None)
    dlg.exec()
    return "ok"