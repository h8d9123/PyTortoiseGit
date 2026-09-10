# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""locatorbar.py —— TortoiseMerge 的 LocatorBar（左侧竖向定位条）。"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .viewdata import DiffState

COLOR_REMOVED = QColor(255, 200, 100)
COLOR_ADDED = QColor(255, 255, 0)
COLOR_MODIFIED = QColor(220, 220, 255)
COLOR_CONFLICT = QColor(255, 100, 100)
COLOR_VIEW = QColor(80, 80, 80, 50)


class LocatorBar(QWidget):
    """左侧 minimap：按行比例绘制差异，点击/拖动滚动。"""

    WIDTH = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stripes: List[List[Tuple[int, int, QColor]]] = []
        self._total = 1
        self._view_start = 0
        self._view_end = 0
        self._on_locate: Optional[Callable[[int], None]] = None
        self.setMinimumWidth(self.WIDTH)
        self.setMaximumWidth(self.WIDTH)
        self.setMouseTracking(True)

    @staticmethod
    def _marks_for(states: List) -> List[Tuple[int, int, QColor]]:
        marks: List[Tuple[int, int, QColor]] = []
        for i, s in enumerate(states):
            if s in (DiffState.Removed, DiffState.MovedFrom,
                     DiffState.TheirsRemoved, DiffState.YoursRemoved,
                     DiffState.IdenticalRemoved):
                marks.append((i, i + 1, COLOR_REMOVED))
            elif s in (DiffState.Added, DiffState.MovedTo,
                       DiffState.TheirsAdded, DiffState.YoursAdded,
                       DiffState.IdenticalAdded):
                marks.append((i, i + 1, COLOR_ADDED))
            elif s == DiffState.Edited:
                marks.append((i, i + 1, COLOR_MODIFIED))
            elif s in (DiffState.Conflict, DiffState.ConflictAdded,
                       DiffState.ConflictEmpty, DiffState.ConflictIgnored):
                marks.append((i, i + 1, COLOR_CONFLICT))
        return marks

    def set_states(self, states: List, right_states: List | None = None,
                   bottom_states: List | None = None):
        """对齐 CLocatorBar：最多三条 stripe（左/右/底）。"""
        self._total = max(1, len(states))
        self._stripes = [self._marks_for(states)]
        if right_states is not None:
            self._stripes.append(self._marks_for(right_states))
        if bottom_states is not None:
            self._stripes.append(self._marks_for(bottom_states))
        self.update()

    def set_viewport(self, start: int, end: int):
        self._view_start = start
        self._view_end = end
        self.update()

    def document_updated(self):
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        w = self.width()
        h = self.height()
        p.fillRect(self.rect(), QColor(235, 235, 235))
        n = max(1, len(self._stripes))
        stripe_w = max(1, (w - 2) // n)
        for idx, marks in enumerate(self._stripes):
            x0 = 1 + idx * stripe_w
            for start, end, color in marks:
                y0 = int(start / self._total * h)
                y1 = max(y0 + 2, int(end / self._total * h))
                p.fillRect(QRect(x0, y0, stripe_w, y1 - y0), color)
        if self._view_end > self._view_start:
            y0 = int(self._view_start / self._total * h)
            y1 = max(y0 + 4, int(self._view_end / self._total * h))
            p.fillRect(QRect(0, y0, w, y1 - y0), COLOR_VIEW)
            p.setPen(QPen(QColor(90, 90, 90)))
            p.drawRect(0, y0, w - 1, y1 - y0)
        p.end()

    def _locate(self, event):
        frac = event.position().y() / max(1, self.height())
        target = int(frac * self._total)
        if self._on_locate:
            self._on_locate(target)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._locate(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._locate(event)
        super().mouseMoveEvent(event)
