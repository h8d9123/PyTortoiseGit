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

"""baseview.py —— TortoiseGitMerge 的 BaseView / LeftView / RightView。"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from .diffcolors import DiffColors
from .inlinediff import inline_spans
from .viewdata import DiffState, EOL, HideState, ViewData


class _LineNumberArea(QWidget):
    def __init__(self, editor: "BaseView"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class BaseView(QPlainTextEdit):
    """一个并排 diff 视图（对应 CBaseView）。"""

    line_moved = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view_data: List[ViewData] = []
        self.other_view: Optional["BaseView"] = None
        self.colors = DiffColors()
        self.inline_diff = True
        self.inline_word = True
        self.show_whitespaces = False
        self.collapsed = False
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMinimumWidth(280)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.setFont(mono)
        self._line_height = QFontMetrics(mono).height()
        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._emit_line)
        self.verticalScrollBar().valueChanged.connect(self._emit_line)
        self._update_line_area_width(0)
        self._on_line_clicked = None
        self._screen_to_view: List[int] = []
        self.modified = False

    def line_number_width(self) -> int:
        return 62

    def _update_line_area_width(self, _n=0):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(cr.left(), cr.top(), self.line_number_width(), cr.height())

    def paint_line_numbers(self, event):
        p = QPainter(self._line_area)
        p.fillRect(event.rect(), QColor(245, 245, 245))
        p.setPen(QColor(140, 140, 140))
        block = self.firstVisibleBlock()
        block_n = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        fm = QFontMetrics(self.font())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                view_i = self._screen_to_view[block_n] if 0 <= block_n < len(self._screen_to_view) else block_n
                if 0 <= view_i < len(self.view_data):
                    vd = self.view_data[view_i]
                    num = str(vd.linenumber) if vd.linenumber >= 0 else ""
                    p.drawText(4, top, 36, fm.height(), Qt.AlignmentFlag.AlignRight, num)
                    icon = self._state_icon(vd.state)
                    if icon is not None:
                        p.drawPixmap(42, top + max(0, (fm.height() - 16) // 2), icon.pixmap(16, 16))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_n += 1
        p.setPen(QColor(200, 200, 200))
        p.drawLine(self._line_area.width() - 1, 0, self._line_area.width() - 1, self.height())
        p.end()

    def set_view_data(self, data: List[ViewData], colors: DiffColors | None = None,
                      rebuild: bool = True):
        self.view_data = data
        if colors is not None:
            self.colors = colors
        if rebuild:
            self._rebuild()

    def set_writable(self, writable: bool):
        self.setReadOnly(not writable)

    def is_writable(self) -> bool:
        return not self.isReadOnly()

    def set_modified(self, on: bool = True):
        self.modified = on

    def set_wrap(self, wrap: bool):
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if wrap
            else QPlainTextEdit.LineWrapMode.NoWrap)

    def get_line_count(self) -> int:
        return len(self.view_data)

    def current_view_line(self) -> int:
        block = self.textCursor().blockNumber()
        if 0 <= block < len(self._screen_to_view):
            return self._screen_to_view[block]
        return block

    def _display_text(self, text: str) -> str:
        if not self.show_whitespaces:
            return text
        return text.replace(" ", "·").replace("\t", "→   ")

    def _rebuild(self):
        self._screen_to_view = []
        self.clear()
        doc = self.document()
        other = self.other_view.view_data if self.other_view is not None else []
        for i, vd in enumerate(self.view_data):
            unchanged = vd.state in (DiffState.Normal, DiffState.Filtered,
                                    DiffState.FilteredDiff)
            if self.collapsed and unchanged:
                if self._screen_to_view:
                    prev = self.view_data[self._screen_to_view[-1]]
                    if prev.state in (DiffState.Normal, DiffState.Filtered,
                                      DiffState.FilteredDiff):
                        continue
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText("···\n")
                self._screen_to_view.append(i)
                continue
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            # 重置字符格式，避免上一行的差异背景色“渗透”到本行/后续行
            cursor.setCharFormat(QTextCharFormat())
            text = "" if vd.is_empty else self._display_text(vd.line)
            other_vd = other[i] if i < len(other) else None
            eol_differs = (
                not vd.is_empty and other_vd is not None
                and vd.ending not in (EOL.NoneEOL, EOL.Autodetect)
                and other_vd.ending not in (EOL.NoneEOL, EOL.Autodetect)
                and vd.ending != other_vd.ending)
            marker = ""
            if not vd.is_empty and (self.show_whitespaces or eol_differs):
                marker = self._eol_marker(vd.ending)
            display = text + marker
            cursor.insertText(display)
            block = doc.findBlockByNumber(doc.blockCount() - 1)
            sel = QTextCursor(block)
            sel.select(QTextCursor.SelectionType.LineUnderCursor)
            bg = self.colors.back_color(vd.state)
            if bg is not None and vd.state != DiffState.Normal:
                fmt = QTextCharFormat()
                fmt.setBackground(bg)
                sel.mergeCharFormat(fmt)
            if self.inline_diff and i < len(other):
                ov = other[i]
                if (vd.state in (DiffState.Removed, DiffState.TheirsRemoved, DiffState.YoursRemoved)
                        and ov.state in (DiffState.Added, DiffState.TheirsAdded, DiffState.YoursAdded,
                                         DiffState.ConflictAdded)) or (
                        vd.state in (DiffState.Added, DiffState.TheirsAdded, DiffState.YoursAdded,
                                     DiffState.ConflictAdded)
                        and ov.state in (DiffState.Removed, DiffState.TheirsRemoved, DiffState.YoursRemoved)):
                    lspans, rspans = inline_spans(vd.line, ov.line, self.inline_word)
                    spans = lspans if vd.is_removed else rspans
                    color = (self.colors.inline_removed_color() if vd.is_removed
                             else self.colors.inline_added_color())
                    for a, b in spans:
                        if a >= len(text) or b <= 0:
                            continue
                        ic = QTextCursor(block)
                        ic.setPosition(block.position() + max(0, a))
                        ic.setPosition(block.position() + min(len(text), b),
                                       QTextCursor.MoveMode.KeepAnchor)
                        fmt = QTextCharFormat()
                        fmt.setBackground(color)
                        ic.mergeCharFormat(fmt)
            # 行尾差异：给行尾标记着色，使换行符差异可见
            if marker and eol_differs:
                ic = QTextCursor(block)
                ic.setPosition(block.position() + len(text))
                ic.setPosition(block.position() + len(display),
                               QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setBackground(
                    self.colors.inline_removed_color()
                    if getattr(self, "_side", "left") == "left"
                    else self.colors.inline_added_color())
                ic.mergeCharFormat(fmt)
            # 换行前重置格式，避免段分隔符带着差异色导致下一段继承
            cursor.setCharFormat(QTextCharFormat())
            cursor.insertText("\n")
            self._screen_to_view.append(i)
        self._update_line_area_width()

    _EOL_MARK = {
        EOL.LF: " ↵LF",
        EOL.CRLF: " ↵CRLF",
        EOL.CR: " ↵CR",
    }

    def _eol_marker(self, ending: EOL) -> str:
        return self._EOL_MARK.get(ending, "")

    def _emit_line(self, *_):
        self.line_moved.emit(self.current_view_line())

    def scroll_to_line(self, line: int):
        if line < 0 or line >= len(self.view_data):
            return
        screen = 0
        for s, v in enumerate(self._screen_to_view):
            if v >= line:
                screen = s
                break
        cursor = QTextCursor(self.document().findBlockByNumber(screen))
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

    def _states(self) -> List[DiffState]:
        return [vd.state for vd in self.view_data]

    def _is_diff(self, s: DiffState) -> bool:
        return s not in (DiffState.Normal, DiffState.Unknown, DiffState.Empty,
                         DiffState.Filtered, DiffState.ConflictsResolved,
                         DiffState.FilteredDiff)

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

    def show_diff_lines(self, line: int, other: "BaseView | None" = None):
        self.scroll_to_line(line)
        if other is not None:
            other.scroll_to_line(line)

    _STATE_ICON = {
        DiffState.Added: "IDI_ADDEDLINE",
        DiffState.Removed: "IDI_REMOVEDLINE",
        DiffState.Edited: "IDI_LINEEDITED",
        DiffState.Conflict: "IDI_CONFLICTEDLINE",
        DiffState.ConflictIgnored: "IDI_CONFLICTEDIGNOREDLINE",
        DiffState.ConflictAdded: "IDI_CONFLICTEDLINE",
        DiffState.WhitespaceDiff: "IDI_WHITESPACELINE",
        DiffState.MovedFrom: "IDI_MOVEDLINE",
        DiffState.MovedTo: "IDI_MOVEDLINE",
        DiffState.Normal: "IDI_EQUALLINE",
        DiffState.TheirsAdded: "IDI_ADDEDLINE",
        DiffState.YoursAdded: "IDI_ADDEDLINE",
        DiffState.TheirsRemoved: "IDI_REMOVEDLINE",
        DiffState.YoursRemoved: "IDI_REMOVEDLINE",
        DiffState.IdenticalAdded: "IDI_ADDEDLINE",
        DiffState.IdenticalRemoved: "IDI_REMOVEDLINE",
    }

    def _state_icon(self, state: DiffState):
        key = self._STATE_ICON.get(state)
        if not key:
            return None
        try:
            from ..res import icons
            return icons.icon(key)
        except Exception:
            return None

    def first_diff_line(self) -> int:
        for i, vd in enumerate(self.view_data):
            if self._is_diff(vd.state):
                return i
        return -1

    def next_diff_from(self, line: int) -> int:
        for i in range(line + 1, len(self.view_data)):
            if self._is_diff(self.view_data[i].state):
                return i
        return -1

    def prev_diff_from(self, line: int) -> int:
        for i in range(line - 1, -1, -1):
            if self._is_diff(self.view_data[i].state):
                return i
        return -1

    def next_conflict_from(self, line: int) -> int:
        for i in range(line + 1, len(self.view_data)):
            if self.view_data[i].is_conflict:
                return i
        return -1

    def prev_conflict_from(self, line: int) -> int:
        for i in range(line - 1, -1, -1):
            if self.view_data[i].is_conflict:
                return i
        return -1

    def block_range(self, line: int) -> tuple:
        if not (0 <= line < len(self.view_data)):
            return 0, -1
        if not self._is_diff(self.view_data[line].state):
            return line, line
        start = line
        while start > 0 and self._is_diff(self.view_data[start - 1].state):
            start -= 1
        end = line
        while end + 1 < len(self.view_data) and self._is_diff(self.view_data[end + 1].state):
            end += 1
        return start, end

    def go_to_diff(self, line: int, other: "BaseView | None" = None):
        self.go_to_line(line)
        if other is not None:
            other.go_to_line(line)

    def set_marked_block(self, first: int, last: int, marked: bool):
        for i in range(first, min(last + 1, len(self.view_data))):
            self.view_data[i].marked = marked

    def set_view_state(self, index: int, state: DiffState):
        if 0 <= index < len(self.view_data):
            self.view_data[index].state = state

    def take_block(self, index: int, from_other: "BaseView", marked_other: bool = True):
        from .blocks import use_view_block
        start, end = self.block_range(index)
        if end < start:
            return
        use_view_block(self.view_data, from_other.view_data, start, end)
        if marked_other:
            for i in range(start, min(end + 1, len(self.view_data), len(from_other.view_data))):
                self.view_data[i].marked = True
                from_other.view_data[i].marked = True
        self.set_modified()
        self._rebuild()
        from_other._rebuild()

    def take_file(self, from_other: "BaseView"):
        from .blocks import use_view_block
        if not self.view_data:
            return
        use_view_block(self.view_data, from_other.view_data, 0, len(self.view_data) - 1)
        self.set_modified()
        self._rebuild()

    def use_resolved_block(self, from_other: "BaseView", first: int, last: int):
        from .blocks import use_resolved_block
        if last < first:
            return
        use_resolved_block(self.view_data, from_other.view_data, first, last)
        self.set_modified()
        self._rebuild()

    def use_resolved_file(self, from_other: "BaseView"):
        if not self.view_data:
            return
        self.use_resolved_block(from_other, 0, len(self.view_data) - 1)

    def mark_resolved(self, index: int):
        from .blocks import resolve_state
        start, end = self.block_range(index)
        for i in range(start, end + 1):
            if 0 <= i < len(self.view_data):
                self.view_data[i].state = resolve_state(self.view_data[i].state)
                self.view_data[i].marked = False
        self.set_modified()
        self._rebuild()

    def merged_lines(self) -> List[str]:
        out = []
        for vd in self.view_data:
            if vd.is_empty:
                continue
            out.append(vd.line)
        return out

    def first_inline_col(self, line: int, forward: bool = True) -> int:
        if self.other_view is None or not (0 <= line < len(self.view_data)):
            return -1
        if line >= len(self.other_view.view_data):
            return -1
        mine = self.view_data[line].line
        other = self.other_view.view_data[line].line
        lspans, rspans = inline_spans(mine, other, self.inline_word)
        spans = lspans if self is getattr(self.other_view, "other_view", None) else lspans
        if self.other_view and getattr(self, "_side", "left") == "right":
            spans = rspans
        if not spans:
            return -1
        return spans[0][0] if forward else spans[-1][0]


class LeftView(BaseView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._side = "left"


class RightView(BaseView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._side = "right"


class BottomView(BaseView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._side = "bottom"
