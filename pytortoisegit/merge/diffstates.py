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

"""diffstates.py —— TortoiseMerge 的 DiffStates（行状态枚举，独立导出）。

为对齐 TortoiseMerge 的 DiffStates.h，把 DiffState/HideState 单独导出，
供其它模块引用。
"""

from __future__ import annotations

from .viewdata import DiffState, HideState, EOL

__all__ = ["DiffState", "HideState", "EOL"]