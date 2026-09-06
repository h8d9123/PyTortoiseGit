# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""linediffbar.py —— TortoiseGitMerge 的 LineDiffBar。

原版停在窗口底部，高度为两行：当前左右行的字符级对照（不是全文件分布条）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .diffcolors import DiffColors
from .inlinediff import inline_spans


class LineDiffBar(QWidget):
    """当前行的左右字符级对照条（对齐 CLineDiffBar）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left = ""
        self._right = ""
        self._word_wise = True
        self.colors = DiffColors()
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.setFont(mono)
        self._line_h = QFontMetrics(mono).height() + 4
        self.setMinimumHeight(self._line_h * 2)
        self.setMaximumHeight(self._line_h * 2)

    def set_lines(self, left: str, right: str, word_wise: bool = True):
        self._left = left or ""
        self._right = right or ""
        self._word_wise = word_wise
        self.update()

    def document_updated(self):
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(245, 245, 245))
        fm = QFontMetrics(self.font())
        h = self.height() // 2
        lspans, rspans = inline_spans(self._left, self._right, self._word_wise)
        self._paint_line(p, fm, 0, h, self._left, lspans,
                         self.colors.inline_removed_color())
        self._paint_line(p, fm, h, h, self._right, rspans,
                         self.colors.inline_added_color())
        p.setPen(QPen(QColor(180, 180, 180)))
        p.drawLine(0, h, self.width(), h)
        p.end()

    def _paint_line(self, p: QPainter, fm: QFontMetrics, y: int, h: int,
                    text: str, spans, color: QColor):
        p.fillRect(0, y, self.width(), h, QColor(255, 255, 255))
        x = 6
        baseline = y + fm.ascent() + 2
        marked = [False] * (len(text) + 1)
        for a, b in spans:
            for i in range(max(0, a), min(len(text), b)):
                marked[i] = True
        i = 0
        while i < len(text):
            j = i + 1
            while j < len(text) and marked[j] == marked[i]:
                j += 1
            chunk = text[i:j]
            w = fm.horizontalAdvance(chunk)
            if marked[i]:
                p.fillRect(x, y + 1, w, h - 2, color)
            p.setPen(QColor(0, 0, 0))
            p.drawText(x, baseline, chunk)
            x += w
            i = j
        if not text:
            p.setPen(QColor(160, 160, 160))
            p.drawText(6, baseline, " ")
