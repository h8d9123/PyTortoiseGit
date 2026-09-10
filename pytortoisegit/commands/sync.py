"""commands/sync.py —— /command:sync / :fetch / :pull / :push 打开同步对话框。"""

from __future__ import annotations

from ..dialogs.sync import SyncDlg
from ._util import repo_from_cl
from ..res.strings import tr
from .dispatcher import CommandContext, register


@register("sync")
def sync(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = SyncDlg(repo, parent=None)
    dlg.exec()
    return "ok"


@register("fetch")
def fetch(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = SyncDlg(repo, parent=None)
    dlg.setWindowTitle(f"{repo.name} — {tr('sync_fetch', 'Fetch')}")
    dlg.exec()
    return "ok"


@register("pull")
def pull(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = SyncDlg(repo, parent=None)
    dlg.setWindowTitle(f"{repo.name} — {tr('sync_pull', 'Pull')}")
    dlg.exec()
    return "ok"


@register("push")
def push(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = SyncDlg(repo, parent=None)
    dlg.setWindowTitle(f"{repo.name} — {tr('sync_push', 'Push')}")
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
