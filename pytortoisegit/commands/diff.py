"""commands/diff.py —— /command:diff / /command:review 打开 diff 对话框。

镜像 DiffCommand.cpp：
  * path 是目录（或整仓）→ CChangedDlg（Working Tree 列表）
  * path 是单文件 → 统一 diff（showcompare /unified）
"""

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

from __future__ import annotations

import os

from PySide6.QtWidgets import QDialog

from ..dialogs.changedlg import ChangedDlg
from ..dialogs.diffdlg import DiffDlg
from ..merge.mergefrm import MergeFrm
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


def _diff(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl else []
    rev1 = ctx.cl.value("rev1", "HEAD") if ctx.cl else "HEAD"
    rev2 = ctx.cl.value("rev2") if ctx.cl else None

    if paths and all(os.path.isfile(p) for p in paths):
        # 单文件比较 → 打开 TortoiseGitMerge 风格并排视图
        rel = os.path.relpath(paths[0], repo.root)
        ref2 = rev2 if rev2 else None
        base = (rev1 + "^") if rev1 and rev1 not in ("HEAD", None) else None
        frm = MergeFrm(repo, rel.replace("\\", "/"), base or rev1, ref2,
                       parent=None)
        frm.show()
        return "ok"
    else:
        dlg = ChangedDlg(repo, paths=paths or None, parent=None)
        dlg.exec()
        return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"


@register("diff")
def diff(ctx: CommandContext):
    return _diff(ctx)


@register("review")
def review(ctx: CommandContext):
    return _diff(ctx)


@register("prevdiff")
def prevdiff(ctx: CommandContext):
    """TGit 的 /command:prevdiff —— 与上一提交比较。"""
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl else []
    dlg = DiffDlg(repo, rev1="HEAD~1", rev2="HEAD", paths=paths or None,
                  parent=None)
    dlg.exec()
    return "ok" if dlg.result() == QDialog.DialogCode.Accepted else "cancel"