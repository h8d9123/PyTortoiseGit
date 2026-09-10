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

"""diffcolors.py —— TortoiseGitMerge 的 DiffColors（配色），逐行翻译 DiffColors.h。

每行 diff 状态(DiffState) 对应一组前景/背景色，含浅色/深色主题。
对照 TortoiseGit 源码 src/TortoiseMerge/DiffColors.h：
  * DIFFSTATE_REMOVED_BG   = RGB(255,200,100)  橙色（删除/移出）
  * DIFFSTATE_ADDED_BG     = RGB(255,255,0)    黄色（新增/移入）
  * DIFFSTATE_EDITED_BG    = RGB(220,220,255)  浅蓝（修改）
  * DIFFSTATE_CONFLICTED_BG= RGB(255,100,100)  红色（冲突）
  * DIFFSTATE_EMPTY_BG     = RGB(200,200,200)  灰色（空行）
  * DIFFSTATE_FILTERED_BG  = RGB(220,255,220)  浅绿（被过滤）
"""

from __future__ import annotations

from typing import Dict
from PySide6.QtGui import QColor

from .viewdata import DiffState


class DiffColors:
    """DiffColors：按 DiffState 返回前景/背景色（浅色 / 深色）。"""

    # 浅色主题背景（翻译自 DiffColors.h 默认值）
    _LIGHT_BG: Dict[DiffState, QColor] = {
        DiffState.Normal: QColor(255, 255, 255),
        DiffState.Removed: QColor(255, 200, 100),
        DiffState.RemovedWhitespace: QColor(255, 255, 255),
        DiffState.Added: QColor(255, 255, 0),
        DiffState.AddedWhitespace: QColor(255, 255, 255),
        DiffState.Whitespace: QColor(255, 255, 255),
        DiffState.WhitespaceDiff: QColor(255, 255, 255),
        DiffState.Empty: QColor(200, 200, 200),
        DiffState.Conflict: QColor(255, 100, 100),
        DiffState.ConflictIgnored: QColor(255, 100, 100),
        DiffState.ConflictAdded: QColor(255, 100, 100),
        DiffState.ConflictEmpty: QColor(255, 100, 100),
        DiffState.MovedFrom: QColor(255, 200, 100),
        DiffState.MovedTo: QColor(255, 255, 0),
        DiffState.IdenticalMovedFrom: QColor(255, 255, 255),
        DiffState.IdenticalMovedTo: QColor(255, 255, 255),
        DiffState.Edited: QColor(220, 220, 255),
        DiffState.Filtered: QColor(220, 255, 220),
        DiffState.IdenticalRemoved: QColor(255, 200, 100),
        DiffState.IdenticalAdded: QColor(255, 255, 0),
        DiffState.TheirsRemoved: QColor(255, 200, 100),
        DiffState.TheirsAdded: QColor(255, 255, 0),
        DiffState.YoursRemoved: QColor(255, 200, 100),
        DiffState.YoursAdded: QColor(255, 255, 0),
        DiffState.ConflictResolvedEmpty: QColor(200, 200, 200),
        DiffState.FilteredDiff: QColor(220, 255, 220),
        DiffState.ConflictsResolved: QColor(200, 255, 200),
    }

    # 深色主题背景（翻译自 DiffColors.h dark 默认值）
    _DARK_BG: Dict[DiffState, QColor] = {
        DiffState.Normal: QColor(32, 32, 32),
        DiffState.Removed: QColor(83, 66, 33),
        DiffState.RemovedWhitespace: QColor(32, 32, 32),
        DiffState.Added: QColor(83, 83, 0),
        DiffState.AddedWhitespace: QColor(32, 32, 32),
        DiffState.Whitespace: QColor(32, 32, 32),
        DiffState.WhitespaceDiff: QColor(32, 32, 32),
        DiffState.Empty: QColor(66, 66, 66),
        DiffState.Conflict: QColor(83, 33, 33),
        DiffState.ConflictIgnored: QColor(83, 33, 33),
        DiffState.ConflictAdded: QColor(83, 33, 33),
        DiffState.ConflictEmpty: QColor(83, 33, 33),
        DiffState.MovedFrom: QColor(83, 66, 33),
        DiffState.MovedTo: QColor(83, 83, 0),
        DiffState.IdenticalMovedFrom: QColor(32, 32, 32),
        DiffState.IdenticalMovedTo: QColor(32, 32, 32),
        DiffState.Edited: QColor(80, 80, 103),
        DiffState.Filtered: QColor(73, 83, 73),
        DiffState.IdenticalRemoved: QColor(83, 66, 33),
        DiffState.IdenticalAdded: QColor(83, 83, 0),
        DiffState.TheirsRemoved: QColor(83, 66, 33),
        DiffState.TheirsAdded: QColor(83, 83, 0),
        DiffState.YoursRemoved: QColor(83, 66, 33),
        DiffState.YoursAdded: QColor(83, 83, 0),
        DiffState.ConflictResolvedEmpty: QColor(66, 66, 66),
        DiffState.FilteredDiff: QColor(73, 83, 73),
        DiffState.ConflictsResolved: QColor(66, 83, 66),
    }

    def __init__(self, dark: bool = False):
        self.dark = dark

    def text_color(self, state: DiffState) -> QColor:
        return QColor(0xDD, 0xDD, 0xDD) if self.dark else QColor(0, 0, 0)

    def back_color(self, state: DiffState) -> QColor | None:
        table = self._DARK_BG if self.dark else self._LIGHT_BG
        return table.get(state)

    def inline_added_color(self) -> QColor:
        return QColor(120, 120, 50) if self.dark else QColor(255, 255, 150)

    def inline_removed_color(self) -> QColor:
        return QColor(100, 40, 40) if self.dark else QColor(200, 100, 100)