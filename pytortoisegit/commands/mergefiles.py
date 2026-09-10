"""commands/mergefiles.py —— 独立文件合并（对齐 TortoiseMerge 的 /base /theirs /mine /merged）。

TortoiseMerge 作为独立工具可用文件路径直接打开比较/合并：
    /base:<file> /theirs:<file> /mine:<file> /merged:<file>
本命令镜像该调用方式：无仓库时按本地文件两栏比较（left=theirs/base，right=mine）。
"""

from __future__ import annotations

from .dispatcher import CommandContext, register


@register("mergefiles")
def mergefiles(ctx: CommandContext):
    cl = ctx.cl

    def val(key: str) -> str:
        if cl is None:
            return ""
        v = cl.value(key)
        return v if isinstance(v, str) else ""

    base = val("base")
    theirs = val("theirs")
    mine = val("mine")
    merged = val("merged")
    if not (base or theirs or mine):
        return "cancel"

    from ..merge.mergefrm import MergeFrm
    # 左 = theirs（或 base），右 = mine；结果写回 merged（若给定）
    left = theirs or base
    right = mine or merged or theirs
    frm = MergeFrm(None, right or "", None, None)
    frm._local_left = left
    frm._local_right = right
    frm.path = right
    frm._load()
    frm.exec()
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
