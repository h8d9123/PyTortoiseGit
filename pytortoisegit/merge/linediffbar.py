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

"""linediffbar.py —— TortoiseGitMerge 的 LineDiffBar（差异分布条）。

逐行翻译 LineDiffBar.cpp：
  * 在主窗口左侧显示一个横向（实为主框架侧边）差异条，_OnPaint 画出
    每处差异块的彩色标记（删除橙/添加黄）
  * ShowLines / DocumentUpdated：点击条上某处跳转到对应差异行
  * CalcFixedLayout：固定两行高度
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .diffcolors import DiffColors
from .viewdata import DiffState

# 差异块标记颜色（对应 DiffColors）
COLOR_REMOVED = QColor(255, 200, 100)
COLOR_ADDED = QColor(255, 255, 0)
COLOR_MODIFIED = QColor(220, 220, 255)


class LineDiffBar(QWidget):
    """差异分布条：按总行数绘制差异块，点击跳转。"""

    LINE_HEIGHT = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marks: List[Tuple[float, float, DiffState]] = []
        self._total = 1
        self._on_click: Optional[Callable[[int], None]] = None
        self.setMinimumHeight(self.LINE_HEIGHT)
        self.setMaximumHeight(self.LINE_HEIGHT)

    # ---- ShowLines（把各差异行加入标记）----
    def set_rows(self, states: List[DiffState]):
        self._total = max(1, len(states))
        self._marks = []
        for i, s in enumerate(states):
            if s in (DiffState.Removed, DiffState.MovedFrom):
                self._marks.append((i, i + 1, DiffState.MovedFrom))
            elif s in (DiffState.Added, DiffState.MovedTo):
                self._marks.append((i, i + 1, DiffState.MovedTo))
            elif s == DiffState.Edited:
                self._marks.append((i, i + 1, DiffState.Edited))
        self.update()

    def document_updated(self):
        self.update()

    # ---- CalcFixedLayout: 固定高度 ----
    def fixed_height(self) -> int:
        return self.LINE_HEIGHT

    # ---- OnPaint ----
    def paintEvent(self, _event):
        p = QPainter(self)
        w = self.width()
        h = self.height()
        p.fillRect(self.rect(), self.palette().base().color())
        p.setPen(QPen(self.palette().mid().color(), 1))
        for (start, end, state) in self._marks:
            x0 = int(start / self._total * w)
            x1 = max(x0 + 2, int(end / self._total * w))
            color = COLOR_REMOVED if state == DiffState.MovedFrom else (
                COLOR_ADDED if state == DiffState.MovedTo else COLOR_MODIFIED)
            p.fillRect(QRect(x0, 1, x1 - x0, h - 2), color)
        p.end()

    # ---- 点击跳转（OnLButtonDown）----
    def mousePressEvent(self, event):
        frac = event.position().x() / max(1, self.width())
        target = int(frac * self._total)
        if self._on_click:
            self._on_click(target)
        super().mousePressEvent(event)