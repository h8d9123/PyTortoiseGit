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

"""commands/merge3.py —— /command:merge3（三栏合并冲突解决）。

对齐 TortoiseMerge 的三栏合并：左=theirs、右=ours、底=合并输出。
"""

from __future__ import annotations

from ..merge.mergefrm import MergeFrm
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("merge3")
def merge3(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    our = ctx.cl.value("rev2", "HEAD") if ctx.cl else "HEAD"
    their = ctx.cl.value("rev1") if ctx.cl else None
    path = ctx.cl.value("path") if ctx.cl and ctx.cl.value("path") else ""
    if not path:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "merge3", "需要 /path:<文件>")
        return "cancel"
    frm = MergeFrm(repo, path, their or "HEAD", our, three_way=True)
    frm.exec()
    return "ok"