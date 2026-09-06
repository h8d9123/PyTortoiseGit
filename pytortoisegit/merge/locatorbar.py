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

"""locatorbar.py —— TortoiseMerge 的 LocatorBar（定位条）。

逐行翻译 LocatorBar.cpp：顶部差异定位条，点击/拖动把视图滚动到对应行
（ScrollViewToLine），在条上绘制差异位置标记。
比 LineDiffBar 更通用：支持鼠标拖动自动滚动（ScrollOnMouseMove）。
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .diffcolors import DiffColors

COLOR_REMOVED = QColor(255, 200, 100)
COLOR_ADDED = QColor(255, 255, 0)
COLOR_MODIFIED = QColor(220, 220, 255)
COLOR_CONFLICT = QColor(255, 100, 100)


class LocatorBar(QWidget):
    """定位条：绘制差异标记 + 点击/拖动滚动到行。"""

    HEIGHT = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marks: List[Tuple[int, int, QColor]] = []
        self._total = 1
        self._on_locate: Optional[Callable[[int], None]] = None
        self.setMinimumHeight(self.HEIGHT)
        self.setMaximumHeight(self.HEIGHT)

    # ---- DocumentUpdated ---- 
    def set_states(self, states: List):
        self._total = max(1, len(states))
        self._marks = []
        from .viewdata import DiffState
        for i, s in enumerate(states):
            if s in (DiffState.Removed, DiffState.MovedFrom):
                self._marks.append((i, i + 1, COLOR_REMOVED))
            elif s in (DiffState.Added, DiffState.MovedTo):
                self._marks.append((i, i + 1, COLOR_ADDED))
            elif s == DiffState.Edited:
                self._marks.append((i, i + 1, COLOR_MODIFIED))
            elif s in (DiffState.Conflict, DiffState.ConflictAdded,
                       DiffState.ConflictEmpty):
                self._marks.append((i, i + 1, COLOR_CONFLICT))
        self.update()

    def document_updated(self):
        self.update()

    # ---- CalcFixedLayout ----
    def fixed_height(self) -> int:
        return self.HEIGHT

    # ---- OnPaint ----
    def paintEvent(self, _event):
        p = QPainter(self)
        w = self.width()
        h = self.height()
        p.fillRect(self.rect(), self.palette().base().color())
        p.setPen(QPen(self.palette().mid().color(), 1))
        for (start, end, color) in self._marks:
            x0 = int(start / self._total * w)
            x1 = max(x0 + 2, int(end / self._total * w))
            p.fillRect(QRect(x0, 1, x1 - x0, h - 2), color)
        p.end()

    # ---- OnLButtonDown → ScrollViewToLine ----
    def mousePressEvent(self, event):
        frac = event.position().x() / max(1, self.width())
        target = int(frac * self._total)
        if self._on_locate:
            self._on_locate(target)
        super().mousePressEvent(event)

    # ---- ScrollOnMouseMove：拖动时持续定位 ----
    def mouseMoveEvent(self, event):
        frac = event.position().x() / max(1, self.width())
        target = int(frac * self._total)
        if self._on_locate:
            self._on_locate(target)
        super().mouseMoveEvent(event)