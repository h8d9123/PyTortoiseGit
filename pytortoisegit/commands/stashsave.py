"""commands/stashsave.py —— /command:stashsave 暂存当前改动。"""

from ..dialogs.stashdlg import StashDlg
from ..dialogs.progress import ProgressDialog
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("stashsave")
def stashsave(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    dlg = StashDlg(repo, parent=None)
    if dlg.exec() != StashDlg.DialogCode.Accepted:
        return "cancel"
    args = ["stash", "push"]
    if dlg.include_untracked:
        args.append("--include-untracked")
    if dlg.use_all:
        args.append("--all")
    if dlg.message:
        args += ["-m", dlg.message]
    prog = ProgressDialog(title=tr("progress", "Progress"), parent=None)
    prog.set_label(" ".join(args))
    def _bg():
        r = repo.runner.run(*args)
        if r.stdout: prog.log_async(r.stdout)
        if r.stderr: prog.log_async(r.stderr)
        return r.returncode == 0
    prog.run(_bg)
    prog.exec()
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
