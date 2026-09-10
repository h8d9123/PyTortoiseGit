"""commands/unignore.py —— /command:unignore 取消忽略。"""

from PySide6.QtWidgets import QMessageBox
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("unignore")
def unignore(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl is not None else []
    if not paths:
        return "cancel"
    # 移除工作区 .gitignore 中对应条目（最简实现：删除文件名所在行）
    import os
    gitignore = os.path.join(repo.root, ".gitignore")
    if os.path.isfile(gitignore):
        with open(gitignore, encoding="utf-8") as fh:
            lines = fh.readlines()
        out = [ln for ln in lines if not any(
            ln.strip() == os.path.basename(p.rstrip("/\\")) for p in paths)]
        with open(gitignore, "w", encoding="utf-8") as fh:
            fh.writelines(out)
        repo.runner.run("check-ignore", *paths)  # 刷新
    QMessageBox.information(None, tr("unignore_done", "Unignored (updated .gitignore)"))
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
