"""commands/blame.py —— /command:blame 打开按行标注对话框。"""

from __future__ import annotations

import os

from ..dialogs.blamedlg import BlameDlg
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


def _as_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@register("blame")
def blame(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    filepath = ""
    rev = None
    line = 0
    if ctx.cl is not None:
        paths = [
            p for p in ctx.cl.all_values("path")
            if p and p != repo.root
        ]
        if paths:
            filepath = paths[0]
            if os.path.isfile(filepath):
                filepath = os.path.relpath(filepath, repo.root)
        # 对齐 BlameCommand.cpp：/endrev 是 blame 的终点修订；/line 定位行。
        # 同时兼容直接传 /rev 的调用方（log/repobrowser 等）。
        rev = ctx.cl.value("endrev") or ctx.cl.value("rev") or None
        if rev == "HEAD":
            rev = None
        line = _as_int(ctx.cl.value("line"), 0)
    dlg = BlameDlg(repo, filepath=filepath, rev=rev, line=line, parent=None)
    # BlameDlg 是 QMainWindow（镜像 TortoiseGitBlame 的 SDI 主窗口），
    # 没有 QDialog.exec()，按工具窗口非模态打开。
    _open(dlg)
    return "ok"


def _open(dlg):
    """打开 BlameDlg：优先用 modeless 助手保住引用，回退到 exec/show。"""
    from ..dialogs.modeless import show_modeless
    if hasattr(dlg, "exec"):
        dlg.exec()
    else:
        show_modeless(dlg)

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
