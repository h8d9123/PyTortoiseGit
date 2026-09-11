"""revisiongraphdlg.py —— RevisionGraphDlg：绘制的分支节点图。

以 GitRevLoglist 计算 lane 布局，用 QPainter 画出提交节点（圆点）与父子连线
（贝塞尔曲线），右侧标注 refs 与提交主题，对齐原版 Revision Graph 的节点图。
"""

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

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.rev import GitRevLoglist
from ..res.strings import tr
from .statgraphdlg import StatGraphDlg

_NODE_R = 7
_COL_W = 28
_ROW_H = 26
_MARGIN_X = 26
_MARGIN_Y = 22
_TEXT_W = 360

_LANE_COLORS = (
    QColor(0x0A, 0x24, 0x36), QColor(0xC0, 0x00, 0x00),
    QColor(0x00, 0x80, 0x00), QColor(0x00, 0x00, 0xC0),
    QColor(0x80, 0x80, 0x80), QColor(0x80, 0x80, 0x00),
    QColor(0x00, 0x80, 0x80), QColor(0x80, 0x00, 0x80),
)


class _GraphCanvas(QWidget):
    """绘制提交节点图：x=lane，y=提交顺序。"""

    def __init__(self, commits, parent=None):
        super().__init__(parent)
        self._commits = list(commits)
        self._index = {c.hash: i for i, c in enumerate(self._commits)}
        max_lane = max((c.lane for c in self._commits), default=0)
        w = _MARGIN_X * 2 + (max_lane + 1) * _COL_W + _TEXT_W
        h = _MARGIN_Y * 2 + max(1, len(self._commits)) * _ROW_H
        self.setMinimumSize(w, h)

    def node_count(self) -> int:
        return len(self._commits)

    def _pos(self, commit) -> QPointF:
        i = self._index[commit.hash]
        return QPointF(_MARGIN_X + commit.lane * _COL_W,
                       _MARGIN_Y + i * _ROW_H + _ROW_H / 2)

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), self.palette().base())

        # 连线（子 -> 父，贝塞尔）
        for c in self._commits:
            a = self._pos(c)
            for parent in c.parents:
                idx = self._index.get(parent)
                if idx is None:
                    continue
                b = self._pos(self._commits[idx])
                col = _LANE_COLORS[c.lane % len(_LANE_COLORS)]
                p.setPen(QPen(col, 2, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                mid = (a.y() + b.y()) / 2
                path = QPainterPath(a)
                path.cubicTo(QPointF(a.x(), mid), QPointF(b.x(), mid), b)
                p.drawPath(path)

        # 节点 + 文本
        fm = p.fontMetrics()
        ref_font = QFont(self.font())
        ref_font.setBold(True)
        for c in self._commits:
            a = self._pos(c)
            col = _LANE_COLORS[c.lane % len(_LANE_COLORS)]
            p.setBrush(QBrush(col))
            p.setPen(QPen(col, 1))
            p.drawEllipse(a, _NODE_R, _NODE_R)

            x = a.x() + _NODE_R + 6
            y = a.y() + fm.ascent() / 2 - 1
            if c.refs_str:
                p.setFont(ref_font)
                p.setPen(QPen(QColor(0x00, 0x60, 0x00)))
                ref_text = f"[{c.refs_str}] "
                p.drawText(QPointF(x, y), ref_text)
                x += fm.horizontalAdvance(ref_text)
            p.setFont(self.font())
            p.setPen(QPen(self.palette().text().color()))
            p.drawText(QPointF(x, y), c.subject)


class RevisionGraphDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.setWindowTitle(
            f"{repo.name} — {tr('revgraph_title', 'Revision Graph')}")
        self.resize(900, 640)

        lay = QVBoxLayout(self)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.canvas = _GraphCanvas([], self.scroll)
        self.scroll.setWidget(self.canvas)
        lay.addWidget(self.scroll, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_stats = QPushButton(tr("revgraph_stats", "Statistics"), self)
        self.btn_stats.clicked.connect(self._open_stats)
        row.addWidget(self.btn_stats)
        lay.addLayout(row)

        self._load()

    def _load(self):
        run_async(self._load_bg, on_done=self._on_loaded, parent=self)

    def _load_bg(self) -> list:
        log = GitRevLoglist(self.repo)
        log.load(limit=300)
        return list(log)

    def _on_loaded(self, commits):
        self.canvas = _GraphCanvas(commits, self.scroll)
        self.scroll.setWidget(self.canvas)

    def _open_stats(self):
        StatGraphDlg(self.repo, parent=self).exec()
