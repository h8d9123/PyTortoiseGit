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

"""baseview.py —— TortoiseGitMerge 的 BaseView / LeftView / RightView（并排视图）。

用 PySide6 QPlainTextEdit 复刻 CBaseView 的查看/渲染能力：
  * 按 ViewData.state 逐行着色的 diff 视图
  * 同步滚动、行号、差异跳转、LineDiffBar 联动
  * 只读查看（Compare 模式）
功能流程对齐 TortoiseGitMerge（src/TortoiseMerge/BaseView.cpp）：
  * ScrollToLine / GoToLine / ScrollAllToLine（同步）
  * ShowDiffLines、HasNext/PrevDiff、HasNext/PrevConflict
  * RecalcVertScrollBar、BuildAllScreen2ViewVector（行对齐）
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QAbstractScrollArea, QPlainTextEdit, QScrollBar,
                               QVBoxLayout, QWidget)

from .diffcolors import DiffColors
from .viewdata import DiffState, EOL, HideState, ViewData


class BaseView(QPlainTextEdit):
    """一个并排 diff 视图（对应 CBaseView）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view_data: List[ViewData] = []
        self.colors = DiffColors()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMinimumWidth(360)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.setFont(mono)
        self._line_height = QFontMetrics(mono).height()
        # 行号边距
        self.setViewportMargins(60, 0, 0, 0)
        self._first_view_line = 0
        self._on_line_clicked = None

    # ---- 数据 ----
    def set_view_data(self, data: List[ViewData], colors: DiffColors | None = None):
        self.view_data = data
        if colors is not None:
            self.colors = colors
        self._rebuild()

    def set_writable(self, writable: bool):
        """翻译 SetWritable：合并输出视图可编辑。"""
        self.setReadOnly(not writable)

    def get_line_count(self) -> int:
        return len(self.view_data)

    # ---- 渲染 ----
    def _rebuild(self):
        self.clear()
        doc = self.document()
        for i, vd in enumerate(self.view_data):
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            text = vd.line if not vd.is_empty else ""
            cursor.insertText(text)
            bg = self.colors.back_color(vd.state)
            if bg is not None:
                fmt = QTextCharFormat()
                fmt.setBackground(bg)
                block = doc.findBlockByNumber(doc.blockCount() - 1)
                sel = QTextCursor(block)
                sel.select(QTextCursor.SelectionType.LineUnderCursor)
                sel.mergeCharFormat(fmt)
            cursor.insertText("\n")

    # ---- 滚动/跳转（翻译 ScrollToLine / GoToLine / ScrollAllToLine）----
    def scroll_to_line(self, line: int):
        if line < 0 or line >= len(self.view_data):
            return
        cursor = QTextCursor(self.document().findBlockByNumber(line))
        self.setTextCursor(cursor)
        self.centerCursor()

    def go_to_line(self, line: int, sync: bool = True):
        self.scroll_to_line(line)
        if sync and self._on_line_clicked:
            self._on_line_clicked(line)

    def scroll_all_to_line(self, line: int, sync_to=None):
        self.scroll_to_line(line)
        if sync_to is not None:
            sync_to.scroll_to_line(line)

    # ---- 差异/冲突：HasNext/PrevDiff、HasNext/PrevConflict ----
    def _states(self) -> List[DiffState]:
        return [vd.state for vd in self.view_data]

    def has_next_diff(self, from_line: int = 0) -> bool:
        return self._find_next(from_line, self._is_diff) is not None

    def has_next_conflict(self, from_line: int = 0) -> bool:
        return self._find_next(from_line, lambda s: s in (
            DiffState.Conflict, DiffState.ConflictIgnored,
            DiffState.ConflictAdded, DiffState.ConflictEmpty)) is not None

    def _find_next(self, start: int, pred) -> Optional[int]:
        for i in range(start, len(self.view_data)):
            if pred(self.view_data[i].state):
                return i
        return None

    def _is_diff(self, s: DiffState) -> bool:
        return s in (DiffState.Removed, DiffState.Added, DiffState.Edited,
                     DiffState.MovedFrom, DiffState.MovedTo)

    def show_diff_lines(self, line: int, other: "BaseView | None" = None):
        self.scroll_to_line(line)
        if other is not None:
            other.scroll_to_line(line)

    # ---- 行号绘制（DrawMargin / CalcLineCharDim 的简化）----
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self.viewport())
        p.setPen(QPen(QColor(160, 160, 160)))
        fm = QFontMetrics(self.font())
        top = self.verticalScrollBar().value() * self._line_height
        y = 2
        line = int(top / self._line_height)
        while y < self.viewport().height():
            p.drawText(4, y + fm.ascent(), str(line))
            line += 1
            y += self._line_height
        p.end()

    # 行号边距画竖线
    def _paint_line_number_margin(self):
        pass

    # ---- 差异块导航（翻译 HasNextDiff/OnNavigateNextdiff）----
    def first_diff_line(self) -> int:
        for i, vd in enumerate(self.view_data):
            if self._is_diff(vd.state):
                return i
        return -1

    def next_diff_from(self, line: int) -> int:
        """从 line 之后找下一差异行；找不到返回 -1。"""
        for i in range(line + 1, len(self.view_data)):
            if self._is_diff(self.view_data[i].state):
                return i
        return -1

    def prev_diff_from(self, line: int) -> int:
        for i in range(line - 1, -1, -1):
            if self._is_diff(self.view_data[i].state):
                return i
        return -1

    def go_to_diff(self, line: int, other: "BaseView | None" = None):
        self.go_to_line(line)
        if other is not None:
            other.go_to_line(line)

    # ---- 合并操作（翻译 MarkBlock / SetViewMarked / SetViewState）----
    def set_marked_block(self, first: int, last: int, marked: bool):
        for i in range(first, min(last + 1, len(self.view_data))):
            self.view_data[i].marked = marked

    def set_view_state(self, index: int, state: DiffState):
        if 0 <= index < len(self.view_data):
            self.view_data[index].state = state

    def take_block(self, index: int, from_other: "BaseView", marked_other: bool = True):
        """把 other 的 index 行文本与状态复制到本视图 index（合并取对方）。"""
        if not (0 <= index < len(self.view_data) and 0 <= index < len(from_other.view_data)):
            return
        src = from_other.view_data[index]
        self.view_data[index].line = src.line
        self.view_data[index].state = DiffState.ConflictsResolved
        self.view_data[index].marked = marked_other
        # 同步另一侧为空占位
        if 0 <= index < len(from_other.view_data):
            from_other.view_data[index].marked = marked_other
        self._rebuild()

    def mark_resolved(self, index: int):
        if 0 <= index < len(self.view_data):
            self.view_data[index].state = DiffState.ConflictsResolved
            self.view_data[index].marked = False
            self._rebuild()

    def merged_lines(self) -> List[str]:
        """返回合并后结果行（ConflictsResolved 的行；Normal/Added 保留；Empty 去掉）。"""
        out = []
        for vd in self.view_data:
            if vd.is_empty and vd.state in (DiffState.Empty, DiffState.ConflictEmpty):
                continue
            if vd.state == DiffState.ConflictsResolved or not vd.is_empty:
                out.append(vd.line)
        return out


class LeftView(BaseView):
    """左视图（旧版本/base side）。"""


class RightView(BaseView):
    """右视图（新版本/target side）。"""