"""commands/_util.py —— 命令公共工具：从命令行上下文解析仓库。"""

from __future__ import annotations

from ..cmdline import CommandLine
from ..git.repo import NotARepositoryError, Repository


def repo_from_cl(cl: CommandLine | None) -> Repository:
    """根据 /path 打开仓库；无 /path 或不是仓库时报错。"""

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
    if cl is None or not cl.path:
        raise NotARepositoryError("(未提供 /path)")
    return Repository.open(cl.path)


def repo_from_cl_optional(cl: CommandLine | None) -> Repository | None:
    """尽量解析仓库，用于设置等可无仓库的命令。"""
    if cl is not None and cl.path:
        try:
            return Repository.open(cl.path)
        except NotARepositoryError:
            return None
    return None