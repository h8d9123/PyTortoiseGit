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

"""viewdata.py —— TortoiseGitMerge 的 ViewData（单行数据），逐行翻译 ViewData.h。

一行文本的数据：state(DiffState)/linenumber/EOL/hidestate/marked。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from .eol import EOL  # noqa: F401  (re-export，统一使用 EOL.h 对应的枚举)


class DiffState(Enum):
    """一行文本的差异状态（翻译自 DiffStates.h 枚举）。"""
    Unknown = 0
    Normal = 1
    Removed = 2
    RemovedWhitespace = 3
    Added = 4
    AddedWhitespace = 5
    Whitespace = 6
    WhitespaceDiff = 7
    Empty = 8
    Conflict = 9
    ConflictIgnored = 10
    ConflictAdded = 11
    ConflictEmpty = 12
    MovedFrom = 13
    MovedTo = 14
    IdenticalMovedFrom = 15
    IdenticalMovedTo = 16
    Edited = 17
    Filtered = 18
    ConflictsResolved = 19
    IdenticalRemoved = 20
    IdenticalAdded = 21
    TheirsRemoved = 22
    TheirsAdded = 23
    YoursRemoved = 24
    YoursAdded = 25
    ConflictResolvedEmpty = 26
    FilteredDiff = 27


class HideState(Enum):
    Shown = 0
    Hidden = 1
    Marker = 2


class ViewData:
    """单行数据：state / linenumber / ending / hidestate / marked。"""

    def __init__(self, line: str = "", state: DiffState = DiffState.Unknown,
                 linenumber: int = -1, ending: EOL = EOL.AutoLine,
                 hidestate: HideState = HideState.Shown, marked: bool = False):
        self.line = line
        self.state = state
        self.linenumber = linenumber
        self.ending = ending
        self.hidestate = hidestate
        self.marked = marked

    def clone(self) -> "ViewData":
        return ViewData(self.line, self.state, self.linenumber,
                        self.ending, self.hidestate, self.marked)

    # ---- 状态判断（翻译 BaseView IsStateXxx）----
    @property
    def is_removed(self) -> bool:
        return self.state in (DiffState.Removed, DiffState.MovedFrom,
                              DiffState.TheirsRemoved, DiffState.YoursRemoved,
                              DiffState.IdenticalRemoved)

    @property
    def is_added(self) -> bool:
        return self.state in (DiffState.Added, DiffState.MovedTo,
                              DiffState.TheirsAdded, DiffState.YoursAdded,
                              DiffState.IdenticalAdded, DiffState.ConflictAdded)

    @property
    def is_conflict(self) -> bool:
        return self.state in (DiffState.Conflict, DiffState.ConflictIgnored,
                              DiffState.ConflictAdded, DiffState.ConflictEmpty)

    @property
    def is_empty(self) -> bool:
        return self.state in (DiffState.Empty, DiffState.ConflictEmpty,
                              DiffState.ConflictResolvedEmpty)

    @property
    def is_modified(self) -> bool:
        return self.state == DiffState.Edited

    @property
    def is_diff(self) -> bool:
        return self.state not in (DiffState.Normal, DiffState.Unknown,
                                  DiffState.Empty, DiffState.Filtered,
                                  DiffState.ConflictsResolved)