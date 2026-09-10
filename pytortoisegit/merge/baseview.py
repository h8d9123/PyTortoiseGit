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

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from .diffcolors import DiffColors
from .filetextlines import UnicodeType
from .inlinediff import inline_spans
from .viewdata import DiffState, EOL, HideState, ViewData


class CharGroup(Enum):
    """对齐 CBaseView::ECharGroup（按优先级低到高）。"""
    UNKNOWN = 0
    CONTROL = 1
    WHITESPACE = 2
    WORDSEPARATOR = 3
    WORDLETTER = 4


# 对齐 CBaseView 默认 WordSeparators
DEFAULT_WORD_SEPARATORS = "[]();:.,{}!@#$%^&*-+=|/\\<>'`~\"?"


@dataclass
class WhitecharsProperties:
    """对齐 CBaseView::TWhitecharsProperties。"""
    has_mixed_eols: bool = False
    has_trail_white_chars: bool = False
    has_spaces_to_convert: bool = False
    has_tabs_to_convert: bool = False


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
    caret_line_changed = Signal(int)

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
        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.verticalScrollBar().valueChanged.connect(self._emit_line)
        self._update_line_area_width(0)
        self._on_line_clicked = None
        self._screen_to_view: List[int] = []
        self.modified = False
        # 对齐 CBaseView 的空白/编码/行尾相关状态
        self.tab_size = 4
        self.tab_mode = 0
        self.line_endings = EOL.AutoLine
        self.text_type = UnicodeType.AUTOTYPE
        self.word_separators = DEFAULT_WORD_SEPARATORS
        # 查找 / 标记词
        self.marked_word = ""
        self.find_text = ""
        self.match_case = False
        self.limit_to_diff = True
        self.marked_word_lines: List[int] = []
        self.find_string_lines: List[int] = []
        self.marked_word_count = 0
        self._cur_block = (-1, -1)
        self.show_eol_diff = False
        self._current_line = -1
        self._find_selections: list = []

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
                    if self._cur_block[0] <= view_i <= self._cur_block[1]:
                        p.fillRect(0, top, self._line_area.width() - 1, fm.height(),
                                   QColor(180, 180, 255))
                    num = str(vd.linenumber) if vd.linenumber >= 0 else ""
                    p.drawText(4, top, 36, fm.height(), Qt.AlignmentFlag.AlignRight, num)
                    icon = self._state_icon(vd.state, vd.marked)
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
                and vd.ending not in (EOL.NoEnding, EOL.AutoLine)
                and other_vd.ending not in (EOL.NoEnding, EOL.AutoLine)
                and vd.ending != other_vd.ending)
            marker = ""
            if not vd.is_empty and (self.show_whitespaces
                                    or (self.show_eol_diff and eol_differs)):
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

    # ---- 行尾 / 编码（对齐 CBaseView 的 GetLineEndings 等）----
    def get_line_endings(self, has_mixed_eols: bool | None = None) -> EOL:
        if has_mixed_eols is None:
            has_mixed_eols = self.get_whitechars_properties().has_mixed_eols
        if has_mixed_eols:
            return EOL.AutoLine  # 混合行尾 → hack 值
        if self.line_endings == EOL.AutoLine:
            return EOL.CRLF
        return self.line_endings

    def set_line_ending_style(self, eol: EOL):
        self.line_endings = eol

    def replace_line_endings(self, eol: EOL):
        if eol == EOL.AutoLine:
            return
        self.line_endings = eol
        for vd in self.view_data:
            if vd.is_empty:
                continue
            if vd.ending in (EOL.AutoLine, EOL.NoEnding, self.line_endings):
                continue
            vd.ending = eol
        self.set_modified()
        self._rebuild()

    def get_text_type(self) -> UnicodeType:
        return self.text_type

    def set_text_type(self, text_type: UnicodeType):
        if self.text_type == text_type:
            return
        self.text_type = text_type
        self.set_modified()
        self._rebuild()

    def get_tab_size(self) -> int:
        return self.tab_size

    def set_tab_size(self, n: int):
        self.tab_size = n

    def get_tab_mode(self) -> int:
        return self.tab_mode

    def set_tab_mode(self, n: int):
        self.tab_mode = n

    # ---- 空白工具（对齐 ConvertTabToSpaces/Tabularize/RemoveTrailWhiteChars）----
    def get_largest_space_streak(self, line: str) -> int:
        count = 0
        maxstreak = 0
        for ch in line:
            if ch == " ":
                count += 1
            else:
                maxstreak = max(count, maxstreak)
                count = 0
        return max(count, maxstreak)

    def convert_tab_to_spaces(self):
        modified = False
        for vd in self.view_data:
            if vd.is_empty:
                continue
            s = vd.line
            pos_in = pos_out = 0
            tab_found = False
            while pos_in < len(s):
                c = s[pos_in]
                if c == " ":
                    pos_in += 1
                    pos_out += 1
                    continue
                if c == "\t":
                    pos_in += 1
                    tab_found = True
                    pos_out = (pos_out + self.tab_size) - pos_out % self.tab_size
                    continue
                break
            if tab_found:
                vd.line = " " * pos_out + s[pos_in:]
                modified = True
        if modified:
            self.set_modified()
            self._rebuild()

    def tabularize(self):
        modified = False
        for vd in self.view_data:
            if vd.is_empty:
                continue
            s = vd.line
            n_del = 0
            n_tab = 0
            n_space = 0
            pos = 0
            while pos < len(s):
                c = s[pos]
                pos += 1
                if c == " ":
                    n_space += 1
                    if n_space < self.tab_size:
                        continue
                    n_tab += 1
                    n_space = 0
                    n_del = pos
                    continue
                if c == "\t":
                    n_tab += 1
                    n_space = 0
                    n_del = pos
                    continue
                break
            if n_del > 0:
                new = "\t" * n_tab + s[n_del:]
                if new != s:
                    vd.line = new
                    modified = True
        if modified:
            self.set_modified()
            self._rebuild()

    def remove_trail_white_chars(self):
        modified = False
        for vd in self.view_data:
            if vd.is_empty:
                continue
            new = vd.line.rstrip()
            if len(new) != len(vd.line):
                vd.line = new
                modified = True
        if modified:
            self.set_modified()
            self._rebuild()

    def get_whitechars_properties(self) -> WhitecharsProperties:
        if len(self.view_data) > 10000:
            return WhitecharsProperties(True, True, True, True)
        ret = WhitecharsProperties()
        for vd in self.view_data:
            if vd.is_empty or not vd.line:
                continue
            s = vd.line
            pos = 0
            n_space = 0
            while pos < len(s) and (not ret.has_spaces_to_convert or not ret.has_tabs_to_convert):
                c = s[pos]
                pos += 1
                if c == " ":
                    n_space += 1
                    if n_space >= self.tab_size:
                        ret.has_spaces_to_convert = True
                    continue
                if c == "\t":
                    ret.has_tabs_to_convert = True
                    if n_space != 0:
                        ret.has_spaces_to_convert = True
                    continue
                break
            if s[-1] in (" ", "\t"):
                ret.has_trail_white_chars = True
            le = vd.ending
            if (not ret.has_mixed_eols and le != self.line_endings
                    and le not in (EOL.AutoLine, EOL.NoEnding)):
                ret.has_mixed_eols = True
        return ret

    # ---- 状态分类（对齐 IsStateConflicted/Empty/Removed/ResolveState）----
    @staticmethod
    def is_state_conflicted(state: DiffState) -> bool:
        return state in (DiffState.Conflict, DiffState.ConflictIgnored,
                         DiffState.ConflictEmpty, DiffState.ConflictAdded)

    @staticmethod
    def is_state_empty(state: DiffState) -> bool:
        return state in (DiffState.ConflictEmpty, DiffState.Unknown,
                         DiffState.Empty)

    @staticmethod
    def is_state_removed(state: DiffState) -> bool:
        return state in (DiffState.Removed, DiffState.TheirsRemoved,
                         DiffState.YoursRemoved, DiffState.IdenticalRemoved)

    @staticmethod
    def resolve_state(state: DiffState) -> DiffState:
        if BaseView.is_state_conflicted(state):
            if state == DiffState.ConflictEmpty:
                return DiffState.ConflictResolvedEmpty
            return DiffState.ConflictsResolved
        return state

    def is_view_line_empty(self, n_view_line: int) -> bool:
        if not (0 <= n_view_line < len(self.view_data)):
            return False
        return self.is_state_empty(self.view_data[n_view_line].state)

    # ---- 字符分组（对齐 GetCharGroup/IsWordSeparator）----
    def get_char_group(self, ch: str) -> CharGroup:
        if ch in (" ", "\t"):
            return CharGroup.WHITESPACE
        if ch < "\x20":
            return CharGroup.CONTROL
        if ch in self.word_separators:
            return CharGroup.WORDSEPARATOR
        return CharGroup.WORDLETTER

    def is_word_separator(self, ch: str) -> bool:
        return self.get_char_group(ch) in (
            CharGroup.CONTROL, CharGroup.WHITESPACE, CharGroup.WORDSEPARATOR)

    # ---- 行长（对齐 GetViewLineLength/GetLineLengthWithTabsConverted）----
    def get_view_line_length(self, n_view_line: int) -> int:
        if not (0 <= n_view_line < len(self.view_data)):
            return 0
        return len(self.view_data[n_view_line].line)

    def get_line_length_with_tabs_converted(self, index: int) -> int:
        if not (0 <= index < len(self.view_data)):
            return 0
        s = self.view_data[index].line
        tab_count = s.count("\t")
        return len(s) + tab_count * (self.tab_size - 1)

    def get_indent_chars_for_line(self, x: int, y: int) -> int:
        """对齐 GetIndentCharsForLine（简化：SMARTINDENT 判定用 tab/空格）。"""
        if not (0 <= y < len(self.view_data)):
            return 0
        line = self.view_data[y].line
        TABMODE_SMARTINDENT = 1
        if self.tab_mode & TABMODE_SMARTINDENT:
            if "\t" in line:
                return 0  # 用 tab
            if self.get_largest_space_streak(line) > self.tab_size:
                return self.tab_size  # 用空格
        return 0

    # ---- 缩进工具（对齐 Add/RemoveIndentationForSelectedBlock）----
    def add_indentation_for_selected_block(self, start: int, end: int,
                                           end_col: int = 1):
        modified = False
        for n in range(start, end + 1):
            if n == end and end_col == 0:
                continue
            if not (0 <= n < len(self.view_data)):
                continue
            vd = self.view_data[n]
            if vd.is_empty or not vd.line.strip():
                continue
            indent = self.get_indent_chars_for_line(0, n)
            tab = (" " * indent) if indent > 0 else "\t"
            vd.line = tab + vd.line
            modified = True
        if modified:
            self.set_modified()
            self._rebuild()

    def remove_indentation_for_selected_block(self, start: int, end: int,
                                              end_col: int = 1):
        modified = False
        for n in range(start, end + 1):
            if n == end and end_col == 0:
                continue
            if not (0 <= n < len(self.view_data)):
                continue
            vd = self.view_data[n]
            if vd.is_empty:
                continue
            s = vd.line
            pos = 0
            while pos < self.tab_size and pos < len(s):
                c = s[pos]
                if c == " ":
                    pos += 1
                    continue
                if c == "\t":
                    pos += 1
                break
            if pos > 0:
                vd.line = s[pos:]
                modified = True
        if modified:
            self.set_modified()
            self._rebuild()

    # ---- 清理全空行（对齐 CleanEmptyLines）----
    def clean_empty_lines(self, views: List["BaseView"]) -> int:
        removed = 0
        i = 0
        while i < len(self.view_data):
            all_empty = True
            for v in views:
                if i < len(v.view_data) and not self.is_state_empty(
                        v.view_data[i].state):
                    all_empty = False
                    break
            if all_empty:
                for v in views:
                    if i < len(v.view_data):
                        del v.view_data[i]
                removed += 1
                continue
            i += 1
        return removed

    # ---- 隐藏行（对齐 IsViewLineHidden）----
    def is_view_line_hidden(self, n_view_line: int) -> bool:
        if not (0 <= n_view_line < len(self.view_data)):
            return False
        return (self.collapsed
                and self.view_data[n_view_line].hidestate != HideState.Shown)

    # ---- 标记词 / 查找（对齐 BuildMarkedWordArray/BuildFindStringArray）----
    def _char_group_at(self, line: str, i: int) -> CharGroup:
        if 0 <= i < len(line):
            return self.get_char_group(line[i])
        return CharGroup.UNKNOWN

    def set_marked_word(self, word: str):
        self.marked_word = word or ""
        self.build_marked_word_array()

    def build_marked_word_array(self):
        self.marked_word_lines = []
        self.marked_word_count = 0
        doit = bool(self.marked_word)
        for vd in self.view_data:
            if not doit or not vd.line:
                self.marked_word_lines.append(0)
                continue
            line = vd.line
            found = 0
            start = 0
            while True:
                idx = line.find(self.marked_word, start)
                if idx < 0:
                    break
                n_mark_end = idx + len(self.marked_word)
                e_left = self._char_group_at(line, idx - 1)
                e_start = self._char_group_at(line, idx)
                if e_left != e_start:
                    e_right = self._char_group_at(line, n_mark_end)
                    e_end = self._char_group_at(line, n_mark_end - 1)
                    if e_right != e_end:
                        found = 1
                        self.marked_word_count += 1
                        break
                start = idx + 1
            self.marked_word_lines.append(found)

    def build_find_string_array(self):
        self.find_string_lines = []
        doit = bool(self.find_text)
        for vd in self.view_data:
            if not doit or not vd.line:
                self.find_string_lines.append(0)
                continue
            state = vd.state
            if state == DiffState.Empty:
                self.find_string_lines.append(0)
                continue
            if (state in (DiffState.Unknown, DiffState.Normal,
                          DiffState.FilteredDiff) and self.limit_to_diff):
                self.find_string_lines.append(0)
                continue
            hay = vd.line if self.match_case else vd.line.lower()
            needle = self.find_text if self.match_case else self.find_text.lower()
            self.find_string_lines.append(hay.count(needle))

    def _emit_line(self, *_):
        self.line_moved.emit(self.current_view_line())

    def _on_cursor_moved(self, *_):
        self.caret_line_changed.emit(self.current_view_line())

    def _screen_for_view(self, view_line: int) -> int:
        for s, v in enumerate(self._screen_to_view):
            if v == view_line:
                return s
        return -1

    def set_current_line(self, view_line: int):
        """高亮当前行（ExtraSelection），供跨视图同步。"""
        self._current_line = view_line
        self._apply_extra_selections()

    def _apply_extra_selections(self):
        from PySide6.QtWidgets import QTextEdit
        sels = list(self._find_selections)
        screen = (self._screen_for_view(self._current_line)
                  if self._current_line >= 0 else -1)
        if screen >= 0:
            block = self.document().findBlockByNumber(screen)
            if block.isValid():
                sel = QTextEdit.ExtraSelection()
                sel.cursor = QTextCursor(block)
                sel.cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(230, 230, 255))
                sel.format = fmt
                sels.append(sel)
        self.setExtraSelections(sels)

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
        DiffState.TheirsAdded: "IDI_ADDEDLINE",
        DiffState.YoursAdded: "IDI_ADDEDLINE",
        DiffState.IdenticalAdded: "IDI_ADDEDLINE",
        DiffState.ConflictAdded: "IDI_ADDEDLINE",
        DiffState.Removed: "IDI_REMOVEDLINE",
        DiffState.TheirsRemoved: "IDI_REMOVEDLINE",
        DiffState.YoursRemoved: "IDI_REMOVEDLINE",
        DiffState.IdenticalRemoved: "IDI_REMOVEDLINE",
        DiffState.Conflict: "IDI_CONFLICTEDLINE",
        DiffState.ConflictIgnored: "IDI_CONFLICTEDIGNOREDLINE",
        DiffState.Edited: "IDI_LINEEDITED",
        DiffState.MovedFrom: "IDI_MOVEDLINE",
        DiffState.MovedTo: "IDI_MOVEDLINE",
        DiffState.IdenticalMovedFrom: "IDI_MOVEDLINE",
        DiffState.IdenticalMovedTo: "IDI_MOVEDLINE",
        DiffState.Whitespace: "IDI_WHITESPACELINE",
        DiffState.WhitespaceDiff: "IDI_WHITESPACELINE",
        DiffState.Filtered: "IDI_EQUALLINE",
        DiffState.FilteredDiff: "IDI_EQUALLINE",
        DiffState.ConflictsResolved: "IDI_EQUALLINE",
    }

    def _state_icon(self, state: DiffState, marked: bool = False):
        key = "IDI_LINEMARKED" if marked else self._STATE_ICON.get(state)
        if not key:
            return None
        try:
            from ..res import icons
            return icons.icon(key)
        except Exception:  # noqa: BLE001
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

    def set_current_block(self, first: int, last: int = -1):
        """标记当前差异块（在行号区高亮），对齐 DrawBlockLine 语义。"""
        if last < 0:
            last = first
        self._cur_block = (first, last)
        self._line_area.update()

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

    # ---- 标记块操作（对齐 MarkBlock/LeaveOnlyMarkedBlocks 等）----
    def mark_block(self, marked: bool, first: int, last: int):
        from .blocks import mark_block
        mark_block(self.view_data, marked, first, last)
        self.set_modified()
        self._rebuild()

    def leave_only_marked_blocks(self, other: "BaseView"):
        from .blocks import leave_only_marked_blocks
        leave_only_marked_blocks(self.view_data, other.view_data)
        self.set_modified()
        self._rebuild()

    def use_view_file_of_marked(self, other: "BaseView"):
        from .blocks import use_view_file_of_marked
        use_view_file_of_marked(self.view_data, other.view_data)
        self.set_modified()
        self._rebuild()

    def use_view_file_except_edited(self, other: "BaseView"):
        from .blocks import use_view_file_except_edited
        use_view_file_except_edited(self.view_data, other.view_data)
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
