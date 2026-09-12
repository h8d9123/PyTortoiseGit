"""revisiongraphdlg.py —— RevisionGraphDlg：绘制的分支节点图。

对齐 TortoiseGit 原版 Revision Graph：

* 提交按 Sugiyama 分层布局（见 ``git/revgraph.py``），新提交在上、父提交在下。
* 节点为圆角矩形，每个引用一行，按引用类型着色（当前分支红、本地分支绿、
  远程分支米黄、标签黄、无引用浅粉并显示短 hash）。
* 父子连线沿折点绘制，两端裁剪到节点边界并带箭头。

默认使用 ``--simplify-by-decoration`` 只保留被引用标注的提交与分叉/合并点，
与原版 ``LOG_INFO_SIMPILFY_BY_DECORATION`` 一致。
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
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)
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
from ..git.revgraph import GraphLayout, build_layout
from ..res.strings import tr
from .statgraphdlg import StatGraphDlg

# C++：默认缩放字体 9；左上/右下内边距 20 / 5
_FONT_SIZE = 9
_MARGIN_X = 20.0
_MARGIN_Y = 5.0
_CORNER = 12.0
_ARROW_SIZE = 8.0
_ARROW_COS = math.cos(math.pi / 8)
_ARROW_SIN = math.sin(math.pi / 8)

# Colors.cpp 默认色
_COLORS = {
    "current_branch": QColor(200, 0, 0),
    "branch": QColor(0, 195, 0),
    "remote": QColor(255, 221, 170),
    "tag": QColor(255, 255, 0),
    "stash": QColor(128, 128, 128),
    "commit": QColor(255, 229, 229),
}


def _best_text_color(bg: QColor) -> QColor:
    """按亮度选择黑/白文字（对齐 GetBestContrastColor）。"""
    r = bg.redF()
    g = bg.greenF()
    b = bg.blueF()

    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)
    return QColor(0, 0, 0) if lum > 0.5 else QColor(255, 255, 255)


def _line_path(rect: QRectF, r: float, top: bool, bottom: bool) -> QPainterPath:
    """一行字形的路径：仅首行圆上角、末行圆下角，其余为直角。"""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = max(0.0, min(r, w / 2, h / 2))
    p = QPainterPath()
    if top:
        p.moveTo(x + r, y)
        p.arcTo(QRectF(x, y, 2 * r, 2 * r), 90, 90)
    else:
        p.moveTo(x, y)
    p.lineTo(x, y + h - (r if bottom else 0))
    if bottom:
        p.arcTo(QRectF(x, y + h - 2 * r, 2 * r, 2 * r), 180, 90)
    else:
        p.lineTo(x, y + h)
    p.lineTo(x + w - (r if bottom else 0), y + h)
    if bottom:
        p.arcTo(QRectF(x + w - 2 * r, y + h - 2 * r, 2 * r, 2 * r), 270, 90)
    else:
        p.lineTo(x + w, y + h)
    p.lineTo(x + w, y + (r if top else 0))
    if top:
        p.arcTo(QRectF(x + w - 2 * r, y, 2 * r, 2 * r), 0, 90)
    else:
        p.lineTo(x + w, y)
    p.closeSubpath()
    return p


def _cut_point(cx: float, cy: float, w: float, h: float, lw: float,
               ps: QPointF, pt: QPointF) -> QPointF:
    """把线段 ps->pt 裁剪到以 (cx,cy) 为中心、尺寸 w×h 的节点边界。"""
    xmin = cx - w / 2 - lw / 2
    xmax = cx + w / 2 + lw / 2
    ymin = cy - h / 2 - lw / 2
    ymax = cy + h / 2 + lw / 2
    dx = pt.x() - ps.x()
    dy = pt.y() - ps.y()
    if dy != 0:
        if pt.y() > ymax:
            x = ps.x() + (ymax - ps.y()) / dy * dx
            if xmin <= x <= xmax:
                return QPointF(x, ymax)
        elif pt.y() < ymin:
            x = ps.x() + (ymin - ps.y()) / dy * dx
            if xmin <= x <= xmax:
                return QPointF(x, ymin)
    if dx != 0:
        if pt.x() > xmax:
            y = ps.y() + (xmax - ps.x()) / dx * dy
            if ymin <= y <= ymax:
                return QPointF(xmax, y)
        elif pt.x() < xmin:
            y = ps.y() + (xmin - ps.x()) / dx * dy
            if ymin <= y <= ymax:
                return QPointF(xmin, y)
    return pt


class _GraphCanvas(QWidget):
    """绘制提交节点图（x=lane/层坐标，y=层）。"""

    def __init__(self, layout: GraphLayout | None = None,
                 current_branch: str | None = None, parent=None):
        super().__init__(parent)
        self._layout = layout
        self._current_branch = current_branch or ""
        if layout is not None:
            self.setMinimumSize(int(layout.width) + 2,
                                int(layout.height) + 2)

    def node_count(self) -> int:
        return len(self._layout.order) if self._layout is not None else 0

    def set_layout(self, layout: GraphLayout, current_branch: str | None,
                   font: QFont):
        self._layout = layout
        self._current_branch = current_branch or ""
        self.setFont(font)
        self.setMinimumSize(int(layout.width) + 2, int(layout.height) + 2)
        self.update()

    # ---- 颜色 ----
    def _ref_color(self, text: str, ref_type: str) -> QColor:
        if ref_type == "branch":
            if text == self._current_branch:
                return _COLORS["current_branch"]
            return _COLORS["branch"]
        return _COLORS.get(ref_type, _COLORS["commit"])

    # ---- 绘制 ----
    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(255, 255, 255))
        if self._layout is None:
            return
        self._draw_edges(p)
        self._draw_nodes(p)

    def _draw_edges(self, p: QPainter):
        assert self._layout is not None
        pen = QPen(QColor(0, 0, 0), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for e in self._layout.edges:
            pts = [QPointF(x, y) for x, y in e.points]
            if len(pts) < 2:
                continue
            src = self._layout.node(e.source)
            dst = self._layout.node(e.target)
            if src is not None:
                pts[0] = _cut_point(src.x, src.y, src.width, src.height, 1,
                                    pts[0], pts[1])
            if dst is not None:
                pts[-1] = _cut_point(dst.x, dst.y, dst.width, dst.height, 1,
                                     pts[-1], pts[-2])
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.drawPath(path)
            self._draw_arrow(p, pts[-1], pts[-2])

    def _draw_arrow(self, p: QPainter, tip: QPointF, prev: QPointF):
        dx = (prev.x() - tip.x()) * -1
        dy = (prev.y() - tip.y()) * -1
        length = math.hypot(dx, dy)
        if length == 0:
            return
        dx = _ARROW_SIZE * dx / length
        dy = _ARROW_SIZE * dy / length
        p1x = dx * _ARROW_COS - dy * _ARROW_SIN
        p1y = dx * _ARROW_SIN + dy * _ARROW_COS
        p2x = dx * _ARROW_COS + dy * _ARROW_SIN
        p2y = -dx * _ARROW_SIN + dy * _ARROW_COS
        d = -1.0
        a0 = QPointF(tip.x() + d * dx * 3 / 5, tip.y() + d * dy * 3 / 5)
        a1 = QPointF(tip.x() + d * p1x, tip.y() + d * p1y)
        a2 = tip
        a3 = QPointF(tip.x() + d * p2x, tip.y() + d * p2y)
        arrow = QPainterPath(a0)
        arrow.lineTo(a1)
        arrow.lineTo(a2)
        arrow.lineTo(a3)
        arrow.lineTo(a0)
        p.drawPath(arrow)

    def _draw_nodes(self, p: QPainter):
        assert self._layout is not None
        for key in self._layout.order:
            node = self._layout.nodes.get(key)
            if node is None:
                continue
            lines = node.lines or [(key[:8], "commit")]
            n = len(lines)
            lh = node.height / n
            left = node.x - node.width / 2
            top = node.y - node.height / 2
            for i, (text, ref_type) in enumerate(lines):
                rect = QRectF(left, top + i * lh, node.width, lh)
                fill = self._ref_color(text, ref_type)
                path = _line_path(rect, _CORNER, i == 0, i == n - 1)
                p.setPen(QPen(QColor(0, 0, 0, 0), 0))
                p.setBrush(QBrush(fill))
                p.drawPath(path)
                p.setPen(QPen(_best_text_color(fill)))
                p.setFont(self.font())
                p.drawText(QRectF(rect.x() + _MARGIN_X, rect.y() + _MARGIN_Y,
                                  rect.width() - 2 * _MARGIN_X,
                                  rect.height() - 2 * _MARGIN_Y),
                           int(Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignVCenter),
                           text)


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
        self.canvas = _GraphCanvas(None, None, self.scroll)
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
        log.load(limit=0, all_branches=True, simplify=True)
        return list(log)

    def _on_loaded(self, commits):
        font = QFont()
        font.setPointSize(_FONT_SIZE)
        fm = QFontMetricsF(font)

        def measure(text: str):
            return float(fm.horizontalAdvance(text)), float(fm.height())

        layout = build_layout(commits, measure)
        self.canvas.set_layout(layout, self.repo.current_branch(), font)

    def _open_stats(self):
        StatGraphDlg(self.repo, parent=self).exec()
