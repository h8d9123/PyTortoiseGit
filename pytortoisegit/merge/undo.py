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

"""undo.py —— TortoiseMerge 的 CUndo（撤销/重做），逐行翻译 Undo.h/.cpp。

viewstate：一次变更的数据（各行文本/状态/EOL/marked/增删、删除/替换的行）。
allviewstate：左/右/底栏快照。CUndo 维护 undo/redo 栈 + 分组(Grouping)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .viewdata import DiffState, EOL, ViewData


def _clone_list(data: Optional[list]) -> Optional[List[ViewData]]:
    if data is None:
        return None
    return [vd.clone() for vd in data]


def _replace_list(target: list, snap: Optional[list]) -> None:
    if snap is None:
        return
    target[:] = [vd.clone() for vd in snap]


@dataclass
class ViewState:
    """一次变更的快照（翻译 Undo.h viewstate）。"""
    difflines: Dict[int, str] = field(default_factory=dict)
    linestates: Dict[int, DiffState] = field(default_factory=dict)
    linelines: Dict[int, int] = field(default_factory=dict)
    linesEOL: Dict[int, EOL] = field(default_factory=dict)
    markedlines: Dict[int, bool] = field(default_factory=dict)
    addedlines: List[int] = field(default_factory=list)
    removedlines: Dict[int, ViewData] = field(default_factory=dict)
    replaceslines: Dict[int, ViewData] = field(default_factory=dict)
    modifies: bool = False

    def is_empty(self) -> bool:
        return not (self.difflines or self.linestates or self.linelines
                    or self.linesEOL or self.markedlines or self.addedlines
                    or self.removedlines or self.replaceslines)

    @classmethod
    def from_view(cls, view, view_lines: Optional[list] = None) -> "ViewState":
        """从 BaseView 对齐的行构建快照（记录所有变更行）。"""
        data = view_lines if view_lines is not None else getattr(view, "view_data", [])
        st = cls()
        for i, vd in enumerate(data if data else []):
            st.difflines[i] = vd.line
            st.linestates[i] = vd.state
            st.markedlines[i] = vd.marked
        st.modifies = True
        return st

    def restore(self, target_data: list) -> None:
        """把快照写回 target_data（对齐行的 ViewData 列表）。"""
        for i, vd in enumerate(target_data):
            if i >= len(self.difflines):
                break
            vd.line = self.difflines[i]
            vd.state = self.linestates.get(i, vd.state)
            vd.marked = self.markedlines.get(i, vd.marked)


@dataclass
class AllViewState:
    left: List[ViewData] = field(default_factory=list)
    right: List[ViewData] = field(default_factory=list)
    bottom: Optional[List[ViewData]] = None

    def is_empty(self) -> bool:
        return not self.left and not self.right and not self.bottom

    def snapshot(self, left_data: list, right_data: list,
                 bottom_data: Optional[list] = None) -> "AllViewState":
        self.left = _clone_list(left_data) or []
        self.right = _clone_list(right_data) or []
        self.bottom = _clone_list(bottom_data)
        return self

    def restore_into(self, left_data: list, right_data: list,
                     bottom_data: Optional[list] = None) -> None:
        _replace_list(left_data, self.left)
        _replace_list(right_data, self.right)
        if bottom_data is not None:
            _replace_list(bottom_data, self.bottom)


class CUndo:
    """撤销/重做管理器（翻译 CUndo）。"""

    def __init__(self):
        self._undo: List[AllViewState] = []
        self._redo: List[AllViewState] = []
        self._group_count = 0
        self._groups: List[bool] = []
        self._original_left = 0
        self._original_right = 0
        self._original_bottom = 0

    # ---- Undo.h: CanUndo/CanRedo ----
    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    # ---- Grouping（BeginGrouping/EndGrouping/IsGrouping）----
    def is_grouping(self) -> bool:
        return self._group_count > 0

    def is_redo_grouping(self) -> bool:
        return False

    def mark_as_original_state(self, left: bool = True, right: bool = True,
                               bottom: bool = True):
        """对齐 MarkAsOriginalState：记录哪些视图已处于原始状态。"""
        self._original_left = 1 if left else 0
        self._original_right = 1 if right else 0
        self._original_bottom = 1 if bottom else 0

    def mark_all_as_original_state(self):
        self.mark_as_original_state(True, True, True)

    # ---- Grouping（BeginGrouping/EndGrouping）----
    def begin_grouping(self):
        if self._group_count == 0:
            self._groups.append(True)
        self._group_count += 1

    def end_grouping(self):
        self._group_count -= 1
        if self._group_count == 0:
            self._groups.append(False)

    # ---- AddState ----
    def add_state(self, state: AllViewState):
        self._redo.clear()
        self._undo.append(state)

    def clear(self):
        self._undo.clear()
        self._redo.clear()

    def _snap(self, left_data: list, right_data: list,
              bottom_data: Optional[list] = None) -> AllViewState:
        return AllViewState().snapshot(left_data, right_data, bottom_data)

    def undo(self, left_data: list, right_data: list,
             bottom_data: Optional[list] = None) -> bool:
        if not self._undo:
            return False
        state = self._undo.pop()
        self._redo.append(self._snap(left_data, right_data, bottom_data))
        state.restore_into(left_data, right_data, bottom_data)
        return True

    def redo(self, left_data: list, right_data: list,
             bottom_data: Optional[list] = None) -> bool:
        if not self._redo:
            return False
        state = self._redo.pop()
        self._undo.append(self._snap(left_data, right_data, bottom_data))
        state.restore_into(left_data, right_data, bottom_data)
        return True


# 单例（翻译 CUndo::GetInstance）
_UNDO = CUndo()


def get_undo() -> CUndo:
    return _UNDO
